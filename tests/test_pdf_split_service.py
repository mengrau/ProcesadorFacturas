from __future__ import annotations

import zipfile
from io import BytesIO

import pymupdf
import pytest

from facturas_app.services.pdf_split_service import (
    PdfSplitService,
    PdfSplitValidationError,
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


def test_build_page_ranges_balances_remainder_first() -> None:
    ranges = PdfSplitService.build_page_ranges(total_pages=10, parts=3)

    assert [(item.start, item.end) for item in ranges] == [(1, 4), (5, 7), (8, 10)]


def test_split_pdf_to_zip_returns_named_parts() -> None:
    result = PdfSplitService().split_pdf_to_zip(
        _build_pdf(10),
        original_filename="factura original.pdf",
        parts=3,
    )

    assert result.zip_filename == "factura_original_dividido.zip"
    assert result.total_pages == 10

    with zipfile.ZipFile(result.zip_buffer) as zip_file:
        names = zip_file.namelist()
        assert names == [
            "factura_original_1-4.pdf",
            "factura_original_5-7.pdf",
            "factura_original_8-10.pdf",
        ]
        assert _pdf_page_count(zip_file.read(names[0])) == 4
        assert _pdf_page_count(zip_file.read(names[1])) == 3
        assert _pdf_page_count(zip_file.read(names[2])) == 3


def test_split_pdf_to_zip_rejects_too_many_parts() -> None:
    with pytest.raises(PdfSplitValidationError, match="mayor que el numero"):
        PdfSplitService().split_pdf_to_zip(
            _build_pdf(2),
            original_filename="demo.pdf",
            parts=3,
        )
