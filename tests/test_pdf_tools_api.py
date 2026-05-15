from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pymupdf

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
    _write(web_path / "dividir-pdf.html")
    _write(web_path / "depurar-pdf.html")
    _write(web_path / "pdf.css")
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


def _build_pdf(page_count: int) -> bytes:
    document = pymupdf.open()
    try:
        for _ in range(page_count):
            document.new_page()
        return document.tobytes()
    finally:
        document.close()


def _pdf_page_count(pdf_bytes: bytes) -> int:
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return document.page_count
    finally:
        document.close()


def test_split_pdf_endpoint_returns_zip(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    response = client.post(
        "/api/pdf/dividir",
        data={
            "partes": "3",
            "file": (BytesIO(_build_pdf(10)), "demo.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert "demo_dividido.zip" in response.headers["Content-Disposition"]

    with zipfile.ZipFile(BytesIO(response.data)) as zip_file:
        assert zip_file.namelist() == [
            "demo_1-4.pdf",
            "demo_5-7.pdf",
            "demo_8-10.pdf",
        ]


def test_split_pdf_endpoint_validates_extension(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    response = client.post(
        "/api/pdf/dividir",
        data={
            "partes": "2",
            "file": (BytesIO(b"not a pdf"), "demo.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.json["error"] == "El archivo debe ser un PDF (.pdf)"


def test_split_pdf_endpoint_validates_parts(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    response = client.post(
        "/api/pdf/dividir",
        data={
            "partes": "0",
            "file": (BytesIO(_build_pdf(1)), "demo.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.json["error"] == "El numero de partes debe ser mayor a 0"


def test_deduplicate_pdf_endpoint_returns_pdf_with_odd_pages(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    response = client.post(
        "/api/pdf/depurar",
        data={
            "file": (BytesIO(_build_pdf(6)), "demo.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert "demo_noduplicados.pdf" in response.headers["Content-Disposition"]
    assert _pdf_page_count(response.data) == 3


def test_deduplicate_pdf_endpoint_validates_missing_file(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    response = client.post("/api/pdf/depurar", data={})

    assert response.status_code == 400
    assert response.json["error"] == "No se envio ningun archivo PDF"


def test_deduplicate_pdf_endpoint_validates_extension(tmp_path: Path) -> None:
    app = create_app(_build_settings(tmp_path))
    client = app.test_client()

    response = client.post(
        "/api/pdf/depurar",
        data={
            "file": (BytesIO(b"not a pdf"), "demo.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.json["error"] == "El archivo debe ser un PDF (.pdf)"
