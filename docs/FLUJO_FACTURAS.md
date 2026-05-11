# Flujo de Procesamiento de Facturas

Este documento describe el flujo actual de FactuVal, desde la carga de PDFs
hasta la descarga de `procesadas.xlsx`.

## Actores

| Actor | Archivo | Responsabilidad |
|---|---|---|
| Frontend | `cod_facturas/index.html` | Selecciona PDFs, modo y consulta resultado |
| API | `facturas_app/api/facturas.py` | Recibe archivos y expone estado/descarga |
| Orquestador | `facturas_app/services/invoice_service.py` | Coordina procesamiento completo |
| Validador | `facturas_app/services/invoice_validator.py` | Revisa si el PDF parece factura valida |
| Extractor PDF | `facturas_app/services/pdf_text_extractor.py` | Extrae texto por pagina con timeout |
| Parser | `facturas_app/services/invoice_parser.py` | Convierte texto en registros |
| Excel | `facturas_app/services/invoice_excel_repository.py` | Lee y guarda `procesadas.xlsx` |
| Archivos | `facturas_app/services/invoice_file_manager.py` | Mueve PDFs con reintentos |

`facturas_app/legacy/invoice_legacy.py` queda como compatibilidad y fallback de
facturas, pero el camino normal usa servicios modulares.

## Modos

### `acumular`

- Lee facturas existentes desde `EXCEL_SALIDA`.
- Evita reprocesar numeros de factura ya vistos.
- Agrega registros nuevos al Excel.
- Mueve PDFs correctos a `FACTURAS_PROCESADAS`.

### `separado`

- Procesa la carga actual como corrida independiente.
- Limpia PDFs previos en entrada antes de guardar la nueva carga.
- Crea un Excel para la corrida actual.

## Flujo HTTP

1. El usuario abre:

```text
GET /facturas
```

2. El frontend envia:

```text
POST /upload
```

con:

```text
modo = acumular | separado
files = PDFs seleccionados
```

3. La API responde rapidamente con `processing_started=true` si hay PDFs
validos.

4. El frontend consulta:

```text
GET /resultado
```

5. Cuando termina, descarga:

```text
GET /descargar_excel?file=procesadas.xlsx
```

## Upload

`upload_files()` en `api/facturas.py` hace:

1. Revisa que no haya otro proceso activo.
2. Valida el modo.
3. Limpia entrada si corresponde.
4. Obtiene `request.files.getlist("files")`.
5. Valida extension con `is_allowed_extension()`.
6. Sanitiza nombre con `sanitize_filename()`.
7. Resuelve destino con `resolve_safe_path()`.
8. Guarda el PDF.
9. Valida factura con `InvoiceService.validate_invoice_pdf()`.
10. Mueve rechazados a `FACTURAS_RECHAZADOS`.
11. Lanza un hilo background para procesar validos.

## Procesamiento Background

`_run_background_processing()` crea un `InvoiceService` y llama:

```python
service.process_invoices(mode)
```

El estado global queda en uno de estos valores:

```text
idle
processing
done
error
```

## InvoiceService

`process_invoices()`:

1. Valida el modo.
2. Configura rutas del wrapper legacy para compatibilidad.
3. Ejecuta el pipeline optimizado modular.
4. Si ocurre un error inesperado, usa `invoice_legacy.procesar_facturas()` como
   fallback.

## Pipeline Optimizado

`_run_optimized_pipeline()`:

1. Lista PDFs en `FACTURAS_PATH`.
2. Si el modo es `acumular`, carga facturas existentes desde Excel.
3. Decide cuantos workers usar.
4. Procesa cada PDF con `_process_single_pdf()`.
5. Ordena resultados segun el orden de archivos.
6. Mueve rechazados y errores a sus carpetas.
7. Filtra duplicados en modo `acumular`.
8. Deduplica registros por factura, referencia, producto y total.
9. Guarda el Excel con `InvoiceExcelRepository.save()`.
10. Devuelve un resumen para `/resultado`.

## Procesamiento por PDF

`_process_single_pdf()`:

1. Valida el PDF con `InvoiceValidator`.
2. Extrae paginas con `PdfTextExtractor.extract_pdf_pages_with_retries()`.
3. Parsea paginas con `InvoiceParser.parse_pages()`.
4. Devuelve registros, tiempo y posible error.

## Validacion

`InvoiceValidator` revisa las primeras paginas y busca indicadores como:

- `POSTOBON`
- `FACTURA`
- `CLIENTE:`
- `COD. CLIENTE`
- unidades como `PZA`, `UNIDAD`, `SIX`, `Caja`, `BOL`
- numeros y valores monetarios

Si no cumple, el archivo va a rechazados.

## Extraccion PDF

`PdfTextExtractor`:

- Usa `pdfplumber`.
- Extrae cada pagina en un proceso separado.
- Aplica timeout por pagina.
- Reintenta paginas lentas si `PAGE_FALLBACK_ENABLED=true`.
- Escribe `paginas_timeout.txt` cuando hay paginas con timeout.

## Parsing

`InvoiceParser` extrae:

- numero de factura,
- NIT,
- cliente,
- codigo cliente,
- fecha generacion,
- fecha expedicion,
- referencia,
- producto,
- UMV,
- unidades,
- precio base,
- IVA,
- total,
- estado.

## Excel

`InvoiceExcelRepository` mantiene los encabezados:

```text
ID
Numero Factura
NIT Cliente
Cod Cliente
Nombre Cliente
Fecha Generacion
Fecha Expedicion
Referencia
Producto
UMV
Unidades
Precio Base U
IVA
Total
Estado
```

En modo `acumular`, intenta recuperar datos existentes y reconstruir el Excel si
encuentra corrupcion.

## Carpetas

| Ruta | Uso |
|---|---|
| `FACTURAS_PATH` | PDFs pendientes |
| `FACTURAS_PROCESADAS` | PDFs procesados |
| `FACTURAS_RECHAZADOS` | PDFs no validos |
| `FACTURAS_ERRORES` | PDFs validos que fallaron |
| `EXCEL_SALIDA` | Excel final |
| `PAGE_TEMP_DIR` | Temporales de extraccion |
