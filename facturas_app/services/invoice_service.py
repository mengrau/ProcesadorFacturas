from __future__ import annotations

import logging
from pathlib import Path
from types import ModuleType

from facturas_app.config import Settings, get_settings
from facturas_app.legacy.bridge import get_invoice_legacy
from facturas_app.models.dto import ProcessingSummary

logger = logging.getLogger(__name__)


class InvoiceService:
    """Facade around the legacy invoice processor with typed interfaces."""

    def __init__(
        self,
        settings: Settings | None = None,
        legacy_module: ModuleType | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._legacy = legacy_module or get_invoice_legacy()

    def validate_invoice_pdf(self, pdf_path: Path) -> tuple[bool, str]:
        """Validate a PDF file using existing business rules."""
        return self._legacy._es_factura_valida(str(pdf_path))

    def move_file(
        self,
        source: Path,
        destination: Path,
        *,
        max_attempts: int = 5,
    ) -> bool:
        """Move a file using the resilient legacy mover."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        return bool(
            self._legacy.mover_archivo_seguro(
                str(source),
                str(destination),
                max_intentos=max_attempts,
            )
        )

    def process_invoices(self, mode: str = "acumular") -> ProcessingSummary:
        """Process invoices preserving legacy behavior and output format."""
        if mode not in {"acumular", "separado"}:
            raise ValueError("Mode must be either 'acumular' or 'separado'")

        logger.info("Starting invoice processing. mode=%s", mode)
        result = self._legacy.procesar_facturas(mode)
        if result is None:
            raise RuntimeError("Invoice processing returned no result")

        logger.info(
            "Invoice processing finished. processed=%s",
            result.get("facturas_procesadas", 0),
        )
        return result

    def get_excel_output_path(self) -> Path:
        """Return configured output Excel path."""
        return self.settings.excel_salida
