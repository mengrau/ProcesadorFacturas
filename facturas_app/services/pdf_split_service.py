from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pymupdf

from facturas_app.utils.file_security import sanitize_filename

logger = logging.getLogger(__name__)


class PdfSplitValidationError(ValueError):
    """Raised when the requested split cannot be performed."""


@dataclass(frozen=True, slots=True)
class PdfPageRange:
    """Inclusive one-based page range for one output PDF."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PdfSplitResult:
    """In-memory ZIP payload and metadata for a split PDF."""

    zip_buffer: BytesIO
    zip_filename: str
    total_pages: int
    ranges: list[PdfPageRange]


class PdfSplitService:
    """Split a PDF into balanced parts and package them as a ZIP."""

    @staticmethod
    def build_page_ranges(total_pages: int, parts: int) -> list[PdfPageRange]:
        if parts <= 0:
            raise PdfSplitValidationError("El numero de partes debe ser mayor a 0")
        if total_pages <= 0:
            raise PdfSplitValidationError("El PDF no contiene paginas")
        if parts > total_pages:
            raise PdfSplitValidationError(
                "El numero de partes no puede ser mayor que el numero de paginas"
            )

        base_size, remainder = divmod(total_pages, parts)
        ranges: list[PdfPageRange] = []
        start = 1

        for index in range(parts):
            length = base_size + (1 if index < remainder else 0)
            end = start + length - 1
            ranges.append(PdfPageRange(start=start, end=end))
            start = end + 1

        return ranges

    def split_pdf_to_zip(
        self,
        pdf_bytes: bytes,
        *,
        original_filename: str,
        parts: int,
    ) -> PdfSplitResult:
        if parts <= 0:
            raise PdfSplitValidationError("El numero de partes debe ser mayor a 0")
        if not pdf_bytes:
            raise PdfSplitValidationError("El archivo PDF esta vacio")

        safe_name = sanitize_filename(original_filename)
        original_stem = Path(safe_name).stem or "documento"
        zip_filename = f"{original_stem}_dividido.zip"

        try:
            source_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfSplitValidationError("El archivo no es un PDF valido") from exc

        try:
            if source_doc.needs_pass:
                raise PdfSplitValidationError(
                    "El PDF esta protegido con contrasena y no se puede dividir"
                )

            total_pages = source_doc.page_count
            ranges = self.build_page_ranges(total_pages, parts)

            zip_buffer = BytesIO()
            with zipfile.ZipFile(
                zip_buffer,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
            ) as zip_file:
                for page_range in ranges:
                    output_pdf = pymupdf.open()
                    try:
                        output_pdf.insert_pdf(
                            source_doc,
                            from_page=page_range.start - 1,
                            to_page=page_range.end - 1,
                        )
                        output_bytes = output_pdf.tobytes(
                            garbage=4,
                            deflate=True,
                        )
                    finally:
                        output_pdf.close()

                    part_filename = (
                        f"{original_stem}_{page_range.start}-{page_range.end}.pdf"
                    )
                    zip_file.writestr(part_filename, output_bytes)

            zip_buffer.seek(0)
            logger.info(
                "PDF split completed. file=%s pages=%s parts=%s zip=%s",
                safe_name,
                total_pages,
                parts,
                zip_filename,
            )
            return PdfSplitResult(
                zip_buffer=zip_buffer,
                zip_filename=zip_filename,
                total_pages=total_pages,
                ranges=ranges,
            )
        finally:
            source_doc.close()
