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
    service = InvoiceService(settings=_build_settings(tmp_path), legacy_module=fake)

    valid, reason = service.validate_invoice_pdf(tmp_path / "a.pdf")
    moved = service.move_file(tmp_path / "a.pdf", tmp_path / "b.pdf")
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
