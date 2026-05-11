from __future__ import annotations

from pathlib import Path

from facturas_app.app import create_app
from facturas_app.config import Settings


def _write(path: Path, content: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_settings(tmp_path: Path) -> Settings:
    web_path = tmp_path / "web"
    facturas_code_path = tmp_path / "cod_facturas"
    _write(web_path / "index.html")
    _write(web_path / "styles.css")
    _write(web_path / "dsd.html")
    _write(web_path / "dsd.css")
    _write(facturas_code_path / "index.html")
    _write(facturas_code_path / "styles.css")

    return Settings(
        base_path=tmp_path,
        facturas_root=tmp_path / "Facturas",
        facturas_path=tmp_path / "Facturas" / "entrada",
        facturas_procesadas=tmp_path / "Facturas" / "salida",
        facturas_rechazados=tmp_path / "Facturas" / "rechazados",
        facturas_errores=tmp_path / "Facturas" / "errores",
        facturas_codigo_path=facturas_code_path,
        excel_salida=tmp_path / "Facturas" / "procesadas.xlsx",
        web_assets_path=web_path,
        ruta_salida_dsd=tmp_path / "salida_dsd",
        dsd_temp_path=tmp_path / "dsd_temp",
    )


def test_current_visual_routes_are_available(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/facturas").status_code == 200
    assert client.get("/dsd").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_removed_legacy_routes_are_not_exposed(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    assert client.get("/diferencias").status_code == 404
    assert client.get("/listas").status_code == 404
    assert client.get("/portafolios").status_code == 404
    assert client.post("/api/diferencias/iniciar").status_code == 404
    assert client.post("/api/listas/iniciar").status_code == 404
    assert client.post("/api/portafolios/iniciar").status_code == 404
