from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from facturas_app.api.facturas import facturas_bp
from facturas_app.api.health import health_bp
from facturas_app.api.legacy_proxy import legacy_bp
from facturas_app.config import Settings, ensure_directories, get_settings
from facturas_app.logging_config import configure_logging
from facturas_app.utils.responses import error_response

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> Flask:
    """Application factory for the modular Facturas backend."""
    cfg = settings or get_settings()
    ensure_directories(cfg)
    configure_logging()

    app = Flask(__name__, static_folder=None)
    app.config["SETTINGS"] = cfg
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_content_length_bytes

    CORS(
        app,
        resources={
            r"/api/*": {"origins": list(cfg.cors_origins)},
            r"/upload": {"origins": list(cfg.cors_origins)},
            r"/resultado": {"origins": list(cfg.cors_origins)},
            r"/descargar_excel": {"origins": list(cfg.cors_origins)},
        },
    )

    app.register_blueprint(facturas_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(legacy_bp)

    @app.errorhandler(413)
    def payload_too_large(_: Exception):
        return error_response(
            "Archivo demasiado grande para el límite configurado",
            status=413,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return error_response(exc.description, status=exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc: Exception):
        logger.exception("Unhandled server exception")
        return error_response(
            "Error interno del servidor",
            status=500,
            details={"error": str(exc)},
        )

    return app
