from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pdfplumber

INVALID_INVOICE_MESSAGE = "No fue posible procesarse - no parece una factura válida"

INVOICE_INDICATORS = [
    "POSTOBON",
    "GASEOSAS LUX",
    "LUX",
    "FACTURA ELECTRÓNICA DE VENTA",
    "FACTURA DE VENTA",
    "FACTURA",
    "CLIENTE:",
    "COD. CLIENTE",
]


class InvoiceValidator:
    """Validate whether a PDF/text looks like a processable invoice."""

    def __init__(
        self,
        *,
        debug_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._debug_callback = debug_callback

    def _debug(self, message: str) -> None:
        if self._debug_callback is not None:
            self._debug_callback(message)

    def validate_text(self, text: str) -> tuple[bool, str]:
        """Validate invoice text using the same indicators and regex as legacy."""
        complete_text = text.upper()

        indicators_found = 0
        indicators_found_list: list[str] = []
        for indicator in INVOICE_INDICATORS:
            if indicator in complete_text:
                indicators_found += 1
                indicators_found_list.append(indicator)

        self._debug(
            f"    DEBUG: Indicadores encontrados: {indicators_found}/8 - {indicators_found_list}"
        )
        self._debug(f"    DEBUG: Contiene POSTOBON: {'POSTOBON' in complete_text}")
        self._debug(f"    DEBUG: Contiene LUX: {'LUX' in complete_text}")

        if indicators_found < 2:
            return False, INVALID_INVOICE_MESSAGE

        if (
            "FACTURA" not in complete_text
            and "POSTOBON" not in complete_text
            and "LUX" not in complete_text
        ):
            return False, INVALID_INVOICE_MESSAGE

        if not re.search(
            r"FACTURA\s+(?:ELECTR[ÓO]NICA\s+DE\s+VENTA\s+)?No\.?\s*[A-Z0-9\-]+",
            complete_text,
            re.IGNORECASE,
        ):
            return False, INVALID_INVOICE_MESSAGE

        if not re.search(r"CLIENTE\s*:", complete_text, re.IGNORECASE):
            return False, INVALID_INVOICE_MESSAGE

        if not re.search(r"\b\d{2,8}\b", complete_text):
            return False, INVALID_INVOICE_MESSAGE

        if not re.search(
            r"\b(PZA|UNIDAD|SIX|Caja|BOL|UN|U|PZ|CAJA|BOTELLA|BOT)\b",
            complete_text,
            re.IGNORECASE,
        ):
            return False, INVALID_INVOICE_MESSAGE

        if not re.search(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?\b", complete_text):
            return False, INVALID_INVOICE_MESSAGE

        return True, "Archivo válido"

    def validate_pdf(self, pdf_path: str | Path) -> tuple[bool, str]:
        """Validate a PDF file by reading up to the first three pages."""
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                if len(pdf.pages) == 0:
                    return False, "El archivo PDF no tiene páginas válidas"

                complete_text = ""
                pages_to_review = min(3, len(pdf.pages))

                for page_index in range(pages_to_review):
                    page_text = pdf.pages[page_index].extract_text() or ""
                    complete_text += page_text + "\n"

                return self.validate_text(complete_text)

        except Exception as exc:
            return False, f"Error al leer el archivo: {str(exc)}"


def validate_invoice_pdf(
    pdf_path: str | Path,
    *,
    debug_callback: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    """Compatibility-friendly functional entrypoint for PDF invoice validation."""
    return InvoiceValidator(debug_callback=debug_callback).validate_pdf(pdf_path)
