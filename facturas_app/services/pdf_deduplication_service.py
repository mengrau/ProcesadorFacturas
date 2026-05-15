from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pymupdf

from facturas_app.utils.file_security import sanitize_filename

logger = logging.getLogger(__name__)


class PdfDeduplicationValidationError(ValueError):
    """Raised when a PDF cannot be deduplicated."""


@dataclass(frozen=True, slots=True)
class PdfDeduplicationResult:
    """In-memory PDF payload and metadata for an odd-page cleanup."""

    pdf_buffer: BytesIO
    pdf_filename: str
    total_pages: int
    kept_pages: list[int]


class PdfDeduplicationService:
    """Create a copy of a PDF keeping only user-facing odd pages."""

    def keep_odd_pages(
        self,
        pdf_bytes: bytes,
        *,
        original_filename: str,
    ) -> PdfDeduplicationResult:
        if not pdf_bytes:
            raise PdfDeduplicationValidationError("El archivo PDF esta vacio")

        safe_name = sanitize_filename(original_filename)
        original_stem = Path(safe_name).stem or "documento"
        pdf_filename = f"{original_stem}_noduplicados.pdf"

        try:
            source_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfDeduplicationValidationError(
                "El archivo no es un PDF valido"
            ) from exc

        try:
            if source_doc.needs_pass:
                raise PdfDeduplicationValidationError(
                    "El PDF esta protegido con contrasena y no se puede depurar"
                )

            total_pages = source_doc.page_count
            if total_pages <= 0:
                raise PdfDeduplicationValidationError("El PDF no contiene paginas")

            kept_page_indexes = list(range(0, total_pages, 2))
            output_pdf = pymupdf.open()
            try:
                for page_index in kept_page_indexes:
                    output_pdf.insert_pdf(
                        source_doc,
                        from_page=page_index,
                        to_page=page_index,
                    )
                output_bytes = output_pdf.tobytes(garbage=4, deflate=True)
            finally:
                output_pdf.close()

            pdf_buffer = BytesIO(output_bytes)
            pdf_buffer.seek(0)
            kept_pages = [page_index + 1 for page_index in kept_page_indexes]

            logger.info(
                "PDF deduplication completed. file=%s pages=%s kept_pages=%s output=%s",
                safe_name,
                total_pages,
                len(kept_pages),
                pdf_filename,
            )
            return PdfDeduplicationResult(
                pdf_buffer=pdf_buffer,
                pdf_filename=pdf_filename,
                total_pages=total_pages,
                kept_pages=kept_pages,
            )
        finally:
            source_doc.close()
