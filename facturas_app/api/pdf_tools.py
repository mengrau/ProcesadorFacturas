from __future__ import annotations

import logging

from flask import Blueprint, send_file, request

from facturas_app.services.pdf_deduplication_service import (
    PdfDeduplicationService,
    PdfDeduplicationValidationError,
)
from facturas_app.services.pdf_split_service import (
    PdfSplitService,
    PdfSplitValidationError,
)
from facturas_app.utils.file_security import is_allowed_extension
from facturas_app.utils.responses import error_response

logger = logging.getLogger(__name__)

pdf_tools_bp = Blueprint("pdf_tools", __name__)


def _parse_parts(raw_value: str | None) -> int:
    try:
        return int(raw_value or "")
    except (TypeError, ValueError) as exc:
        raise PdfSplitValidationError(
            "El numero de partes debe ser un entero valido"
        ) from exc


@pdf_tools_bp.route("/api/pdf/dividir", methods=["POST"])
def split_pdf():
    """Split one PDF into balanced parts and return a ZIP download."""
    if "file" not in request.files:
        return error_response("No se envio ningun archivo PDF", status=400)

    file_storage = request.files["file"]
    original_name = file_storage.filename or ""
    if not original_name:
        return error_response("No se selecciono ningun archivo", status=400)

    if not is_allowed_extension(original_name, (".pdf",)):
        return error_response("El archivo debe ser un PDF (.pdf)", status=400)

    try:
        parts = _parse_parts(request.form.get("partes"))
        pdf_bytes = file_storage.read()
        result = PdfSplitService().split_pdf_to_zip(
            pdf_bytes,
            original_filename=original_name,
            parts=parts,
        )
    except PdfSplitValidationError as exc:
        return error_response(str(exc), status=400)
    except Exception as exc:
        logger.exception("PDF split failed")
        return error_response(
            "No se pudo dividir el PDF",
            status=500,
            details={"error": str(exc)},
        )

    return send_file(
        result.zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=result.zip_filename,
        max_age=0,
    )


@pdf_tools_bp.route("/api/pdf/depurar", methods=["POST"])
def deduplicate_pdf():
    """Return a PDF copy that keeps only pages 1, 3, 5, and so on."""
    if "file" not in request.files:
        return error_response("No se envio ningun archivo PDF", status=400)

    file_storage = request.files["file"]
    original_name = file_storage.filename or ""
    if not original_name:
        return error_response("No se selecciono ningun archivo", status=400)

    if not is_allowed_extension(original_name, (".pdf",)):
        return error_response("El archivo debe ser un PDF (.pdf)", status=400)

    try:
        pdf_bytes = file_storage.read()
        result = PdfDeduplicationService().keep_odd_pages(
            pdf_bytes,
            original_filename=original_name,
        )
    except PdfDeduplicationValidationError as exc:
        return error_response(str(exc), status=400)
    except Exception as exc:
        logger.exception("PDF deduplication failed")
        return error_response(
            "No se pudo depurar el PDF",
            status=500,
            details={"error": str(exc)},
        )

    return send_file(
        result.pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=result.pdf_filename,
        max_age=0,
    )
