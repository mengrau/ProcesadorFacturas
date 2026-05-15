# Mapa del Proyecto

El proyecto es una aplicacion Flask local con experiencias visibles para:

- `/facturas`: procesamiento de facturas PDF.
- `/dsd`: consulta de pedidos DSD.
- `/dividir-pdf`: division de PDFs.
- `/depurar-pdf`: depuracion de PDFs duplicados por paginas impares.

Los flujos historicos de listas, diferencias y portafolios fueron retirados de
la app modular porque ya no aparecen en el menu ni cuentan con interfaz activa.

## Entradas

| Archivo | Uso |
|---|---|
| `server.py` | Entrada principal del servidor |
| `iniciar_servidor.bat` | Arranque Windows con diagnostico previo |
| `verificar_servidor.py` | Wrapper hacia `scripts/diagnostico.py` |
| `scripts/run_server.py` | Entrada alternativa |

## Capas

```text
facturas_app/
  app.py
  config.py
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
    pdf_deduplication_service.py
  utils/
    file_security.py
    responses.py
  models/
    dto.py
  legacy/
    invoice_legacy.py
    bridge.py
```

## API

| Archivo | Responsabilidad |
|---|---|
| `api/pages.py` | Sirve menu, CSS general y pantalla DSD |
| `api/facturas.py` | Sirve FactuVal y maneja upload/resultado/descarga |
| `api/dsd.py` | Maneja upload, inicio, estado y descarga DSD |
| `api/health.py` | Expone `/api/health` |

## Servicios

| Servicio | Responsabilidad |
|---|---|
| `InvoiceService` | Orquesta el flujo completo de facturas |
| `InvoiceValidator` | Determina si un PDF parece factura valida |
| `PdfTextExtractor` | Extrae texto por pagina con timeout y retry |
| `InvoiceParser` | Convierte texto en registros de factura |
| `InvoiceExcelRepository` | Lee y guarda `procesadas.xlsx` |
| `InvoiceFileManager` | Mueve archivos con reintentos |
| `DsdService` | Genera `Solicitantes_SAP.xlsx` desde Base Jerarquia |

## Frontend

| Carpeta | Contenido |
|---|---|
| `web/` | Menu principal y pantalla DSD |
| `cod_facturas/` | Pantalla FactuVal |

## Legacy

`facturas_app/legacy/invoice_legacy.py` se conserva para compatibilidad con
imports antiguos de facturas. Ya no existe un servidor legacy registrado en
Flask.

## Rutas Activas

| Ruta | Uso |
|---|---|
| `/` | Menu principal |
| `/facturas` | FactuVal |
| `/dsd` | Consulta DSD |
| `/dividir-pdf` | Dividir PDF |
| `/depurar-pdf` | Depurar PDF |
| `/api/health` | Healthcheck |
| `/upload` | Upload de PDFs |
| `/resultado` | Estado de facturas |
| `/descargar_excel` | Descarga de facturas |
| `/api/dsd/*` | API DSD |
| `/api/pdf/dividir` | API dividir PDF |
| `/api/pdf/depurar` | API depurar PDF |

## Rutas Retiradas

```text
/diferencias
/listas
/portafolios
/api/diferencias/*
/api/listas/*
/api/portafolios/*
```
