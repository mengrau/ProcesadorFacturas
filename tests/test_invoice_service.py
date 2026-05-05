from __future__ import annotations

from pathlib import Path

from facturas_app.config import Settings
from facturas_app.services.invoice_service import InvoiceService


class FakeLegacy:
    def __init__(self) -> None:
        self.calls: dict[str, object] = {}

    def _es_factura_valida(self, path: str) -> tuple[bool, str]:
        self.calls["validate"] = path
        return True, "Archivo válido"

    def mover_archivo_seguro(
        self,
        origen: str,
        destino: str,
        max_intentos: int = 5,
    ) -> bool:
        self.calls["move"] = (origen, destino, max_intentos)
        return True

    def procesar_facturas(self, mode: str):
        self.calls["process"] = mode
        return {
            "excel_path": "procesadas.xlsx",
            "total_seconds": 10.0,
            "facturas_procesadas": 2,
            "facturas_nuevas": 2,
            "facturas_duplicadas": 0,
        }


class FakeOptimizedLegacy:
    def __init__(self) -> None:
        self.validate_calls = 0
        self.saved_rows = 0
        self.saved_mode = ""

    def _es_factura_valida(self, path: str) -> tuple[bool, str]:
        self.validate_calls += 1
        return True, "Archivo válido"

    def mover_archivo_seguro(
        self,
        origen: str,
        destino: str,
        max_intentos: int = 5,
    ) -> bool:
        return True

    def cargar_facturas_existentes(self, excel_path: str) -> set[str]:
        return set()

    def extraer_datos_factura(
        self,
        pdf_path: str,
        facturas_vistas: set,
        paginas_por_bloque: int = 100,
        modo: str = "acumular",
    ) -> list[dict[str, str]]:
        return [
            {
                "id": "abc123",
                "numero_factura": "FV-001",
                "nit_cliente": "900123456",
                "cod_cliente": "1001",
                "nombre_cliente": "Cliente Test",
                "fecha_generacion": "01/01/2025",
                "fecha_expedicion": "01/01/2025",
                "referencia": "REF-01",
                "productos": "Producto Test",
                "umv": "UNIDAD",
                "unidades": "1",
                "precio_base_unitario": "1000",
                "iva": "19.00",
                "total": "1190",
                "estado": "OK",
            }
        ]

    def guardar_en_excel(self, datos: list[dict], modo: str = "acumular") -> str:
        self.saved_rows = len(datos)
        self.saved_mode = modo
        return "procesadas.xlsx"


class FakeValidatorService:
    def __init__(self) -> None:
        self.calls = 0

    def validate_pdf(self, path: Path) -> tuple[bool, str]:
        self.calls += 1
        return True, "Archivo válido"


class FakePdfTextExtractorService:
    def __init__(self) -> None:
        self.calls = 0

    def extract_pdf_pages_with_retries(self, pdf_path: str, **kwargs):
        self.calls += 1
        return {
            "total_pages": 1,
            "texts": {0: """
                FACTURA ELECTRÓNICA DE VENTA No. FV-001
                CLIENTE: 900123456
                Cliente Test
                COD. CLIENTE 1001
                FECHA GENERACIÓN 01/01/2025 10:00:00
                FECHA DE EXPEDICIÓN 01/01/2025
                123456 Producto Test UNIDAD 1 1000 1000 19 1190
                """},
        }


class FakeParserService:
    def __init__(self) -> None:
        self.calls = 0

    def parse_pages(self, page_texts, **kwargs) -> list[dict[str, str]]:
        self.calls += 1
        return [
            {
                "id": "abc123",
                "numero_factura": "FV-001",
                "nit_cliente": "900123456",
                "cod_cliente": "1001",
                "nombre_cliente": "Cliente Test",
                "fecha_generacion": "01/01/2025",
                "fecha_expedicion": "01/01/2025",
                "referencia": "REF-01",
                "productos": "Producto Test",
                "umv": "UNIDAD",
                "unidades": "1",
                "precio_base_unitario": "1000",
                "iva": "19.00",
                "total": "1190",
                "estado": "OK",
            }
        ]


class FakeExcelRepositoryService:
    def __init__(self) -> None:
        self.saved_rows = 0
        self.saved_mode = ""
        self.loaded = 0

    def load_existing_invoice_numbers(self) -> set[str]:
        self.loaded += 1
        return set()

    def save(self, datos: list[dict], mode: str = "acumular") -> str:
        self.saved_rows = len(datos)
        self.saved_mode = mode
        return "procesadas.xlsx"


class FailingExcelRepositoryService:
    def load_existing_invoice_numbers(self) -> set[str]:
        raise RuntimeError("fallo controlado para probar fallback legacy")

    def save(self, datos: list[dict], mode: str = "acumular") -> str:
        raise RuntimeError("no debería guardar en este escenario")


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        base_path=tmp_path,
        facturas_root=tmp_path / "Facturas",
        facturas_path=tmp_path / "Facturas" / "entrada",
        facturas_procesadas=tmp_path / "Facturas" / "salida",
        facturas_rechazados=tmp_path / "Facturas" / "rechazados",
        facturas_errores=tmp_path / "Facturas" / "errores",
        facturas_codigo_path=tmp_path / "Facturas" / "cod_facturas",
        excel_salida=tmp_path / "Facturas" / "procesadas.xlsx",
        web_assets_path=tmp_path / "Web",
        carpeta_base_dif=tmp_path / "dif",
        ruta_base_jerarquia=tmp_path / "base.xlsx",
        ruta_salida_dsd=tmp_path / "dsd",
        dsd_temp_path=tmp_path / "dsd_temp",
    )


def test_invoice_service_calls_legacy_module(tmp_path: Path) -> None:
    fake = FakeLegacy()
    settings = _build_settings(tmp_path)
    settings.facturas_path.mkdir(parents=True, exist_ok=True)
    (settings.facturas_path / "factura_fallback.pdf").write_bytes(b"%PDF-1.4 test")
    service = InvoiceService(
        settings=settings,
        legacy_module=fake,
        validator=FakeValidatorService(),
        excel_repository=FailingExcelRepositoryService(),
    )
    source = tmp_path / "a.pdf"
    destination = tmp_path / "b.pdf"
    source.write_bytes(b"%PDF-1.4 test")

    valid, reason = service.validate_invoice_pdf(source)
    moved = service.move_file(source, destination)
    result = service.process_invoices("acumular")

    assert valid is True
    assert reason == "Archivo válido"
    assert moved is True
    assert result["facturas_procesadas"] == 2
    assert fake.calls["process"] == "acumular"


def test_invoice_service_validates_mode(tmp_path: Path) -> None:
    service = InvoiceService(
        settings=_build_settings(tmp_path), legacy_module=FakeLegacy()
    )

    try:
        service.process_invoices("invalido")
    except ValueError as exc:
        assert "acumular" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid mode")


def test_validate_invoice_pdf_uses_cache(tmp_path: Path) -> None:
    validator = FakeValidatorService()
    service = InvoiceService(
        settings=_build_settings(tmp_path),
        legacy_module=FakeOptimizedLegacy(),
        validator=validator,
    )

    pdf_path = tmp_path / "validacion.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    first = service.validate_invoice_pdf(pdf_path)
    second = service.validate_invoice_pdf(pdf_path)

    assert first == (True, "Archivo válido")
    assert second == (True, "Archivo válido")
    assert validator.calls == 1


def test_invoice_service_optimized_pipeline_runs(tmp_path: Path) -> None:
    fake = FakeOptimizedLegacy()
    validator = FakeValidatorService()
    extractor = FakePdfTextExtractorService()
    parser = FakeParserService()
    excel_repository = FakeExcelRepositoryService()
    settings = _build_settings(tmp_path)
    settings.facturas_path.mkdir(parents=True, exist_ok=True)
    (settings.facturas_path / "factura_1.pdf").write_bytes(b"%PDF-1.4 test")

    service = InvoiceService(
        settings=settings,
        legacy_module=fake,
        validator=validator,
        pdf_text_extractor=extractor,
        parser=parser,
        excel_repository=excel_repository,
    )
    result = service.process_invoices("separado")

    assert result["facturas_procesadas"] == 1
    assert result["excel_path"] == "procesadas.xlsx"
    assert validator.calls == 1
    assert extractor.calls == 1
    assert parser.calls == 1
    assert excel_repository.saved_rows == 1
    assert excel_repository.saved_mode == "separado"
