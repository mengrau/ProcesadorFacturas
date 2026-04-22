from __future__ import annotations

from flask import Blueprint

from facturas_app.legacy.bridge import get_server_legacy

legacy_bp = Blueprint("legacy_proxy", __name__)


def _legacy():
    """Return loaded legacy server module."""
    return get_server_legacy()


@legacy_bp.route("/", methods=["GET"])
def index():
    return _legacy().index()


@legacy_bp.route("/styles.css", methods=["GET"])
def styles():
    return _legacy().styles()


@legacy_bp.route("/diferencias", methods=["GET"])
@legacy_bp.route("/diferencias/", methods=["GET"])
def diferencias_page():
    return _legacy().diferencias_page()


@legacy_bp.route("/diferencias.css", methods=["GET"])
def diferencias_css():
    return _legacy().diferencias_css()


@legacy_bp.route("/listas", methods=["GET"])
@legacy_bp.route("/listas/", methods=["GET"])
def listas_page():
    return _legacy().listas_page()


@legacy_bp.route("/listas.css", methods=["GET"])
def listas_css():
    return _legacy().listas_css()


@legacy_bp.route("/portafolios", methods=["GET"])
@legacy_bp.route("/portafolios/", methods=["GET"])
def portafolios_page():
    return _legacy().portafolios_page()


@legacy_bp.route("/portafolios.css", methods=["GET"])
def portafolios_css():
    return _legacy().portafolios_css()


@legacy_bp.route("/dsd", methods=["GET"])
@legacy_bp.route("/dsd/", methods=["GET"])
def dsd_page():
    return _legacy().dsd_page()


@legacy_bp.route("/dsd.css", methods=["GET"])
def dsd_css():
    return _legacy().dsd_css()


@legacy_bp.route("/api/listas/iniciar", methods=["POST"])
def api_listas_iniciar():
    return _legacy().api_listas_iniciar()


@legacy_bp.route("/api/listas/estado", methods=["GET"])
def api_listas_estado():
    return _legacy().api_listas_estado()


@legacy_bp.route("/api/listas/descargar", methods=["GET"])
def api_listas_descargar():
    return _legacy().api_listas_descargar()


@legacy_bp.route("/api/diferencias/iniciar", methods=["POST"])
def api_diferencias_iniciar():
    return _legacy().api_diferencias_iniciar()


@legacy_bp.route("/api/diferencias/estado", methods=["GET"])
def api_diferencias_estado():
    return _legacy().api_diferencias_estado()


@legacy_bp.route("/api/diferencias/descargar", methods=["GET"])
def api_diferencias_descargar():
    return _legacy().api_diferencias_descargar()


@legacy_bp.route("/api/portafolios/iniciar", methods=["POST"])
def api_portafolios_iniciar():
    return _legacy().api_portafolios_iniciar()


@legacy_bp.route("/api/portafolios/progreso", methods=["GET"])
def api_portafolios_progreso():
    return _legacy().api_portafolios_progreso()


@legacy_bp.route("/api/dsd/upload", methods=["POST"])
def api_dsd_upload():
    return _legacy().api_dsd_upload()


@legacy_bp.route("/api/dsd/iniciar", methods=["POST"])
def api_dsd_iniciar():
    return _legacy().api_dsd_iniciar()


@legacy_bp.route("/api/dsd/estado", methods=["GET"])
def api_dsd_estado():
    return _legacy().api_dsd_estado()


@legacy_bp.route("/api/dsd/descargar", methods=["GET"])
def api_dsd_descargar():
    return _legacy().api_dsd_descargar()


@legacy_bp.route("/<path:filename>", methods=["GET"])
def serve_static(filename: str):
    return _legacy().serve_static(filename)
