from __future__ import annotations

from pathlib import Path

from facturas_app.services import pdf_text_extractor as extractor_module
from facturas_app.services.pdf_text_extractor import PdfTextExtractor


def test_write_timeout_pages_file_creates_expected_content(tmp_path: Path) -> None:
    extractor = PdfTextExtractor()
    output = tmp_path / "temp" / "paginas_timeout.txt"

    extractor.write_timeout_pages_file(
        str(output),
        [0, 2],
        total_pages=5,
        source_file="archivo.pdf",
    )

    content = output.read_text(encoding="utf-8")
    assert "file=archivo.pdf" in content
    assert "total_pages=5" in content
    assert "timeout_pages_1_based=1,3" in content


def test_safe_unlink_removes_existing_file(tmp_path: Path) -> None:
    extractor = PdfTextExtractor()
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")

    extractor.safe_unlink(str(target))

    assert not target.exists()


def test_extract_pdf_pages_with_retries_handles_timeouts_without_fallback(
    monkeypatch,
) -> None:
    extractor = PdfTextExtractor()

    class _FakePdf:
        def __init__(self) -> None:
            self.pages = [object(), object()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        extractor_module.pdfplumber,
        "open",
        lambda _path: _FakePdf(),
    )

    def fake_extract_pages_with_timeout(
        engine: str,
        pdf_path: str,
        page_indices: list[int],
        timeout_seconds: float,
        max_workers: int,
        *,
        source_file: str | None = None,
        page_map: dict[int, int] | None = None,
    ) -> dict[int, dict]:
        _ = (engine, pdf_path, timeout_seconds, max_workers, source_file, page_map)
        if page_indices == [0, 1]:
            return {
                0: {
                    "status": "OK",
                    "text": "texto-1",
                    "error": "",
                    "elapsed": 0.1,
                    "method": "pdfplumber",
                },
                1: {
                    "status": "TIMEOUT",
                    "text": "",
                    "error": "timeout",
                    "elapsed": 8.0,
                    "method": "pdfplumber",
                },
            }
        raise AssertionError(
            "No debería haber reintento cuando fallback está desactivado"
        )

    monkeypatch.setattr(
        extractor,
        "extract_pages_with_timeout",
        fake_extract_pages_with_timeout,
    )

    result = extractor.extract_pdf_pages_with_retries(
        "archivo.pdf",
        timeout_seconds=8,
        max_workers=2,
        temp_dir_root="temp",
        fallback_enabled=False,
        source_file="archivo.pdf",
    )

    assert result["total_pages"] == 2
    assert result["texts"][0] == "texto-1"
    assert result["status"][1] == "TIMEOUT"
    assert result["timeout_pages"] == [1]
    assert result["timeout_list_path"] is not None


def test_extract_pdf_pages_with_retries_marks_recovered_page_with_fallback(
    monkeypatch,
) -> None:
    extractor = PdfTextExtractor()

    class _FakePdf:
        def __init__(self) -> None:
            self.pages = [object(), object()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        extractor_module.pdfplumber,
        "open",
        lambda _path: _FakePdf(),
    )

    calls: list[list[int]] = []

    def fake_extract_pages_with_timeout(
        engine: str,
        pdf_path: str,
        page_indices: list[int],
        timeout_seconds: float,
        max_workers: int,
        *,
        source_file: str | None = None,
        page_map: dict[int, int] | None = None,
    ) -> dict[int, dict]:
        _ = (engine, pdf_path, timeout_seconds, max_workers, source_file, page_map)
        calls.append(page_indices)
        if page_indices == [0, 1]:
            return {
                0: {
                    "status": "OK",
                    "text": "texto-1",
                    "error": "",
                    "elapsed": 0.1,
                    "method": "pdfplumber",
                },
                1: {
                    "status": "TIMEOUT",
                    "text": "",
                    "error": "timeout",
                    "elapsed": 8.0,
                    "method": "pdfplumber",
                },
            }
        if page_indices == [1]:
            return {
                1: {
                    "status": "OK",
                    "text": "texto-recuperado",
                    "error": "",
                    "elapsed": 0.5,
                    "method": "pdfplumber",
                }
            }
        raise AssertionError("Llamada inesperada")

    monkeypatch.setattr(
        extractor,
        "extract_pages_with_timeout",
        fake_extract_pages_with_timeout,
    )

    result = extractor.extract_pdf_pages_with_retries(
        "archivo.pdf",
        timeout_seconds=8,
        max_workers=2,
        temp_dir_root="temp",
        fallback_enabled=True,
        source_file="archivo.pdf",
    )

    assert calls == [[0, 1], [1]]
    assert result["status"][1] == "RECUPERADA"
    assert result["texts"][1] == "texto-recuperado"
    assert result["method"][1] == "pdfplumber-retry"
