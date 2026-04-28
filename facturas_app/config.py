from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_dotenv_if_available() -> None:
    """Load environment variables from .env when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # The project remains functional without python-dotenv.
        return


def _as_bool(value: str | None, default: bool) -> bool:
    """Parse boolean strings with a deterministic fallback."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_tuple_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse comma-separated values preserving only non-empty tokens."""
    if not value:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return tuple(items) if items else default


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    base_path: Path
    facturas_root: Path
    facturas_path: Path
    facturas_procesadas: Path
    facturas_rechazados: Path
    facturas_errores: Path
    facturas_codigo_path: Path
    excel_salida: Path
    web_assets_path: Path
    carpeta_base_dif: Path
    ruta_base_jerarquia: Path
    ruta_salida_dsd: Path
    dsd_temp_path: Path
    max_content_length_mb: int = 100
    allowed_upload_extensions: tuple[str, ...] = (".pdf",)
    allowed_excel_extensions: tuple[str, ...] = (".xlsx", ".xls", ".xlsm")
    cors_origins: tuple[str, ...] = (
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    )
    flask_host: str = "0.0.0.0"
    flask_port: int = 5000
    flask_debug: bool = False
    disable_excel_update: bool = True
    processing_parallel_enabled: bool = True
    processing_max_workers: int = 0
    processing_quiet_legacy_logs: bool = True
    page_timeout_seconds: float = 8.0
    page_max_workers: int = 6
    page_temp_dir: Path = Path("temp")
    page_fallback_enabled: bool = True
    page_fallback_library: str = "pymupdf"
    page_keep_temp_files: bool = False

    @property
    def max_content_length_bytes(self) -> int:
        """Return request payload size limit in bytes."""
        return self.max_content_length_mb * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment with safe defaults for local Windows execution."""
        _load_dotenv_if_available()

        workspace_root = Path(__file__).resolve().parents[1]
        default_base_path = workspace_root

        base_path = Path(os.getenv("BASE_PATH", str(default_base_path)))
        facturas_root = Path(os.getenv("FACTURAS_ROOT", str(base_path / "Facturas")))

        return cls(
            base_path=base_path,
            facturas_root=facturas_root,
            facturas_path=Path(
                os.getenv("FACTURAS_PATH", str(facturas_root / "entrada"))
            ),
            facturas_procesadas=Path(
                os.getenv("FACTURAS_PROCESADAS", str(facturas_root / "salida"))
            ),
            facturas_rechazados=Path(
                os.getenv("FACTURAS_RECHAZADOS", str(facturas_root / "rechazados"))
            ),
            facturas_errores=Path(
                os.getenv("FACTURAS_ERRORES", str(facturas_root / "errores"))
            ),
            facturas_codigo_path=Path(
                os.getenv("FACTURAS_CODIGO_PATH", str(workspace_root / "cod_facturas"))
            ),
            excel_salida=Path(
                os.getenv("EXCEL_SALIDA", str(facturas_root / "procesadas.xlsx"))
            ),
            web_assets_path=Path(
                os.getenv("WEB_ASSETS_PATH", str(workspace_root / "cod_facturas"))
            ),
            carpeta_base_dif=Path(
                os.getenv(
                    "CARPETA_BASE_DIF",
                    str(base_path / "LISTAS DE PRECIOS"),
                )
            ),
            ruta_base_jerarquia=Path(
                os.getenv(
                    "RUTA_BASE_JERARQUIA",
                    str(
                        base_path
                        / "Analistas Precios - BASES SAP"
                        / "MaestraCientes"
                        / "Base Jerarquia.xlsx"
                    ),
                )
            ),
            ruta_salida_dsd=Path(
                os.getenv(
                    "RUTA_SALIDA_DSD",
                    str(base_path / "Analistas Precios - BASES SAP"),
                )
            ),
            dsd_temp_path=Path(os.getenv("DSD_TEMP_PATH", str(base_path / "DSD_temp"))),
            max_content_length_mb=int(os.getenv("MAX_CONTENT_LENGTH_MB", "100")),
            allowed_upload_extensions=_as_tuple_csv(
                os.getenv("ALLOWED_UPLOAD_EXTENSIONS"),
                (".pdf",),
            ),
            allowed_excel_extensions=_as_tuple_csv(
                os.getenv("ALLOWED_EXCEL_EXTENSIONS"),
                (".xlsx", ".xls", ".xlsm"),
            ),
            cors_origins=_as_tuple_csv(
                os.getenv("CORS_ORIGINS"),
                ("http://localhost:5000", "http://127.0.0.1:5000"),
            ),
            flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
            flask_port=int(os.getenv("FLASK_PORT", "5000")),
            flask_debug=_as_bool(os.getenv("FLASK_DEBUG"), default=False),
            disable_excel_update=_as_bool(
                os.getenv("DESHABILITAR_ACTUALIZACION_EXCEL"),
                default=True,
            ),
            processing_parallel_enabled=_as_bool(
                os.getenv("PROCESSING_PARALLEL_ENABLED"),
                default=True,
            ),
            processing_max_workers=int(os.getenv("PROCESSING_MAX_WORKERS", "0")),
            processing_quiet_legacy_logs=_as_bool(
                os.getenv("PROCESSING_QUIET_LEGACY_LOGS"),
                default=True,
            ),
            page_timeout_seconds=float(os.getenv("PAGE_TIMEOUT_SECONDS", "10")),
            page_max_workers=int(os.getenv("PAGE_MAX_WORKERS", "2")),
            page_temp_dir=Path(os.getenv("PAGE_TEMP_DIR", str(facturas_root / "temp"))),
            page_fallback_enabled=_as_bool(
                os.getenv("PAGE_FALLBACK_ENABLED"),
                default=True,
            ),
            page_fallback_library=os.getenv("PAGE_FALLBACK_LIBRARY", "pymupdf"),
            page_keep_temp_files=_as_bool(
                os.getenv("PAGE_KEEP_TEMP_FILES"),
                default=False,
            ),
        )


def ensure_directories(settings: Settings) -> None:
    """Create required runtime directories if they do not exist."""
    required_dirs = (
        settings.facturas_root,
        settings.facturas_path,
        settings.facturas_procesadas,
        settings.facturas_rechazados,
        settings.facturas_errores,
        settings.dsd_temp_path,
        settings.page_temp_dir,
    )
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton settings instance for the current process."""
    return Settings.from_env()
