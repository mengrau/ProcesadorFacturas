from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd

from facturas_app.config import Settings
from facturas_app.services.dsd_service import DsdService, normalize_text


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        base_path=tmp_path,
        facturas_root=tmp_path / "Facturas",
        facturas_path=tmp_path / "Facturas" / "entrada",
        facturas_procesadas=tmp_path / "Facturas" / "salida",
        facturas_rechazados=tmp_path / "Facturas" / "rechazados",
        facturas_errores=tmp_path / "Facturas" / "errores",
        facturas_codigo_path=tmp_path / "cod_facturas",
        excel_salida=tmp_path / "Facturas" / "procesadas.xlsx",
        web_assets_path=tmp_path / "web",
        ruta_salida_dsd=tmp_path / "salida_dsd",
        dsd_temp_path=tmp_path / "dsd_temp",
    )


def test_normalize_text_removes_accents_and_lowercases() -> None:
    assert normalize_text("  Cliente J1  ") == "cliente j1"
    assert normalize_text("Generacion") == "generacion"


def test_dsd_service_generates_solicitantes_workbook(tmp_path: Path) -> None:
    source_path = tmp_path / "Base_Jerarquia.xlsx"
    df = pd.DataFrame(
        {
            "Cliente J1": ["100", "100", "200"],
            "Nombre": ["Cliente Uno", "Cliente Uno", "Cliente Dos"],
            "Nombre 2": ["Sucursal A", "Sucursal A", "Sucursal B"],
            "Cliente J3": ["300", "301", "400"],
        }
    )
    df.to_excel(source_path, index=False)

    updates: list[dict] = []
    result = DsdService(_build_settings(tmp_path)).process(
        source_path,
        progress_callback=updates.append,
    )

    output_path = Path(result["archivo_generado"])
    assert output_path.exists()
    assert result["total_filas"] == 3
    assert any(update.get("progreso") == 90 for update in updates)

    workbook = openpyxl.load_workbook(output_path, data_only=True)
    worksheet = workbook.active
    try:
        assert worksheet["A1"].value == "Cliente_J1"
        assert worksheet["B1"].value == "Nombre_Solicitante"
        assert worksheet["D2"].value == "300"
        assert worksheet["D3"].value == "301"
        assert worksheet["G1"].value == "Cliente_J1"
        assert worksheet["J2"].value == "400"
    finally:
        workbook.close()
