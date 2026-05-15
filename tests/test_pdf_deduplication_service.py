from __future__ import annotations

import pymupdf
import pytest

from facturas_app.services.pdf_deduplication_service import (
    PdfDeduplicationService,
    PdfDeduplicationValidationError,
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


def test_keep_odd_pages_returns_only_user_facing_odd_pages() -> None:
    result = PdfDeduplicationService().keep_odd_pages(
        _build_pdf(6),
        original_filename="factura duplicada.pdf",
    )

    assert result.pdf_filename == "factura_duplicada_noduplicados.pdf"
    assert result.total_pages == 6
    assert result.kept_pages == [1, 3, 5]
    assert _pdf_page_count(result.pdf_buffer.getvalue()) == 3


def test_keep_odd_pages_keeps_single_page_pdf() -> None:
    result = PdfDeduplicationService().keep_odd_pages(
        _build_pdf(1),
        original_filename="demo.pdf",
    )

    assert result.kept_pages == [1]
    assert _pdf_page_count(result.pdf_buffer.getvalue()) == 1


def test_keep_odd_pages_rejects_invalid_pdf() -> None:
    with pytest.raises(PdfDeduplicationValidationError, match="PDF valido"):
        PdfDeduplicationService().keep_odd_pages(
            b"not a pdf",
            original_filename="demo.pdf",
        )
