import os
import re
import uuid
import logging
import pdfplumber
import time
from typing import Optional
from facturas_app.config import get_settings
from facturas_app.services.invoice_excel_repository import InvoiceExcelRepository
from facturas_app.services.invoice_file_manager import move_file_securely
from facturas_app.services.invoice_parser import (
    clean_product_description,
    extract_customer,
    extract_expedition_date,
    extract_generation_date,
    extract_invoice_number,
    extract_products,
    format_number,
    normalize_customer_name,
    normalize_number,
)
from facturas_app.services.invoice_validator import validate_invoice_pdf
from facturas_app.services.pdf_text_extractor import PdfTextExtractor

_settings = get_settings()
BASE_PATH = str(_settings.base_path)
FACTURAS_ROOT = str(_settings.facturas_root)
FACTURAS_PATH = str(_settings.facturas_path)
FACTURAS_PROCESADAS = str(_settings.facturas_procesadas)
EXCEL_SALIDA = str(_settings.excel_salida)

os.makedirs(FACTURAS_PATH, exist_ok=True)
os.makedirs(FACTURAS_PROCESADAS, exist_ok=True)

tiempos_procesamiento = []
archivos_rechazados_global = []
facturas_con_errores_global = []

logger = logging.getLogger(__name__)
_pdf_text_extractor = PdfTextExtractor()


def _env_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


PAGE_TIMEOUT_SECONDS = float(
    os.getenv("PAGE_TIMEOUT_SECONDS", str(_settings.page_timeout_seconds))
)
PAGE_MAX_WORKERS = int(os.getenv("PAGE_MAX_WORKERS", str(_settings.page_max_workers)))
PAGE_TEMP_DIR = os.getenv("PAGE_TEMP_DIR", str(_settings.page_temp_dir))
PAGE_FALLBACK_ENABLED = _env_bool(
    os.getenv("PAGE_FALLBACK_ENABLED"), _settings.page_fallback_enabled
)


def mover_archivo_seguro(origen: str, destino: str, max_intentos: int = 5) -> bool:
    """Compatibility wrapper around the modular invoice file manager."""
    return move_file_securely(
        origen,
        destino,
        max_attempts=max_intentos,
        message_callback=print,
    )


def normalizar_numero(valor: str) -> str:
    """Compatibility wrapper around the modular invoice parser."""
    return normalize_number(valor)


def formatear_numero(valor: str) -> str:
    """Compatibility wrapper around the modular invoice parser."""
    return format_number(valor)


def _extraer_numero_factura(texto: str) -> Optional[str]:
    """Compatibility wrapper around the modular invoice parser."""
    return extract_invoice_number(texto)


def _normalizar_nombre_cliente(linea: str) -> str:
    """Compatibility wrapper around the modular invoice parser."""
    return normalize_customer_name(linea)


def _extraer_cliente(texto: str) -> tuple[str, str, str]:
    """Compatibility wrapper around the modular invoice parser."""
    return extract_customer(texto)


def _extraer_fecha_generacion(texto: str) -> str:
    """Compatibility wrapper around the modular invoice parser."""
    return extract_generation_date(texto)


def _extraer_fecha_expedicion(texto: str) -> str:
    """Compatibility wrapper around the modular invoice parser."""
    return extract_expedition_date(texto, debug_callback=print)


def _limpiar_producto(descripcion: str) -> str:
    """Compatibility wrapper around the modular invoice parser."""
    return clean_product_description(descripcion)


def _extract_page_text_pdfplumber(pdf_path: str, page_index: int) -> str:
    """Compatibility wrapper around the modular PDF text extractor."""
    return _pdf_text_extractor.extract_page_text_pdfplumber(pdf_path, page_index)


def _page_text_worker(
    engine: str, pdf_path: str, page_index: int, result_queue
) -> None:
    """Compatibility wrapper around the modular PDF text extractor."""
    return _pdf_text_extractor._page_text_worker(
        engine,
        pdf_path,
        page_index,
        result_queue,
    )


def _extract_pages_with_timeout(
    engine: str,
    pdf_path: str,
    page_indices: list[int],
    timeout_seconds: float,
    max_workers: int,
    *,
    source_file: str | None = None,
    page_map: dict[int, int] | None = None,
) -> dict[int, dict]:
    """Compatibility wrapper around the modular PDF text extractor."""
    return _pdf_text_extractor.extract_pages_with_timeout(
        engine,
        pdf_path,
        page_indices,
        timeout_seconds,
        max_workers,
        source_file=source_file,
        page_map=page_map,
    )


def _safe_unlink(path: str) -> None:
    """Compatibility wrapper around the modular PDF text extractor."""
    _pdf_text_extractor.safe_unlink(path)


def _write_timeout_pages_file(
    output_path: str,
    page_indices: list[int],
    total_pages: int,
    source_file: str,
) -> None:
    """Compatibility wrapper around the modular PDF text extractor."""
    _pdf_text_extractor.write_timeout_pages_file(
        output_path,
        page_indices,
        total_pages,
        source_file,
    )


def _es_factura_valida(pdf_path: str) -> tuple[bool, str]:
    """Compatibility wrapper around the modular invoice validator."""
    return validate_invoice_pdf(pdf_path, debug_callback=print)


def _extraer_productos(
    texto: str,
) -> list[tuple[str, str, str, str, str, str, str, str, str, str]]:
    """Compatibility wrapper around the modular invoice parser."""
    return extract_products(texto)


def extraer_datos_factura(
    pdf_path: str,
    facturas_vistas: set,
    paginas_por_bloque: int = 100,
    modo: str = "acumular",
) -> list[dict]:
    datos = []
    archivo_pdf = os.path.basename(pdf_path)
    inicio_extraccion = time.perf_counter()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_paginas = len(pdf.pages)
    except Exception as exc:
        logger.error(
            "Extraction failed to open PDF. file=%s error=%s",
            archivo_pdf,
            exc,
        )
        return datos

    extraction_result = _pdf_text_extractor.extract_pdf_pages_with_retries(
        pdf_path,
        timeout_seconds=PAGE_TIMEOUT_SECONDS,
        max_workers=PAGE_MAX_WORKERS,
        temp_dir_root=PAGE_TEMP_DIR,
        fallback_enabled=PAGE_FALLBACK_ENABLED,
        source_file=archivo_pdf,
    )
    final_texts = extraction_result["texts"]

    logger.info(
        "Extraction start. file=%s mode=%s pages=%s block_size=%s",
        archivo_pdf,
        modo,
        total_paginas,
        paginas_por_bloque,
    )
    try:
        numero_factura = None
        nit_cliente, nombre_cliente, cod_cliente = "", "", ""
        fecha_generacion, fecha_expedicion = "", ""
        productos_totales = []

        def guardar_factura():
            if numero_factura and productos_totales:

                procesar_factura = False
                if modo == "separado":
                    procesar_factura = True
                elif modo == "acumular" and numero_factura not in facturas_vistas:
                    procesar_factura = True
                    facturas_vistas.add(numero_factura)

                if procesar_factura:
                    registros_antes = len(datos)
                    for (
                        ref,
                        prod,
                        umv,
                        unidades,
                        precio_base,
                        iva,
                        total,
                        estado_linea,
                        producto,
                        ml,
                    ) in productos_totales:
                        datos.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "numero_factura": numero_factura,
                                "nit_cliente": nit_cliente,
                                "nombre_cliente": nombre_cliente,
                                "cod_cliente": cod_cliente,
                                "fecha_generacion": fecha_generacion,
                                "fecha_expedicion": fecha_expedicion,
                                "referencia": ref,
                                "productos": producto,
                                "umv": umv,
                                "unidades": unidades,
                                "precio_base_unitario": precio_base,
                                "iva": iva,
                                "total": total,
                                "estado": estado_linea,
                            }
                        )

                    logger.info(
                        "Extraction invoice committed. file=%s numero_factura=%s productos=%s registros_agregados=%s",
                        archivo_pdf,
                        numero_factura,
                        len(productos_totales),
                        len(datos) - registros_antes,
                    )
                else:
                    logger.info(
                        "Extraction invoice skipped. file=%s numero_factura=%s reason=duplicate_in_acumular",
                        archivo_pdf,
                        numero_factura,
                    )

        for start in range(0, total_paginas, paginas_por_bloque):
            end = min(start + paginas_por_bloque, total_paginas)
            inicio_bloque = time.perf_counter()
            logger.info(
                "Extraction block start. file=%s block=%s-%s",
                archivo_pdf,
                start + 1,
                end,
            )

            for page_index in range(start, end):
                pagina_actual = page_index + 1
                inicio_pagina = time.perf_counter()
                logger.info(
                    "Extraction page start. file=%s page=%s",
                    archivo_pdf,
                    pagina_actual,
                )

                texto = final_texts.get(page_index, "")

                if not texto.strip():
                    logger.info(
                        "Extraction page done. file=%s page=%s status=empty elapsed=%.3fs",
                        archivo_pdf,
                        pagina_actual,
                        time.perf_counter() - inicio_pagina,
                    )
                    continue

                m = re.search(
                    r"FACTURA\s+ELECTR[ÓO]NICA\s+DE\s+VENTA\s+No\.?\s*([A-Z0-9\-]+)",
                    texto,
                    flags=re.IGNORECASE,
                )
                if m:
                    nuevo_numero = m.group(1).strip()
                    logger.info(
                        "Extraction field done. file=%s page=%s field=numero_factura value=%s",
                        archivo_pdf,
                        pagina_actual,
                        nuevo_numero,
                    )
                    if numero_factura and nuevo_numero != numero_factura:
                        logger.info(
                            "Extraction invoice boundary detected. file=%s page=%s previous_numero=%s new_numero=%s",
                            archivo_pdf,
                            pagina_actual,
                            numero_factura,
                            nuevo_numero,
                        )
                        guardar_factura()
                        productos_totales = []
                    numero_factura = nuevo_numero

                    inicio_cliente = time.perf_counter()
                    nit_cliente, nombre_cliente, cod_cliente = _extraer_cliente(texto)
                    logger.info(
                        "Extraction field done. file=%s page=%s field=cliente elapsed=%.3fs nit=%s cod=%s nombre=%s",
                        archivo_pdf,
                        pagina_actual,
                        time.perf_counter() - inicio_cliente,
                        nit_cliente,
                        cod_cliente,
                        nombre_cliente,
                    )

                    inicio_fecha_gen = time.perf_counter()
                    fecha_generacion = _extraer_fecha_generacion(texto)
                    logger.info(
                        "Extraction field done. file=%s page=%s field=fecha_generacion elapsed=%.3fs value=%s",
                        archivo_pdf,
                        pagina_actual,
                        time.perf_counter() - inicio_fecha_gen,
                        fecha_generacion,
                    )

                    inicio_fecha_exp = time.perf_counter()
                    fecha_expedicion = _extraer_fecha_expedicion(texto)
                    logger.info(
                        "Extraction field done. file=%s page=%s field=fecha_expedicion elapsed=%.3fs value=%s",
                        archivo_pdf,
                        pagina_actual,
                        time.perf_counter() - inicio_fecha_exp,
                        fecha_expedicion,
                    )
                    print(
                        f"    [DEBUG] Fecha expedición extraída: '{fecha_expedicion}'"
                    )

                inicio_productos = time.perf_counter()
                productos = _extraer_productos(texto)
                logger.info(
                    "Extraction field done. file=%s page=%s field=productos elapsed=%.3fs productos_pagina=%s",
                    archivo_pdf,
                    pagina_actual,
                    time.perf_counter() - inicio_productos,
                    len(productos),
                )
                if productos:
                    productos_totales.extend(productos)
                    logger.info(
                        "Extraction page products aggregated. file=%s page=%s productos_acumulados_factura=%s",
                        archivo_pdf,
                        pagina_actual,
                        len(productos_totales),
                    )

                logger.info(
                    "Extraction page done. file=%s page=%s elapsed=%.3fs",
                    archivo_pdf,
                    pagina_actual,
                    time.perf_counter() - inicio_pagina,
                )

            logger.info(
                "Extraction block done. file=%s block=%s-%s elapsed=%.3fs",
                archivo_pdf,
                start + 1,
                end,
                time.perf_counter() - inicio_bloque,
            )

        guardar_factura()
    except Exception as exc:
        logger.exception(
            "Extraction failed mid-stream. file=%s error=%s partial_records=%s",
            archivo_pdf,
            exc,
            len(datos),
        )
        return datos

    logger.info(
        "Extraction done. file=%s elapsed=%.3fs records=%s",
        archivo_pdf,
        time.perf_counter() - inicio_extraccion,
        len(datos),
    )

    return datos


def cargar_facturas_existentes(excel_path: str) -> set:
    """Compatibility wrapper around the modular Excel repository."""
    return InvoiceExcelRepository(
        excel_path,
        message_callback=print,
    ).load_existing_invoice_numbers()


def _recuperar_datos_excel(excel_path: str) -> list[dict]:
    """Compatibility wrapper around the modular Excel repository."""
    return InvoiceExcelRepository(
        excel_path,
        message_callback=print,
    ).recover_existing_data()


def guardar_en_excel(datos: list[dict], modo: str = "acumular"):
    """Compatibility wrapper around the modular Excel repository."""
    return InvoiceExcelRepository(
        EXCEL_SALIDA,
        message_callback=print,
    ).save(datos, modo)


def procesar_facturas(modo: str = "acumular"):
    global tiempos_procesamiento, archivos_rechazados_global, facturas_con_errores_global

    tiempos_procesamiento = []
    archivos_rechazados_global = []
    facturas_con_errores_global = []

    inicio_total = time.time()
    datos_todas = []
    facturas_encontradas = False
    facturas_vistas = set()
    tiempos_individuales = []
    archivos_rechazados = []
    facturas_con_errores = []
    excel_path = None

    if modo == "acumular":
        excel_path = EXCEL_SALIDA
        facturas_existentes = cargar_facturas_existentes(excel_path)
        facturas_vistas.update(facturas_existentes)
        print(
            f"    [INFO] Modo acumular: {len(facturas_existentes)} facturas ya procesadas encontradas"
        )
    else:
        facturas_vistas = set()
        print(
            f"    [INFO] Modo separado: Procesando TODAS las facturas de esta sesión independientemente"
        )
        print(
            f"    [INFO] Modo separado: facturas_vistas inicializado vacío (no se cargan facturas existentes)"
        )

    for archivo in os.listdir(FACTURAS_PATH):
        if archivo.lower().endswith(".pdf"):
            facturas_encontradas = True
            ruta_pdf = os.path.join(FACTURAS_PATH, archivo)

            print(f"\nValidando: {archivo}")
            es_valida, mensaje_error = _es_factura_valida(ruta_pdf)
            print(
                f"  Resultado validación: es_valida={es_valida}, mensaje={mensaje_error}"
            )

            if not es_valida:
                print(f"  [REJECTED] RECHAZADO: {mensaje_error}")
                archivos_rechazados.append({"archivo": archivo, "razon": mensaje_error})
                carpeta_rechazados = os.path.join(FACTURAS_ROOT, "rechazados")
                os.makedirs(carpeta_rechazados, exist_ok=True)
                destino_rechazado = os.path.join(carpeta_rechazados, archivo)
                if not mover_archivo_seguro(ruta_pdf, destino_rechazado):
                    print(
                        f"    [WARN] No se pudo mover {archivo} a rechazados, pero se procesará normalmente"
                    )
                continue

            print(f"  [VALID] VÁLIDO: {mensaje_error}")

            inicio_archivo = time.time()
            print(f"  Procesando: {archivo}")

            try:
                datos = extraer_datos_factura(ruta_pdf, facturas_vistas, 100, modo)
                fin_archivo = time.time()

                tiempo_archivo = fin_archivo - inicio_archivo
                tiempos_individuales.append(
                    {"archivo": archivo, "tiempo": tiempo_archivo}
                )

                if datos:
                    print(
                        f"  [OK] {archivo} procesado exitosamente en {tiempo_archivo:.2f} seg ({len(datos)} registros)"
                    )
                    datos_todas.extend(datos)

                    if modo == "acumular":
                        destino_procesado = os.path.join(FACTURAS_PROCESADAS, archivo)
                        if not mover_archivo_seguro(ruta_pdf, destino_procesado):
                            print(
                                f"    [WARN] No se pudo mover {archivo} a procesadas, pero los datos se guardaron correctamente"
                            )
                    else:
                        print(
                            f"    [INFO] Modo separado: Archivo {archivo} permanece en carpeta Facturas para permitir reprocesamiento"
                        )
                else:
                    print(f"  [WARN] {archivo} procesado pero no se extrajeron datos")
                    facturas_con_errores.append(
                        {
                            "archivo": archivo,
                            "razon": "Esta factura no se pudo procesar",
                        }
                    )
                    carpeta_errores = os.path.join(FACTURAS_ROOT, "errores")
                    os.makedirs(carpeta_errores, exist_ok=True)
                    destino_errores = os.path.join(carpeta_errores, archivo)
                    if not mover_archivo_seguro(ruta_pdf, destino_errores):
                        print(
                            f"    [WARN] No se pudo mover {archivo} a errores, pero se registró el error"
                        )

            except Exception as e:
                fin_archivo = time.time()
                tiempo_archivo = fin_archivo - inicio_archivo
                error_msg = f"Error durante el procesamiento: {str(e)}"
                print(f"  [ERROR] {archivo} falló: {error_msg}")

                facturas_con_errores.append(
                    {"archivo": archivo, "razon": "Esta factura no se pudo procesar"}
                )

                carpeta_errores = os.path.join(BASE_PATH, "errores")
                os.makedirs(carpeta_errores, exist_ok=True)
                destino_errores = os.path.join(carpeta_errores, archivo)
                if not mover_archivo_seguro(ruta_pdf, destino_errores):
                    print(
                        f"    [WARN] No se pudo mover {archivo} a errores, pero se registró el error"
                    )

    if not facturas_encontradas:
        print("\n No hay facturas nuevas para procesar en la carpeta.")
        fin_total = time.time()
        tiempo_total_procesamiento = fin_total - inicio_total

        return {
            "excel_path": None,
            "tiempos": [],
            "archivos_rechazados": [],
            "facturas_con_errores": [],
            "total_seconds": tiempo_total_procesamiento,
            "facturas_procesadas": 0,
            "facturas_nuevas": 0,
            "facturas_duplicadas": 0,
        }

    if archivos_rechazados:
        print(f"\n [INFO] ARCHIVOS RECHAZADOS ({len(archivos_rechazados)}):")
        for rechazado in archivos_rechazados:
            print(f"  [REJECTED] {rechazado['archivo']}: {rechazado['razon']}")
        print(
            f"  [INFO] Archivos rechazados movidos a: {os.path.join(FACTURAS_ROOT, 'rechazados')}"
        )

    if facturas_con_errores:
        print(
            f"\n [WARN] FACTURAS CON ERRORES DE PROCESAMIENTO ({len(facturas_con_errores)}):"
        )
        for error in facturas_con_errores:
            print(f"  [ERROR] {error['archivo']}: {error['razon']}")
        print(
            f"  [INFO] Facturas con errores movidas a: {os.path.join(FACTURAS_ROOT, 'errores')}"
        )

    if datos_todas:
        unicos = {}
        facturas_nuevas = 0
        facturas_duplicadas = 0

        for d in datos_todas:
            clave = (d["numero_factura"], d["referencia"], d["productos"], d["total"])
            if clave not in unicos:
                unicos[clave] = d
                if modo == "acumular":
                    if d["numero_factura"] in facturas_vistas:
                        facturas_duplicadas += 1
                    else:
                        facturas_nuevas += 1
                else:
                    facturas_nuevas += 1
            else:
                if modo == "acumular":
                    facturas_duplicadas += 1

        excel_path = guardar_en_excel(list(unicos.values()), modo)

        print(f"\n [OK] PROCESAMIENTO COMPLETADO:")
        print(f"  [INFO] Datos guardados en {excel_path}")
        print(f"  [INFO] Facturas válidas movidas a {FACTURAS_PROCESADAS}")
        print(f"  [INFO] Total de registros únicos: {len(unicos)}")

        print(f"  [INFO] Modo: {modo}")

        tiempos_procesamiento = tiempos_individuales.copy()
        archivos_rechazados_global = archivos_rechazados.copy()
        facturas_con_errores_global = facturas_con_errores.copy()

        if tiempos_individuales:
            print(f"\n [INFO] Resumen de tiempos por archivo:")
            for t in tiempos_individuales:
                print(f"  - {t['archivo']}: {t['tiempo']:.2f} seg")

        fin_total = time.time()
        tiempo_total_procesamiento = fin_total - inicio_total

        return {
            "excel_path": excel_path,
            "tiempos": tiempos_individuales,
            "archivos_rechazados": archivos_rechazados,
            "facturas_con_errores": facturas_con_errores,
            "total_seconds": tiempo_total_procesamiento,
            "facturas_procesadas": len(unicos) if "unicos" in locals() else 0,
            "facturas_nuevas": facturas_nuevas,
            "facturas_duplicadas": facturas_duplicadas,
        }
    else:
        print(f"\n [WARN] No se procesaron facturas válidas.")
        if archivos_rechazados:
            print(
                f"  Todos los archivos fueron rechazados por no ser facturas válidas."
            )
        archivos_rechazados_global = archivos_rechazados.copy()
        facturas_con_errores_global = facturas_con_errores.copy()

        fin_total = time.time()
        tiempo_total_procesamiento = fin_total - inicio_total

        return {
            "excel_path": None,
            "tiempos": [],
            "archivos_rechazados": archivos_rechazados,
            "facturas_con_errores": facturas_con_errores,
            "total_seconds": tiempo_total_procesamiento,
            "facturas_procesadas": 0,
        }


if __name__ == "__main__":
    procesar_facturas()
