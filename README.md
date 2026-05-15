# Automatizacion de Facturas - Postobon

Aplicacion local en Flask para operar tres flujos visibles:

- **FactuVal**: carga facturas PDF, extrae datos y genera `procesadas.xlsx`.
- **Consulta DSD**: carga Base Jerarquia y genera `Solicitantes_SAP.xlsx`.
- **Dividir PDF**: carga un PDF y descarga un ZIP con el archivo separado.

La app fue depurada para que el backend exponga solo lo que aparece en el menu
actual. Los antiguos endpoints de listas, diferencias y portafolios fueron
retirados junto con el servidor monolitico que los cargaba.

## Estado Actual

Rutas visibles:

| Ruta | Descripcion |
|---|---|
| `/` | Menu principal |
| `/facturas` | Procesador de facturas PDF |
| `/dsd` | Consulta pedidos DSD |
| `/dividir-pdf` | Herramienta para dividir un PDF |
| `/depurar-pdf` | Herramienta para conservar paginas impares de un PDF |

APIs activas:

| Endpoint | Metodo | Uso |
|---|---|---|
| `/upload` | `POST` | Sube PDFs de facturas |
| `/resultado` | `GET` | Consulta estado del procesamiento de facturas |
| `/descargar_excel` | `GET` | Descarga `procesadas.xlsx` |
| `/api/dsd/upload` | `POST` | Sube Base Jerarquia |
| `/api/dsd/iniciar` | `POST` | Inicia procesamiento DSD |
| `/api/dsd/estado` | `GET` | Consulta estado DSD |
| `/api/dsd/descargar` | `GET` | Descarga `Solicitantes_SAP.xlsx` |
| `/api/pdf/dividir` | `POST` | Divide un PDF y devuelve un ZIP |
| `/api/pdf/depurar` | `POST` | Conserva paginas impares y devuelve un PDF |
| `/api/health` | `GET` | Healthcheck |

Rutas retiradas:

```text
/diferencias
/listas
/portafolios
/api/diferencias/*
/api/listas/*
/api/portafolios/*
```

## Arquitectura

```text
server.py
  |
  v
facturas_app/app.py
  |
  |-- api/pages.py       Menu, estilos y pagina DSD
  |-- api/facturas.py    API y pagina FactuVal
  |-- api/dsd.py         API del flujo DSD
  |-- api/pdf_tools.py   API de herramientas PDF
  |-- api/health.py      Healthcheck
  |
  v
facturas_app/services/
  |-- invoice_service.py
  |-- invoice_validator.py
  |-- pdf_text_extractor.py
  |-- invoice_parser.py
  |-- invoice_excel_repository.py
  |-- invoice_file_manager.py
  |-- dsd_service.py
  |-- pdf_split_service.py
  |-- pdf_deduplication_service.py
```

La carpeta `facturas_app/legacy/` se conserva solo para compatibilidad del flujo
de facturas. Ya no hay servidor legacy registrado en Flask.

## Estructura Principal

```text
Facturas/
  server.py
  iniciar_servidor.bat
  verificar_servidor.py
  requirements.txt
  pytest.ini
  .env.example

  facturas_app/
    app.py
    config.py
    logging_config.py
    api/
      pages.py
      facturas.py
      dsd.py
      pdf_tools.py
      health.py
    services/
      invoice_service.py
      invoice_validator.py
      pdf_text_extractor.py
      invoice_parser.py
      invoice_excel_repository.py
      invoice_file_manager.py
      dsd_service.py
      pdf_split_service.py
    utils/
      file_security.py
      responses.py
    models/
      dto.py
    legacy/
      invoice_legacy.py
      bridge.py

  cod_facturas/
    index.html
    styles.css
    main.py

  web/
    index.html
    styles.css
    dsd.html
    dsd.css
    dividir-pdf.html
    depurar-pdf.html
    pdf.css

  scripts/
    diagnostico.py
    run_server.py

  tests/
    test_*.py
```

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dependencias principales:

- `Flask`
- `flask-cors`
- `pdfplumber`
- `PyMuPDF`
- `pandas`
- `openpyxl`
- `python-dotenv`
- `pytest`

## Ejecucion

Entrada recomendada:

```powershell
python server.py
```

Tambien puedes usar:

```bat
iniciar_servidor.bat
```

El servidor queda disponible por defecto en:

```text
http://localhost:5000
http://127.0.0.1:5000
```

## Configuracion

`facturas_app/config.py` centraliza la configuracion. Si existe `.env`,
`python-dotenv` lo carga automaticamente.

Puedes partir de:

```powershell
Copy-Item .env.example .env
```

Variables principales:

| Variable | Uso |
|---|---|
| `BASE_PATH` | Carpeta base local |
| `FACTURAS_ROOT` | Carpeta base del flujo de facturas |
| `FACTURAS_PATH` | PDFs pendientes |
| `FACTURAS_PROCESADAS` | PDFs procesados |
| `FACTURAS_RECHAZADOS` | PDFs rechazados |
| `FACTURAS_ERRORES` | PDFs con error de extraccion |
| `FACTURAS_CODIGO_PATH` | Carpeta `cod_facturas` |
| `EXCEL_SALIDA` | Ruta de `procesadas.xlsx` |
| `WEB_ASSETS_PATH` | Carpeta `web` |
| `RUTA_SALIDA_DSD` | Carpeta de salida DSD |
| `DSD_TEMP_PATH` | Temporales de carga DSD |
| `MAX_CONTENT_LENGTH_MB` | Limite de subida |
| `ALLOWED_UPLOAD_EXTENSIONS` | Extensiones de facturas permitidas |
| `ALLOWED_EXCEL_EXTENSIONS` | Extensiones Excel permitidas |
| `FLASK_HOST` | Host Flask |
| `FLASK_PORT` | Puerto Flask |
| `FLASK_DEBUG` | Modo debug |
| `PROCESSING_PARALLEL_ENABLED` | Paralelismo de facturas |
| `PROCESSING_MAX_WORKERS` | Maximo de workers |
| `PAGE_TIMEOUT_SECONDS` | Timeout por pagina PDF |
| `PAGE_MAX_WORKERS` | Workers para extraccion de paginas |
| `PAGE_TEMP_DIR` | Temporales de extraccion PDF |
| `PAGE_FALLBACK_ENABLED` | Reintento de paginas con timeout |

## Flujo FactuVal

1. El usuario abre `/facturas`.
2. Selecciona uno o varios PDFs.
3. El frontend envia `POST /upload`.
4. El backend valida extension, nombre seguro y contenido del PDF.
5. Los archivos rechazados van a `FACTURAS_RECHAZADOS`.
6. Los validos se procesan en un hilo background.
7. `InvoiceService` coordina validacion, extraccion, parsing y guardado.
8. `InvoiceExcelRepository` crea o actualiza `procesadas.xlsx`.
9. El frontend consulta `/resultado`.
10. Al finalizar, descarga con `/descargar_excel`.

Modos:

- `acumular`: agrega nuevas facturas al Excel existente y evita duplicados.
- `separado`: procesa la carga actual como corrida independiente.

## Flujo DSD

1. El usuario abre `/dsd`.
2. Sube Base Jerarquia con `/api/dsd/upload`.
3. Inicia el proceso con `/api/dsd/iniciar`.
4. `DsdService` busca columnas `Cliente J1`, `Nombre`, `Nombre 2` y `Cliente J3`.
5. Agrupa cada solicitante con sus clientes J3 unicos.
6. Genera `Solicitantes_SAP.xlsx`.
7. La UI consulta `/api/dsd/estado`.
8. Descarga con `/api/dsd/descargar`.

## Flujo Dividir PDF

1. El usuario abre `/dividir-pdf`.
2. Selecciona un archivo `.pdf`.
3. Ingresa el numero de partes.
4. El frontend envia `POST /api/pdf/dividir` como `multipart/form-data`:
   - `file`: PDF de origen.
   - `partes`: entero mayor a 0.
5. `PdfSplitService` lee el total de paginas y crea rangos equilibrados.
6. El backend devuelve un ZIP en memoria como descarga.

Ejemplo con `factura.pdf` de 10 paginas y `partes=3`:

```text
factura_dividido.zip
  factura_1-4.pdf
  factura_5-7.pdf
  factura_8-10.pdf
```

Validaciones:

- El archivo debe tener extension `.pdf` y ser un PDF valido.
- `partes` debe ser un entero mayor a 0.
- `partes` no puede ser mayor que el numero de paginas del PDF.

## Depurar PDF

1. El usuario abre `/depurar-pdf`.
2. Selecciona un archivo `.pdf`.
3. El frontend envia `POST /api/pdf/depurar` como `multipart/form-data`:
   - `file`: PDF de origen.
4. `PdfDeduplicationService` crea un PDF nuevo con las paginas 1, 3, 5, 7...
5. El backend devuelve el PDF en memoria como descarga.

Ejemplo con `factura.pdf` de 6 paginas:

```text
factura_noduplicados.pdf
  pagina 1
  pagina 3
  pagina 5
```

Validaciones:

- El archivo debe tener extension `.pdf` y ser un PDF valido.
- El PDF debe tener al menos una pagina.
- Los PDFs protegidos con contrasena no se depuran.

## Seguridad

El flujo moderno usa `facturas_app/utils/file_security.py` para:

- Sanitizar nombres de archivo.
- Validar extensiones con allowlist.
- Resolver rutas dentro de carpetas permitidas.
- Limpiar temporales solo por sufijo permitido.

Flask tambien aplica `MAX_CONTENT_LENGTH` segun `MAX_CONTENT_LENGTH_MB`.

## Diagnostico

```powershell
python verificar_servidor.py
```

El diagnostico revisa:

- Configuracion activa.
- Carpetas requeridas.
- Modulo legacy de facturas.
- Dependencias principales.
- App factory.
- Archivos UI activos.

## Pruebas

```powershell
python -m pytest
```

La suite cubre:

- Configuracion.
- Seguridad de archivos.
- Servicios de facturas.
- Parser y validador.
- Repositorio Excel.
- Extractor PDF.
- Servicio DSD.
- Rutas visuales actuales y rutas legacy retiradas.

## Logging

`facturas_app/logging_config.py` configura:

- Salida a consola.
- Archivo `logs/app.log`.
- Rotacion de 5 MB con 3 backups.

## Mantenimiento

- Agregar funcionalidad nueva en `facturas_app/api` y `facturas_app/services`.
- Mantener `facturas_app/legacy` solo para compatibilidad de facturas.
- No reactivar endpoints sin pantalla o flujo visible.
- Actualizar pruebas cuando cambien rutas, parser, Excel o DSD.
- Mantener el formato de `procesadas.xlsx`.

## Solucion Rapida de Problemas

Si el servidor no inicia:

```powershell
python verificar_servidor.py
```

Si FactuVal no procesa:

- Revisar `logs/app.log`.
- Confirmar que los archivos sean PDFs reales.
- Confirmar que no haya otro proceso en ejecucion.
- Confirmar permisos de escritura en carpetas de facturas.

Si DSD no genera archivo:

- Revisar que el Excel tenga columnas compatibles.
- Confirmar que `RUTA_SALIDA_DSD` exista o pueda crearse.
- Revisar `/api/dsd/estado` y `logs/app.log`.
