from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from facturas_app.config import Settings, get_settings
from facturas_app.services.dsd_service import DsdService
from facturas_app.utils.file_security import (
    clear_directory_files,
    is_allowed_extension,
    resolve_safe_path,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

dsd_bp = Blueprint("dsd", __name__)

_state_lock = threading.Lock()
_dsd_state: dict[str, Any] = {
    "estado": "inactivo",
    "etapa": "",
    "progreso": 0,
    "clientes_procesados": 0,
    "total_filas": 0,
    "archivo_generado": "",
    "mensaje": "",
}
_uploaded_file: Path | None = None


def _get_settings() -> Settings:
    settings = current_app.config.get("SETTINGS")
    if isinstance(settings, Settings):
        return settings
    return get_settings()


def _set_state(data: dict[str, Any]) -> None:
    global _dsd_state
    with _state_lock:
        _dsd_state = {**_dsd_state, **data}


def _get_state() -> dict[str, Any]:
    with _state_lock:
        return dict(_dsd_state)


def _reset_state() -> None:
    _set_state(
        {
            "estado": "inactivo",
            "etapa": "",
            "progreso": 0,
            "clientes_procesados": 0,
            "total_filas": 0,
            "archivo_generado": "",
            "mensaje": "",
        }
    )


def _run_dsd(source_path: Path, settings: Settings) -> None:
    global _uploaded_file
    service = DsdService(settings)
    try:
        _set_state(
            {
                "estado": "procesando",
                "etapa": "Validando archivo de origen...",
                "progreso": 0,
                "clientes_procesados": 0,
                "total_filas": 0,
                "archivo_generado": "",
                "mensaje": "",
            }
        )
        result = service.process(source_path, progress_callback=_set_state)
        _set_state(
            {
                "estado": "completado",
                "etapa": "Proceso completado exitosamente",
                "progreso": 100,
                "total_filas": result["total_filas"],
                "archivo_generado": result["archivo_generado"],
                "mensaje": "",
            }
        )
    except Exception as exc:
        logger.exception("DSD processing failed")
        _set_state(
            {
                "estado": "error",
                "etapa": "Error",
                "mensaje": str(exc),
            }
        )
    finally:
        if _uploaded_file and _uploaded_file == source_path and source_path.exists():
            try:
                source_path.unlink()
            except Exception:
                logger.warning("Could not delete temporary DSD file: %s", source_path)
        if _uploaded_file == source_path:
            _uploaded_file = None


@dsd_bp.route("/api/dsd/upload", methods=["POST"])
def api_dsd_upload():
    global _uploaded_file
    settings = _get_settings()

    if _get_state().get("estado") == "procesando":
        return jsonify({"error": "Ya hay un proceso en ejecucion"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No se envio ningun archivo"}), 400

    file_storage = request.files["file"]
    original_name = file_storage.filename or ""
    if not original_name:
        return jsonify({"error": "No se selecciono ningun archivo"}), 400

    if not is_allowed_extension(original_name, settings.allowed_excel_extensions):
        return (
            jsonify({"error": "El archivo debe ser un Excel (.xlsx, .xls, .xlsm)"}),
            400,
        )

    try:
        settings.dsd_temp_path.mkdir(parents=True, exist_ok=True)
        clear_directory_files(settings.dsd_temp_path, settings.allowed_excel_extensions)

        suffix = Path(sanitize_filename(original_name)).suffix or ".xlsx"
        generated_name = f"Base_Jerarquia_{uuid.uuid4().hex[:8]}{suffix}"
        destination = resolve_safe_path(settings.dsd_temp_path, generated_name)
        file_storage.save(destination)

        _uploaded_file = destination
        _reset_state()
        _set_state(
            {"estado": "listo", "etapa": "Archivo cargado. Listo para iniciar."}
        )

        return jsonify({"ok": True, "filename": original_name})
    except Exception as exc:
        logger.exception("DSD upload failed")
        return jsonify({"error": f"Error al guardar el archivo: {str(exc)}"}), 500


@dsd_bp.route("/api/dsd/iniciar", methods=["POST"])
def api_dsd_iniciar():
    state = _get_state()
    if state.get("estado") == "procesando":
        return jsonify({"error": "Ya hay un proceso en ejecucion"}), 400

    if not _uploaded_file or not _uploaded_file.exists():
        return (
            jsonify(
                {
                    "error": (
                        "No hay archivo subido. Por favor, sube el archivo "
                        "Base Jerarquia.xlsx primero."
                    )
                }
            ),
            400,
        )

    settings = _get_settings()
    worker = threading.Thread(
        target=_run_dsd,
        args=(_uploaded_file, settings),
        daemon=True,
    )
    worker.start()

    return jsonify({"ok": True})


@dsd_bp.route("/api/dsd/estado", methods=["GET"])
def api_dsd_estado():
    return jsonify(_get_state())


@dsd_bp.route("/api/dsd/descargar", methods=["GET"])
def api_dsd_descargar():
    state = _get_state()
    generated_file = state.get("archivo_generado")
    if not generated_file:
        return jsonify({"error": "Archivo no disponible"}), 404

    file_path = Path(generated_file)
    if not file_path.exists():
        return jsonify({"error": "Archivo no disponible"}), 404

    return send_from_directory(
        str(file_path.parent),
        file_path.name,
        as_attachment=True,
    )
