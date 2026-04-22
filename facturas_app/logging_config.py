from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path


def configure_logging(log_level: str = "INFO", base_dir: Path | None = None) -> None:
    """Configure structured logging for console and rotating file output."""
    root_dir = base_dir or Path(__file__).resolve().parents[1]
    log_dir = root_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    app_log_path = log_dir / "app.log"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": log_level,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "filename": str(app_log_path),
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 3,
                    "encoding": "utf-8",
                    "level": log_level,
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": log_level,
            },
        }
    )

    logging.getLogger(__name__).info("Logging configured. Log file: %s", app_log_path)
