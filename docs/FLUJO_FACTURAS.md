# Flujo actual de procesamiento de facturas

Este documento explica paso a paso qué ocurre cuando el usuario sube PDFs desde FactuVal.

## 1. Actores principales

| Actor | Archivo | Responsabilidad |
|---|---|---|
| Frontend FactuVal | `cod_facturas/index.html` | Permite subir PDFs, elegir modo y consultar resultado. |
| API FactuVal | `facturas_app/api/facturas.py` | Recibe archivos, valida entrada y lanza procesamiento. |
| Servicio | `facturas_app/services/invoice_service.py` | Orquesta validación, extracción, duplicados y guardado. |
| Legacy facturas | `facturas_app/legacy/invoice_legacy.py` | Hace validación real, extracción PDF y escritura Excel. |
| Seguridad archivos | `facturas_app/utils/file_security.py` | Sanitiza nombres y evita rutas inseguras. |
| Configuración | `facturas_app/config.py` | Define carpetas y parámetros del proceso. |

## 2. Modos de procesamiento

La interfaz permite dos modos:

### Modo `acumular`

Objetivo: agregar facturas nuevas al Excel existente.

Características:

- Lee `procesadas.xlsx` si existe.
- Carga números de factura existentes.
- Intenta evitar duplicados.
- Mueve PDFs procesados a carpeta de salida/procesadas.

### Modo `separado`

Objetivo: procesar la carga actual como una corrida independiente.

Características:

- No usa el Excel existente para filtrar facturas previas.
- Puede reprocesar las facturas de la sesión.
- El frontend lo describe como crear/sobrescribir un Excel nuevo.

## 3. Flujo desde el navegador

### Paso 1: usuario abre FactuVal

Ruta:

```text
GET /facturas
```

Archivo servido:

```text
cod_facturas/index.html
```

El HTML carga:

```text
/facturas/styles.css
```

### Paso 2: usuario selecciona archivos

En el navegador:

- Solo acepta PDFs por `accept="application/pdf"`.
- Permite múltiples archivos.
- Calcula un tiempo estimado aproximado leyendo marcas internas del PDF como `/Count`, `/Type /Page`, `/Kids`, etc.
- Si un archivo pesa más de 8 MB, pregunta si se quiere cargar ahora o después.

Esta validación del frontend es solo ayuda visual. La validación real ocurre en backend.

### Paso 3: usuario presiona Cargar

El frontend crea un `FormData` con:

```text
modo = acumular | separado
files = PDFs seleccionados
```

Luego envía:

```text
POST /upload
```

## 4. Flujo en `/upload`

Archivo:

```text
facturas_app/api/facturas.py
```

Función:

```python
upload_files()
```

### Paso 4.1: valida si ya hay proceso activo

El backend mantiene un estado global:

```python
_processing_state = {"status": "idle"}
```

Si está en `processing`, responde error `409`:

```json
{
  "ok": false,
  "error": "Ya hay un proceso en ejecución"
}
```

### Paso 4.2: lee modo

```python
mode = request.form.get("modo", "acumular")
```

Solo permite:

```text
acumular
separado
```

Si llega otro valor, responde `400`.

### Paso 4.3: limpia carpeta si aplica

Si:

- `modo == "separado"`, o
- `limpiar == "1"`,

borra PDFs existentes en `settings.facturas_path`.

### Paso 4.4: valida archivos enviados

Obtiene archivos con:

```python
files = request.files.getlist("files")
```

Si no llegan archivos, responde `400`.

### Paso 4.5: por cada archivo

Por cada PDF:

1. Toma nombre original.
2. Verifica extensión permitida con `is_allowed_extension()`.
3. Sanitiza nombre con `sanitize_filename()`.
4. Resuelve ruta segura con `resolve_safe_path()`.
5. Guarda archivo en carpeta de entrada.
6. Valida si es factura usando:

```python
service.validate_invoice_pdf(destination)
```

Internamente eso llama legacy:

```python
legacy._es_factura_valida(...)
```

Si no es válida:

- la agrega a `rejected`,
- la mueve a `facturas_rechazados`,
- no la procesa.

Si es válida:

- la agrega a `saved`.

### Paso 4.6: si no hay archivos válidos

Responde algo como:

```json
{
  "ok": true,
  "status": "ok",
  "saved": [],
  "processing_started": false,
  "run_id": null,
  "archivos_rechazados": [...],
  "message": "No hay archivos válidos para procesar"
}
```

### Paso 4.7: si hay archivos válidos

Crea un `run_id`:

```python
run_id = uuid.uuid4().hex
```

Cambia estado a:

```python
{
  "status": "processing",
  "run_id": run_id,
  "tiempo_inicio": time.time(),
  "modo": mode,
}
```

Lanza un hilo:

```python
threading.Thread(
    target=_run_background_processing,
    args=(mode, run_id, settings),
    daemon=True,
)
```

Responde inmediatamente al frontend:

```json
{
  "ok": true,
  "status": "ok",
  "saved": ["factura.pdf"],
  "processing_started": true,
  "run_id": "...",
  "archivos_rechazados": []
}
```

## 5. Procesamiento en background

Archivo:

```text
facturas_app/api/facturas.py
```

Función:

```python
_run_background_processing(mode, run_id, settings)
```

Hace:

```python
service = InvoiceService(settings=settings)
result = service.process_invoices(mode)
```

Si todo sale bien, cambia estado a `done` con resumen.

Si falla, cambia estado a `error`.

## 6. Qué hace `InvoiceService.process_invoices()`

Archivo:

```text
facturas_app/services/invoice_service.py
```

Función:

```python
process_invoices(mode="acumular")
```

### Paso 6.1: valida modo

Solo acepta:

```text
acumular
separado
```

### Paso 6.2: configura contexto legacy

Usa:

```python
with self._legacy_runtime_context():
```

Esto hace dos cosas:

1. Sobrescribe variables globales del legacy con rutas de `Settings`:

```python
FACTURAS_ROOT
FACTURAS_PATH
FACTURAS_PROCESADAS
EXCEL_SALIDA
BASE_PATH
```

2. Opcionalmente silencia `print` del legacy para evitar demasiados logs.

### Paso 6.3: decide pipeline

Si el legacy tiene estas funciones:

```text
_es_factura_valida
cargar_facturas_existentes
extraer_datos_factura
guardar_en_excel
mover_archivo_seguro
```

usa pipeline optimizado:

```python
self._run_optimized_pipeline(mode)
```

Si algo falla, cae al legacy completo:

```python
self._legacy.procesar_facturas(mode)
```

## 7. Pipeline optimizado actual

Archivo:

```text
facturas_app/services/invoice_service.py
```

Función:

```python
_run_optimized_pipeline(mode)
```

### Paso 7.1: recoge PDFs

Busca archivos `.pdf` en:

```python
settings.facturas_path
```

### Paso 7.2: carga facturas existentes si es acumular

Si `mode == "acumular"`, llama:

```python
self._legacy.cargar_facturas_existentes(str(self.settings.excel_salida))
```

Esto devuelve un conjunto de números de factura ya procesadas.

### Paso 7.3: decide paralelismo

Usa `_resolve_workers(total_files)`.

Puede procesar varios PDFs en paralelo con `ThreadPoolExecutor`, dependiendo de:

- cantidad de archivos,
- `processing_parallel_enabled`,
- `processing_max_workers`,
- CPU disponible.

### Paso 7.4: procesa cada PDF

Por cada archivo llama:

```python
_process_single_pdf(pdf_path, mode)
```

## 8. Procesamiento de un PDF individual

Archivo:

```text
facturas_app/services/invoice_service.py
```

Función:

```python
_process_single_pdf(pdf_path, mode)
```

Hace:

1. Valida con:

```python
self.validate_invoice_pdf(pdf_path)
```

2. Si no es válida, devuelve resultado rechazado.

3. Si es válida, llama legacy para extraer datos:

```python
records = self._legacy.extraer_datos_factura(
    str(pdf_path),
    set(),
    100,
    extraction_mode,
)
```

Aquí está el punto clave:

> La extracción real del texto PDF todavía ocurre en `legacy/invoice_legacy.py`.

## 9. Extracción real en legacy

Archivo:

```text
facturas_app/legacy/invoice_legacy.py
```

Función principal:

```python
extraer_datos_factura(pdf_path, facturas_vistas, paginas_por_bloque=100, modo="acumular")
```

### Paso 9.1: abre PDF

Usa:

```python
pdfplumber.open(pdf_path)
```

para conocer número total de páginas.

### Paso 9.2: extrae texto por página

Usa:

```python
_extract_pages_with_timeout(...)
```

Esa función crea procesos separados con `multiprocessing` para evitar que una página bloqueada congele todo el procesamiento.

La extracción por página usa:

```python
_extract_page_text_pdfplumber(pdf_path, page_index)
```

que hace:

```python
pdf.pages[page_index].extract_text()
```

### Paso 9.3: maneja timeout

Si una página se demora demasiado:

- marca estado `TIMEOUT`,
- termina el proceso,
- guarda una lista de páginas con timeout en `PAGE_TEMP_DIR`,
- puede reintentar con timeout más alto si `PAGE_FALLBACK_ENABLED` está activo.

### Paso 9.4: parsea factura

Por cada página con texto:

- busca número de factura,
- detecta cambio de factura dentro del PDF,
- extrae cliente,
- extrae fechas,
- extrae productos.

Funciones de parsing:

```python
_extraer_cliente(texto)
_extraer_fecha_generacion(texto)
_extraer_fecha_expedicion(texto)
_extraer_productos(texto)
```

### Paso 9.5: crea registros

Por cada producto encontrado crea un diccionario con forma aproximada:

```python
{
    "id": "...",
    "numero_factura": "...",
    "nit_cliente": "...",
    "nombre_cliente": "...",
    "cod_cliente": "...",
    "fecha_generacion": "...",
    "fecha_expedicion": "...",
    "referencia": "...",
    "productos": "...",
    "umv": "...",
    "unidades": "...",
    "precio_base_unitario": "...",
    "iva": "...",
    "total": "...",
    "estado": "OK",
}
```

## 10. Regreso al pipeline moderno

Después de extraer cada PDF, `InvoiceService._run_optimized_pipeline()`:

1. Ordena resultados respetando orden de archivos.
2. Mueve rechazados a `facturas_rechazados`.
3. Mueve facturas con error a `facturas_errores`.
4. En modo `acumular`, filtra facturas duplicadas.
5. Acumula todos los registros válidos.
6. Quita duplicados por clave:

```python
(
    numero_factura,
    referencia,
    productos,
    total,
)
```

7. Guarda Excel usando legacy:

```python
self._legacy.guardar_en_excel(list(unicos.values()), mode)
```

## 11. Guardado real del Excel

Archivo:

```text
facturas_app/legacy/invoice_legacy.py
```

Función:

```python
guardar_en_excel(datos, modo="acumular")
```

Responsabilidades:

- Usa `EXCEL_SALIDA` como ruta final.
- Si está en modo `acumular` y el Excel existe:
  - intenta abrirlo,
  - recupera datos existentes,
  - si hay error/corrupción intenta recuperar con pandas/openpyxl,
  - crea backup si puede.
- Crea encabezados si el archivo no existe o se recrea.
- Deduplica por:

```python
numero_factura + referencia + productos + total
```

- Formatea números.
- Guarda con `openpyxl`.

Columnas generadas:

```text
ID
Número Factura
NIT Cliente
Cod Cliente
Nombre Cliente
Fecha Generación
Fecha Expedición
Referencia
Producto
UMV
Unidades
Precio Base U
IVA
Total
Estado
```

## 12. Consulta de resultado desde frontend

Después del upload, el frontend consulta cada 2 segundos:

```text
GET /resultado
```

### Si está procesando

Respuesta aproximada:

```json
{
  "ok": true,
  "status": "processing",
  "tiempo_actual": "10 seg",
  "tiempo_segundos": 10.2,
  "run_id": "..."
}
```

### Si terminó

Respuesta aproximada:

```json
{
  "ok": true,
  "status": "done",
  "tiempos": [...],
  "total": "1 min 20 seg",
  "excel": "procesadas.xlsx",
  "archivos_rechazados": [...],
  "facturas_con_errores": [...],
  "modo": "acumular",
  "run_id": "...",
  "facturas_procesadas": 10,
  "facturas_nuevas": 8,
  "facturas_duplicadas": 2
}
```

### Si falló

Respuesta con error `500`:

```json
{
  "ok": false,
  "error": "Error durante el procesamiento",
  "details": {
    "run_id": "...",
    "error": "..."
  }
}
```

## 13. Descarga del Excel

Cuando `/resultado` devuelve `done`, el frontend muestra botón de descarga.

Ruta:

```text
GET /descargar_excel?file=procesadas.xlsx
```

El backend:

1. Valida extensión permitida.
2. Sanitiza nombre.
3. Resuelve ruta segura dentro de `facturas_root`.
4. Verifica existencia.
5. Envía archivo como adjunto.

## 14. Carpetas usadas en el flujo

Por defecto, bajo `Facturas/`:

| Carpeta/archivo | Uso |
|---|---|
| `Facturas/entrada/` | PDFs cargados pendientes de procesar. |
| `Facturas/salida/` | PDFs procesados correctamente en modo acumular. |
| `Facturas/rechazados/` | PDFs que no parecen facturas válidas. |
| `Facturas/errores/` | PDFs válidos, pero que no pudieron extraerse correctamente. |
| `Facturas/procesadas.xlsx` | Excel final generado. |
| `Facturas/temp/` | Archivos temporales relacionados con páginas con timeout. |

## 15. Dónde está el desorden actual

El flujo actual ya tiene un buen API y un buen servicio orquestador, pero todavía depende de legacy para las partes más complejas:

```text
InvoiceService
   ├─ organiza proceso
   ├─ paraleliza
   ├─ filtra duplicados
   └─ llama a legacy para:
       ├─ validar PDF
       ├─ extraer texto
       ├─ parsear factura
       └─ guardar Excel
```

Por eso, para entender la extracción, no basta con leer `invoice_service.py`; hay que leer también `legacy/invoice_legacy.py`.

## 16. Resumen corto

```text
1. Usuario sube PDFs desde /facturas.
2. /upload guarda y valida archivos.
3. Si hay válidos, inicia hilo background.
4. InvoiceService coordina procesamiento.
5. invoice_legacy extrae texto, parsea datos y guarda Excel.
6. /resultado informa avance o finalización.
7. /descargar_excel entrega procesadas.xlsx.
```
