# Mapa del proyecto ProcesadorFacturas

Este documento explica, en lenguaje práctico, cómo está organizado el proyecto y qué hace cada parte. La intención es que cualquier persona pueda ubicarse antes de tocar código.

## 1. Resumen general

El proyecto es una aplicación local en Flask para automatizaciones operativas de Postobón. Actualmente combina dos estilos de código:

1. **Arquitectura modular nueva**: está en `facturas_app/` y separa API, servicios, utilidades, configuración, modelos y logging.
2. **Código histórico o legacy**: está en `facturas_app/legacy/` y conserva gran parte de la lógica original, especialmente la extracción de facturas PDF, lectura/escritura de Excel, procesos de listas, diferencias, portafolios y DSD.

La aplicación principal se ejecuta con:

```powershell
.\.venv\Scripts\python.exe server.py
```

O con el batch:

```bat
iniciar_servidor.bat
```

El servidor queda disponible normalmente en:

```text
http://localhost:5000
```

## 2. Aplicaciones disponibles

El menú principal vive en `/` y desde ahí se puede entrar a los flujos visibles:

| Ruta | Nombre | Estado actual |
|---|---|---|
| `/` | Menú principal | Sirve `web/index.html`. |
| `/facturas` | FactuVal / Procesador de facturas | Flujo principal para subir PDFs y generar Excel. |
| `/dsd` | Consulta pedidos DSD | Sube Base Jerarquía y genera `Solicitantes_SAP.xlsx`. |
| `/diferencias` | Validador de diferencias | Implementado en legacy, pero en el listado actual no se ven sus HTML/CSS en `web/`. |
| `/listas` | Validador de listas | Implementado en legacy, pero en el listado actual no se ven sus HTML/CSS en `web/`. |
| `/portafolios` | Actualizador de portafolios | Implementado en legacy, pero en el listado actual no se ven sus HTML/CSS en `web/`. |

## 3. Estructura principal de carpetas

```text
Facturas/
  server.py
  iniciar_servidor.bat
  verificar_servidor.py
  requirements.txt
  README.md
  pytest.ini

  facturas_app/
    app.py
    config.py
    logging_config.py
    api/
    services/
    utils/
    models/
    legacy/

  cod_facturas/
    index.html
    styles.css
    main.py

  web/
    index.html
    dsd.html
    styles.css
    dsd.css

  scripts/
    diagnostico.py
    run_server.py

  tests/
    test_config.py
    test_file_security.py
    test_invoice_service.py
```

## 4. Entradas de ejecución

### `server.py`

Es la entrada principal actual.

Responsabilidades:

- Importa `create_app()` desde `facturas_app/app.py`.
- Carga configuración con `get_settings()`.
- Mantiene exportaciones compatibles con scripts antiguos:
  - `main_facturas`
  - `procesar_facturas`
- Ejecuta Flask con host, puerto y debug configurables.

En términos simples: **este archivo arranca el servidor modular**.

### `iniciar_servidor.bat`

Script para Windows.

Responsabilidades:

- Entra al directorio del proyecto.
- Usa `.venv\Scripts\python.exe` si existe.
- Ejecuta `verificar_servidor.py`.
- Si el diagnóstico pasa, ejecuta `server.py`.

### `verificar_servidor.py`

Wrapper de compatibilidad. Solo llama a:

```python
scripts.diagnostico.main()
```

### `scripts/run_server.py`

Entrada alternativa para correr Flask con configuración centralizada.

## 5. Configuración central

### `facturas_app/config.py`

Este archivo define la clase `Settings`, que concentra rutas y parámetros.

Variables importantes:

| Configuración | Para qué sirve |
|---|---|
| `base_path` | Carpeta raíz de trabajo. |
| `facturas_root` | Carpeta base donde viven entradas/salidas de facturas. |
| `facturas_path` | Carpeta donde se guardan PDFs cargados para procesar. |
| `facturas_procesadas` | Carpeta donde se mueven PDFs ya procesados. |
| `facturas_rechazados` | Carpeta para PDFs que no parecen facturas válidas. |
| `facturas_errores` | Carpeta para facturas válidas que fallaron durante extracción. |
| `excel_salida` | Ruta de `procesadas.xlsx`. |
| `facturas_codigo_path` | Ruta del frontend de FactuVal (`cod_facturas`). |
| `web_assets_path` | Ruta de los HTML/CSS generales (`web`). |
| `max_content_length_mb` | Tamaño máximo de carga. Por defecto 100 MB. |
| `allowed_upload_extensions` | Extensiones permitidas para facturas. Por defecto `.pdf`. |
| `allowed_excel_extensions` | Extensiones Excel permitidas. |
| `flask_host` | Host de Flask. Por defecto `0.0.0.0`. |
| `flask_port` | Puerto de Flask. Por defecto `5000`. |
| `processing_parallel_enabled` | Habilita procesamiento paralelo de PDFs. |
| `page_timeout_seconds` | Timeout para extraer texto por página. |
| `page_max_workers` | Número máximo de workers para páginas PDF. |

La función `ensure_directories(settings)` crea las carpetas necesarias en tiempo de ejecución.

## 6. Aplicación Flask modular

### `facturas_app/app.py`

Contiene `create_app(settings=None)`.

Responsabilidades:

- Crea la instancia Flask.
- Carga configuración.
- Crea carpetas necesarias.
- Configura logging.
- Configura CORS.
- Registra blueprints:
  - `facturas_bp`
  - `health_bp`
  - `legacy_bp`
- Define manejadores globales de error:
  - Payload demasiado grande `413`.
  - Excepciones HTTP.
  - Excepciones inesperadas.

En términos simples: **este archivo arma la aplicación web completa**.

## 7. Capa API moderna

### `facturas_app/api/facturas.py`

Este es el API moderno de FactuVal.

Endpoints principales:

| Endpoint | Método | Qué hace |
|---|---|---|
| `/facturas` | GET | Sirve la pantalla `cod_facturas/index.html`. |
| `/facturas/styles.css` | GET | Sirve el CSS de FactuVal. |
| `/facturas/<filename>` | GET | Sirve assets estáticos de `cod_facturas`. |
| `/upload` | POST/OPTIONS | Recibe PDFs, valida extensión, sanitiza nombres, valida factura y lanza procesamiento en background. |
| `/resultado` | GET | Devuelve estado actual del procesamiento: `idle`, `processing`, `done` o `error`. |
| `/descargar_excel` | GET | Descarga el Excel generado desde la carpeta permitida. |

Puntos importantes:

- Usa un estado global protegido por lock: `_processing_state`.
- Solo permite un proceso de facturas a la vez.
- Usa `InvoiceService` para validar y procesar.
- Ejecuta el procesamiento pesado en un `threading.Thread` para no bloquear la respuesta HTTP.
- Sanitiza nombres de archivos antes de guardar.
- Mueve archivos rechazados a `facturas_rechazados`.

### `facturas_app/api/health.py`

Endpoint sencillo:

```text
GET /api/health
```

Devuelve:

```json
{
  "ok": true,
  "message": "ok",
  "status": "healthy",
  "timestamp": "..."
}
```

### `facturas_app/api/legacy_proxy.py`

Es un proxy hacia `facturas_app/legacy/server_legacy.py`.

Responsabilidades:

- Mantener rutas antiguas funcionando.
- Delegar endpoints de:
  - menú principal,
  - diferencias,
  - listas,
  - portafolios,
  - DSD,
  - assets estáticos legacy.

Importante: aquí casi no hay lógica propia; la mayoría de funciones hacen:

```python
return _legacy().alguna_funcion()
```

## 8. Servicio principal de facturas

### `facturas_app/services/invoice_service.py`

Es el punto moderno de orquestación del procesamiento de facturas.

Responsabilidades actuales:

- Configurar rutas del módulo legacy para que use `Settings`.
- Validar PDF usando `_es_factura_valida` de legacy.
- Mover archivos usando `mover_archivo_seguro` de legacy.
- Detectar si legacy tiene funciones suficientes para usar pipeline optimizado.
- Procesar PDFs secuencialmente o en paralelo.
- Filtrar duplicados en modo `acumular`.
- Llamar a `extraer_datos_factura` de legacy.
- Llamar a `guardar_en_excel` de legacy.
- Devolver un resumen tipado (`ProcessingSummary`).

Funciones importantes:

| Función | Qué hace |
|---|---|
| `validate_invoice_pdf()` | Valida una factura PDF usando legacy y usa caché por archivo/tamaño/fecha. |
| `move_file()` | Mueve archivos con reintentos usando legacy. |
| `process_invoices()` | Entrada principal del servicio. Valida modo y elige pipeline optimizado o legacy. |
| `_run_optimized_pipeline()` | Pipeline moderno de orquestación, pero todavía usando funciones legacy internas. |
| `_process_single_pdf()` | Valida y extrae registros de un PDF individual. |
| `_filter_records_for_accumulated_mode()` | Evita duplicados en modo acumular. |

Conclusión importante:

> `InvoiceService` organiza el flujo, pero **la extracción real del texto del PDF y el guardado del Excel siguen en `legacy/invoice_legacy.py`**.

## 9. Modelos

### `facturas_app/models/dto.py`

Define estructuras de datos pequeñas:

- `FileIssue`: representa archivo rechazado y razón.
- `ProcessingSummary`: estructura esperada al terminar procesamiento.

Actualmente todavía hay pocos modelos. Una refactorización futura debería crear modelos más claros para:

- factura,
- cliente,
- producto,
- línea de factura,
- resultado de procesamiento.

## 10. Utilidades

### `facturas_app/utils/file_security.py`

Funciones de seguridad para archivos:

| Función | Qué hace |
|---|---|
| `sanitize_filename()` | Limpia nombres peligrosos usando `secure_filename`. |
| `is_allowed_extension()` | Verifica extensión permitida. |
| `resolve_safe_path()` | Evita path traversal; asegura que el archivo quede dentro de la carpeta base. |
| `clear_directory_files()` | Borra archivos de una carpeta según sufijos permitidos. |

### `facturas_app/utils/responses.py`

Normaliza respuestas JSON:

- `success_response(...)`
- `error_response(...)`

Todas incluyen `timestamp` UTC.

## 11. Capa legacy

### `facturas_app/legacy/bridge.py`

Carga módulos legacy con caché:

```python
get_invoice_legacy()
get_server_legacy()
```

Esto evita imports repetidos y mantiene compatibilidad.

### `facturas_app/legacy/invoice_legacy.py`

Archivo grande con la lógica original de facturas.

Responsabilidades actuales:

- Validar que un PDF parezca factura.
- Extraer texto de páginas PDF usando `pdfplumber`.
- Manejar extracción por páginas con procesos y timeout.
- Extraer:
  - número de factura,
  - cliente,
  - NIT,
  - código cliente,
  - fecha generación,
  - fecha expedición,
  - productos,
  - cantidades,
  - precios,
  - IVA,
  - totales.
- Cargar facturas existentes desde Excel.
- Recuperar datos si un Excel existente está corrupto.
- Guardar `procesadas.xlsx`.
- Mover PDFs a carpetas de salida, rechazados o errores.
- Ejecutar el procesamiento legacy completo con `procesar_facturas()`.

Funciones más importantes:

| Función | Qué hace |
|---|---|
| `_es_factura_valida(pdf_path)` | Valida indicadores mínimos de factura. |
| `extraer_datos_factura(pdf_path, facturas_vistas, paginas_por_bloque, modo)` | Extrae registros de factura desde PDF. |
| `_extraer_productos(texto)` | Extrae líneas de productos desde texto. |
| `_extraer_cliente(texto)` | Extrae NIT, nombre y código cliente. |
| `_extraer_fecha_generacion(texto)` | Extrae fecha de generación. |
| `_extraer_fecha_expedicion(texto)` | Extrae fecha de expedición. |
| `cargar_facturas_existentes(excel_path)` | Lee facturas ya procesadas. |
| `guardar_en_excel(datos, modo)` | Guarda/actualiza `procesadas.xlsx`. |
| `procesar_facturas(modo)` | Procesamiento legacy completo. |

### `facturas_app/legacy/server_legacy.py`

Archivo grande con el servidor monolítico original.

Responsabilidades actuales:

- Servir algunas páginas y assets.
- Ejecutar flujos de listas y diferencias.
- Automatizar SAP GUI usando `win32com.client`.
- Actualizar portafolios en Excel mediante COM.
- Procesar DSD.
- Mantener endpoints antiguos de facturas.

Flujos principales dentro de este archivo:

| Flujo | Funciones relacionadas |
|---|---|
| Listas | `_run_listas`, `api_listas_iniciar`, `api_listas_estado`, `api_listas_descargar`. |
| Diferencias | `_run_diferencias`, `api_diferencias_iniciar`, `api_diferencias_estado`, `api_diferencias_descargar`. |
| Portafolios | `_run_portafolios`, `_actualizar_excel_portafolio`, `api_portafolios_iniciar`, `api_portafolios_progreso`. |
| DSD | `_run_dsd`, `api_dsd_upload`, `api_dsd_iniciar`, `api_dsd_estado`, `api_dsd_descargar`. |
| Facturas legacy | `upload_files`, `run_procesamiento_facturas`, `resultado`, `descargar_excel`. |

## 12. Frontend

### `cod_facturas/index.html`

Pantalla de FactuVal.

Responsabilidades:

- Permitir arrastrar o seleccionar PDFs.
- Seleccionar modo:
  - `acumular`,
  - `separado`.
- Mostrar archivos seleccionados.
- Advertir por archivos grandes.
- Calcular tiempo estimado aproximado revisando estructura interna del PDF.
- Enviar PDFs a `/upload` con `FormData`.
- Consultar `/resultado` cada 2 segundos mientras procesa.
- Mostrar botón de descarga cuando termina.
- Descargar desde `/descargar_excel?file=...`.

### `cod_facturas/styles.css`

Estilos de FactuVal.

### `cod_facturas/main.py`

Wrapper de compatibilidad:

```python
from facturas_app.legacy.invoice_legacy import *
```

Esto permite que scripts viejos que importaban `cod_facturas/main.py` sigan funcionando.

### `web/index.html`

Menú principal. Actualmente muestra tarjetas para:

- Procesador de facturas.
- Consulta DSD.

### `web/dsd.html`

Pantalla para DSD.

Responsabilidades:

- Subir archivo Excel a `/api/dsd/upload`.
- Iniciar proceso con `/api/dsd/iniciar`.
- Consultar estado con `/api/dsd/estado`.
- Descargar resultado con `/api/dsd/descargar`.

## 13. Pruebas

### `tests/test_config.py`

Valida que `Settings.from_env()` respete variables de entorno.

### `tests/test_file_security.py`

Valida:

- sanitización de nombres,
- extensiones permitidas,
- rutas seguras,
- limpieza de archivos por sufijo.

### `tests/test_invoice_service.py`

Valida:

- que `InvoiceService` llame al módulo legacy esperado,
- que rechace modos inválidos,
- que use caché de validación,
- que el pipeline optimizado procese y guarde registros con un legacy falso.

Comando recomendado:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Resultado observado al revisar el proyecto:

```text
9 passed
```

## 14. Mapa mental rápido

```text
Usuario en navegador
   ↓
cod_facturas/index.html
   ↓ POST /upload
facturas_app/api/facturas.py
   ↓
InvoiceService
   ↓
legacy/invoice_legacy.py
   ├─ valida PDF
   ├─ extrae texto
   ├─ parsea factura/productos
   └─ guarda Excel
   ↓
Facturas/procesadas.xlsx
   ↑
GET /descargar_excel
```

## 15. Problema principal actual

El sistema funciona, pero está difícil de entender porque muchas responsabilidades están concentradas en archivos legacy enormes.

Especialmente:

- `legacy/invoice_legacy.py` mezcla validación, extracción PDF, parsing, Excel, movimiento de archivos y proceso completo.
- `legacy/server_legacy.py` mezcla servidor web, SAP, Excel COM, listas, diferencias, portafolios, DSD y endpoints antiguos.
- `InvoiceService` ya ordena parte del flujo, pero todavía depende de funciones internas legacy.

La solución recomendada no es mover todo a `InvoiceService`, sino crear módulos pequeños con responsabilidades claras.
