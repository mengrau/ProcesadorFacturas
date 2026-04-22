from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, request, send_from_directory

from facturas_app.config import Settings, get_settings
from facturas_app.services.invoice_service import InvoiceService
from facturas_app.utils.file_security import (
    clear_directory_files,
    is_allowed_extension,
    resolve_safe_path,
    sanitize_filename,
)
from facturas_app.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

facturas_bp = Blueprint("facturas", __name__)
_state_lock = threading.Lock()
_processing_state: dict[str, Any] = {"status": "idle"}


def _get_settings() -> Settings:
    """Return settings from Flask app context, with safe fallback."""
    settings = current_app.config.get("SETTINGS")
    if isinstance(settings, Settings):
        return settings
    return get_settings()


def _get_service() -> InvoiceService:
    """Build a service instance for current request scope."""
    return InvoiceService(settings=_get_settings())


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as user-friendly text."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes} min {secs} seg"
    return f"{secs} seg"


def _set_processing_state(new_state: dict[str, Any]) -> None:
    """Atomically update background processing state."""
    global _processing_state
    with _state_lock:
        _processing_state = new_state


def _get_processing_state() -> dict[str, Any]:
    """Get a copy of current processing state."""
    with _state_lock:
        return dict(_processing_state)


def _run_background_processing(mode: str, run_id: str) -> None:
    """Execute invoice processing in a background thread."""
    service = _get_service()
    try:
        result = service.process_invoices(mode)
        _set_processing_state(
            {
                "status": "done",
                "run_id": run_id,
                "modo": mode,
                "tiempos": result.get("tiempos", []),
                "total": _format_elapsed(float(result.get("total_seconds", 0))),
                "archivos_rechazados": result.get("archivos_rechazados", []),
                "facturas_con_errores": result.get("facturas_con_errores", []),
                "excel": Path(result.get("excel_path") or "procesadas.xlsx").name,
                "facturas_procesadas": result.get("facturas_procesadas", 0),
                "facturas_nuevas": result.get("facturas_nuevas", 0),
                "facturas_duplicadas": result.get("facturas_duplicadas", 0),
            }
        )
    except Exception as exc:
        logger.exception("Error processing invoices in background")
        _set_processing_state(
            {
                "status": "error",
                "run_id": run_id,
                "modo": mode,
                "error": str(exc),
            }
        )


@facturas_bp.route("/facturas", methods=["GET"])
@facturas_bp.route("/facturas/", methods=["GET"])
def facturas_index():
    """Serve FactuVal UI entrypoint."""
    settings = _get_settings()
    return send_from_directory(str(settings.facturas_codigo_path), "index.html")


@facturas_bp.route("/facturas/styles.css", methods=["GET"])
def facturas_css():
    """Serve FactuVal stylesheet."""
    settings = _get_settings()
    return send_from_directory(
        str(settings.facturas_codigo_path),
        "styles.css",
        mimetype="text/css",
        max_age=0,
    )


@facturas_bp.route("/facturas/<path:filename>", methods=["GET"])
def facturas_static(filename: str):
    """Serve FactuVal static assets from the allowed folder only."""
    settings = _get_settings()
    return send_from_directory(str(settings.facturas_codigo_path), filename)


@facturas_bp.route("/upload", methods=["POST", "OPTIONS"])
def upload_files():
    """Secure upload endpoint for invoice PDFs."""
    if request.method == "OPTIONS":
        return "", 200

    state = _get_processing_state()
    if state.get("status") == "processing":
        return error_response("Ya hay un proceso en ejecución", status=409)

    settings = _get_settings()
    service = _get_service()

    mode = (request.form.get("modo", "acumular") or "acumular").strip().lower()
    if mode not in {"acumular", "separado"}:
        return error_response("Modo inválido. Usa 'acumular' o 'separado'", status=400)

    limpiar = request.form.get("limpiar") == "1"
    if mode == "separado" or limpiar:
        clear_directory_files(
            settings.facturas_path, settings.allowed_upload_extensions
        )

    files = request.files.getlist("files")
    if not files:
        return error_response("No se enviaron archivos", status=400)

    saved: list[str] = []
    rejected: list[dict[str, str]] = []

    for file_storage in files:
        original_name = file_storage.filename or ""
        if not original_name:
            continue

        if not is_allowed_extension(original_name, settings.allowed_upload_extensions):
            rejected.append(
                {
                    "archivo": original_name,
                    "razon": "Extensión no permitida. Solo se aceptan archivos PDF.",
                }
            )
            continue

        safe_name = sanitize_filename(original_name)
        destination = resolve_safe_path(settings.facturas_path, safe_name)
        file_storage.save(destination)

        is_valid, reason = service.validate_invoice_pdf(destination)
        if not is_valid:
            rejected.append({"archivo": safe_name, "razon": reason})
            rejected_path = resolve_safe_path(settings.facturas_rechazados, safe_name)
            service.move_file(destination, rejected_path)
            continue

        saved.append(safe_name)

    if not saved:
        return success_response(
            {
                "status": "ok",
                "saved": saved,
                "processing_started": False,
                "run_id": None,
                "archivos_rechazados": rejected,
                "message": "No hay archivos válidos para procesar",
            }
        )

    run_id = uuid.uuid4().hex
    _set_processing_state(
        {
            "status": "processing",
            "run_id": run_id,
            "tiempo_inicio": time.time(),
            "modo": mode,
        }
    )

    worker = threading.Thread(
        target=_run_background_processing,
        args=(mode, run_id),
        daemon=True,
    )
    worker.start()

    return success_response(
        {
            "status": "ok",
            "saved": saved,
            "processing_started": True,
            "run_id": run_id,
            "archivos_rechazados": rejected,
        }
    )


@facturas_bp.route("/resultado", methods=["GET"])
def processing_result():
    """Return current processing status and summary."""
    state = _get_processing_state()
    status = state.get("status")

    if status == "done":
        return success_response(
            {
                "status": "done",
                "tiempos": state.get("tiempos", []),
                "total": state.get("total", ""),
                "excel": state.get("excel", "procesadas.xlsx"),
                "archivos_rechazados": state.get("archivos_rechazados", []),
                "facturas_con_errores": state.get("facturas_con_errores", []),
                "modo": state.get("modo", "acumular"),
                "run_id": state.get("run_id"),
                "facturas_procesadas": state.get("facturas_procesadas", 0),
                "facturas_nuevas": state.get("facturas_nuevas", 0),
                "facturas_duplicadas": state.get("facturas_duplicadas", 0),
            }
        )

    if status == "error":
        return error_response(
            "Error durante el procesamiento",
            status=500,
            details={
                "run_id": state.get("run_id"),
                "error": state.get("error", "Error desconocido"),
            },
        )

    if status == "processing":
        started_at = float(state.get("tiempo_inicio", time.time()))
        elapsed = max(0.0, time.time() - started_at)
        return success_response(
            {
                "status": "processing",
                "tiempo_actual": _format_elapsed(elapsed),
                "tiempo_segundos": elapsed,
                "run_id": state.get("run_id"),
            }
        )

    return success_response({"status": "idle", "message": "Sin procesos activos"})


@facturas_bp.route("/descargar_excel", methods=["GET"])
def download_excel():
    """Download generated Excel file only from the allowed output directory."""
    settings = _get_settings()
    requested_name = request.args.get("file", "procesadas.xlsx")

    if not is_allowed_extension(requested_name, settings.allowed_excel_extensions):
        return error_response("Archivo no permitido", status=400)

    safe_name = sanitize_filename(requested_name)
    file_path = resolve_safe_path(settings.facturas_root, safe_name)

    if not file_path.exists():
        return error_response("El archivo aún no está disponible", status=404)

    return send_from_directory(
        str(settings.facturas_root), safe_name, as_attachment=True
    )
