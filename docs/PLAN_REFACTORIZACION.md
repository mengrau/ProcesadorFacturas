# Plan recomendado de refactorización

Este documento propone cómo ordenar el proyecto sin romper la operación actual. La idea es migrar por etapas desde legacy hacia módulos pequeños, testeables y fáciles de entender.

## 1. Objetivo

Reducir la dependencia de archivos gigantes legacy y separar responsabilidades.

Hoy, gran parte de la lógica vive en:

```text
facturas_app/legacy/invoice_legacy.py
facturas_app/legacy/server_legacy.py
```

El objetivo es que el flujo de facturas quede así:

```text
facturas_app/
  services/
    invoice_service.py
    pdf_text_extractor.py
    invoice_parser.py
    invoice_excel_repository.py
    invoice_file_manager.py
  models/
    invoice.py
```

Y que `legacy/` quede solo como compatibilidad temporal.

## 2. Principio más importante

No conviene mover todo a `InvoiceService`.

`InvoiceService` debe coordinar, no hacer todo.

Responsabilidad ideal de `InvoiceService`:

```text
Buscar PDFs
  ↓
Validar
  ↓
Extraer texto
  ↓
Parsear registros
  ↓
Guardar Excel
  ↓
Mover archivos
  ↓
Devolver resumen
```

Pero cada paso debería vivir en una clase/módulo separado.

## 3. Estado actual vs estado ideal

### Estado actual

```text
InvoiceService
  ├─ coordina flujo
  ├─ maneja paralelismo
  ├─ filtra duplicados
  └─ llama funciones de invoice_legacy

invoice_legacy
  ├─ valida PDFs
  ├─ extrae texto de PDFs
  ├─ parsea datos
  ├─ carga Excel existente
  ├─ recupera Excel corrupto
  ├─ guarda Excel
  └─ mueve archivos
```

### Estado ideal

```text
InvoiceService
  ├─ PdfInvoiceValidator
  ├─ PdfTextExtractor
  ├─ InvoiceParser
  ├─ InvoiceExcelRepository
  └─ InvoiceFileManager
```

## 4. Módulos propuestos

### `facturas_app/models/invoice.py`

Modelos de dominio.

Propuesta:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class InvoiceLine:
    reference: str
    product: str
    umv: str
    units: str
    base_price: str
    iva: str
    total: str
    status: str = "OK"

@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    id: str
    invoice_number: str
    customer_nit: str
    customer_code: str
    customer_name: str
    generation_date: str
    expedition_date: str
    line: InvoiceLine
```

Nota: al principio se puede seguir devolviendo diccionarios para no romper Excel ni tests, y luego migrar a dataclasses.

### `facturas_app/services/pdf_text_extractor.py`

Responsabilidad:

- Abrir PDF.
- Extraer texto por página.
- Manejar timeout.
- Reintentar páginas lentas.
- Devolver textos por página.

Funciones legacy que migrarían aquí:

```text
_extract_page_text_pdfplumber
_page_text_worker
_extract_pages_with_timeout
_safe_unlink
_write_timeout_pages_file
```

Salida ideal:

```python
class PdfTextExtractor:
    def extract_pages(self, pdf_path: Path) -> PdfTextExtractionResult:
        ...
```

### `facturas_app/services/invoice_parser.py`

Responsabilidad:

- Recibir texto de páginas.
- Detectar facturas.
- Extraer campos.
- Extraer productos.
- Devolver registros normalizados.

Funciones legacy que migrarían aquí:

```text
normalizar_numero
formatear_numero
_extraer_numero_factura
_normalizar_nombre_cliente
_extraer_cliente
_extraer_fecha_generacion
_extraer_fecha_expedicion
_limpiar_producto
_extraer_productos
extraer_datos_factura parcialmente
```

Salida ideal:

```python
class InvoiceParser:
    def parse_pages(self, pages: list[str], mode: str, seen_invoices: set[str]) -> list[dict]:
        ...
```

### `facturas_app/services/invoice_validator.py`

Responsabilidad:

- Determinar si un PDF parece una factura válida.
- Idealmente usar `PdfTextExtractor` para revisar primeras páginas.

Función legacy que migraría aquí:

```text
_es_factura_valida
```

Salida ideal:

```python
class InvoiceValidator:
    def validate(self, pdf_path: Path) -> tuple[bool, str]:
        ...
```

### `facturas_app/services/invoice_excel_repository.py`

Responsabilidad:

- Leer facturas ya procesadas.
- Recuperar datos de Excel existente.
- Guardar Excel final.
- Formatear columnas.
- Manejar backup si el Excel está corrupto.

Funciones legacy que migrarían aquí:

```text
cargar_facturas_existentes
_recuperar_datos_excel
guardar_en_excel
```

Salida ideal:

```python
class InvoiceExcelRepository:
    def load_existing_invoice_numbers(self) -> set[str]:
        ...

    def save(self, records: list[dict], mode: str) -> Path:
        ...
```

### `facturas_app/services/invoice_file_manager.py`

Responsabilidad:

- Mover PDFs con reintentos.
- Enviar archivos a carpetas correctas:
  - procesadas,
  - rechazados,
  - errores.

Función legacy que migraría aquí:

```text
mover_archivo_seguro
```

Salida ideal:

```python
class InvoiceFileManager:
    def move_to_processed(self, path: Path) -> bool:
        ...

    def move_to_rejected(self, path: Path) -> bool:
        ...

    def move_to_errors(self, path: Path) -> bool:
        ...
```

## 5. Orden recomendado de migración

### Fase 0: no cambiar comportamiento

Objetivo: documentar y agregar pruebas antes de tocar lógica.

Tareas:

- Mantener esta documentación actualizada.
- Agregar pruebas de parsing con textos de ejemplo.
- Agregar pruebas de guardado Excel con datos falsos.
- Agregar pruebas de validación con PDFs o mocks.

### Fase 1: mover funciones puras de parsing

Esta es la fase más segura.

Mover primero funciones que no dependen de disco, Flask, Excel ni multiprocessing:

```text
normalizar_numero
formatear_numero
_extraer_numero_factura
_normalizar_nombre_cliente
_extraer_cliente
_extraer_fecha_generacion
_extraer_fecha_expedicion
_limpiar_producto
_extraer_productos
```

Nuevo archivo:

```text
facturas_app/services/invoice_parser.py
```

Estrategia:

1. Copiar funciones.
2. Crear clase `InvoiceParser` o funciones públicas claras.
3. Agregar tests.
4. Cambiar legacy para importar esas funciones, o cambiar `InvoiceService` gradualmente.

Ventaja: bajo riesgo.

### Fase 2: extraer repositorio Excel

Nuevo archivo:

```text
facturas_app/services/invoice_excel_repository.py
```

Mover:

```text
cargar_facturas_existentes
_recuperar_datos_excel
guardar_en_excel
```

Estrategia:

1. Crear repositorio usando `Settings`.
2. Mantener mismo formato de columnas.
3. Probar modo `acumular` y `separado`.
4. Asegurar deduplicación igual que antes.

Riesgo: medio, porque toca el Excel final.

### Fase 3: extraer validador de facturas

Nuevo archivo:

```text
facturas_app/services/invoice_validator.py
```

Mover:

```text
_es_factura_valida
```

Estrategia:

1. Mantener los mismos indicadores de factura.
2. Probar casos válidos e inválidos.
3. Reutilizar extractor de texto cuando exista.

Riesgo: medio, porque puede rechazar/aceptar archivos.

### Fase 4: extraer `PdfTextExtractor`

Nuevo archivo:

```text
facturas_app/services/pdf_text_extractor.py
```

Mover lógica de:

```text
_extract_page_text_pdfplumber
_page_text_worker
_extract_pages_with_timeout
_write_timeout_pages_file
```

Estrategia:

1. Crear una clase aislada.
2. Mantener configuración desde `Settings`.
3. Probar con mocks o PDFs pequeños.
4. Revisar bien comportamiento en Windows con `multiprocessing`.

Riesgo: alto, porque involucra procesos, timeouts y PDFs problemáticos.

### Fase 5: reemplazar llamadas legacy en `InvoiceService`

Cuando ya existan módulos nuevos, cambiar:

```python
self._legacy.extraer_datos_factura(...)
self._legacy.guardar_en_excel(...)
self._legacy._es_factura_valida(...)
self._legacy.mover_archivo_seguro(...)
```

por servicios nuevos:

```python
self.validator.validate(...)
self.parser.parse_pages(...)
self.excel_repository.save(...)
self.file_manager.move_to_processed(...)
```

Riesgo: medio/alto, pero ya estaría cubierto por pruebas.

### Fase 6: limpiar legacy

Cuando todo funcione:

- dejar `legacy/invoice_legacy.py` como compatibilidad,
- o convertirlo en wrapper que llame a servicios nuevos,
- o eliminar funciones duplicadas si ya no se usan.

## 6. Reglas para no romper producción

1. No borrar legacy al inicio.
2. Mover una responsabilidad a la vez.
3. Agregar pruebas antes de cambiar comportamiento.
4. Mantener endpoints existentes:

```text
/upload
/resultado
/descargar_excel
/facturas
```

5. Mantener formato de `procesadas.xlsx`.
6. Mantener modos `acumular` y `separado`.
7. Mantener carpetas:

```text
entrada
salida
rechazados
errores
temp
```

8. Después de cada fase ejecutar:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 7. Primer paso concreto recomendado

El primer paso de refactorización debería ser:

> Crear `facturas_app/services/invoice_parser.py` y mover funciones puras de parsing desde `legacy/invoice_legacy.py`.

Por qué:

- No toca Flask.
- No toca Excel.
- No toca archivos.
- No toca multiprocessing.
- Es fácil de probar con strings.

Funciones candidatas:

```text
normalizar_numero
formatear_numero
_extraer_numero_factura
_normalizar_nombre_cliente
_extraer_cliente
_extraer_fecha_generacion
_extraer_fecha_expedicion
_limpiar_producto
_extraer_productos
```

Pruebas sugeridas:

```text
tests/test_invoice_parser.py
```

Casos mínimos:

- extrae número de factura de texto realista,
- extrae cliente/NIT/código,
- extrae fechas,
- extrae una línea de producto,
- normaliza números con coma/punto,
- ignora líneas que no son productos.

## 8. Segundo paso recomendado

Después del parser:

> Crear `InvoiceExcelRepository`.

Esto ayudaría mucho porque el guardado Excel es una responsabilidad grande que hoy está oculta en legacy.

## 9. Resultado esperado al final

Al terminar la refactorización, leer el proyecto debería ser mucho más sencillo:

```text
api/facturas.py
  Recibe HTTP y responde JSON.

services/invoice_service.py
  Coordina el caso de uso completo.

services/pdf_text_extractor.py
  Sabe leer PDFs.

services/invoice_parser.py
  Sabe convertir texto en datos.

services/invoice_excel_repository.py
  Sabe leer/escribir Excel.

services/invoice_file_manager.py
  Sabe mover archivos.

legacy/invoice_legacy.py
  Solo compatibilidad o respaldo temporal.
```
