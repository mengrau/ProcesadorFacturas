from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from facturas_app.config import Settings, get_settings
from facturas_app.legacy.bridge import get_invoice_legacy
from facturas_app.models.dto import ProcessingSummary

logger = logging.getLogger(__name__)

_validation_cache_lock = threading.Lock()
_legacy_runtime_lock = threading.Lock()
_validation_cache: dict[tuple[str, int, int], tuple[bool, str]] = {}


@dataclass(slots=True)
class _FileProcessingResult:
    file_name: str
    file_path: Path
    valid: bool
    validation_message: str
    records: list[dict[str, Any]]
    elapsed_seconds: float
    error: str | None = None


def _file_validation_key(path: Path) -> tuple[str, int, int] | None:
    """Build a cache key based on file identity and content metadata."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path.resolve()).lower(), int(stat.st_size), int(stat.st_mtime_ns))


class InvoiceService:
    """Facade around the legacy invoice processor with typed interfaces."""

    def __init__(
        self,
        settings: Settings | None = None,
        legacy_module: ModuleType | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._legacy = legacy_module or get_invoice_legacy()

    def _configure_legacy_paths(self) -> None:
        """Align legacy constants with centralized settings for deterministic runtime."""
        path_overrides = {
            "FACTURAS_ROOT": str(self.settings.facturas_root),
            "FACTURAS_PATH": str(self.settings.facturas_path),
            "FACTURAS_PROCESADAS": str(self.settings.facturas_procesadas),
            "EXCEL_SALIDA": str(self.settings.excel_salida),
            "BASE_PATH": str(self.settings.base_path),
        }
        for attr_name, value in path_overrides.items():
            if hasattr(self._legacy, attr_name):
                setattr(self._legacy, attr_name, value)

        for folder in (
            self.settings.facturas_path,
            self.settings.facturas_procesadas,
            self.settings.facturas_rechazados,
            self.settings.facturas_errores,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def _legacy_runtime_context(self):
        """Configure legacy runtime and optionally mute verbose legacy prints."""
        with _legacy_runtime_lock:
            self._configure_legacy_paths()
            if not self.settings.processing_quiet_legacy_logs:
                yield
                return

            marker = object()
            previous_print = getattr(self._legacy, "print", marker)
            setattr(self._legacy, "print", lambda *args, **kwargs: None)
            try:
                yield
            finally:
                if previous_print is marker:
                    try:
                        delattr(self._legacy, "print")
                    except Exception:
                        pass
                else:
                    setattr(self._legacy, "print", previous_print)

    def _supports_optimized_pipeline(self) -> bool:
        """Return whether required legacy hooks exist for optimized orchestration."""
        required_callables = (
            "_es_factura_valida",
            "cargar_facturas_existentes",
            "extraer_datos_factura",
            "guardar_en_excel",
            "mover_archivo_seguro",
        )
        return all(
            callable(getattr(self._legacy, name, None)) for name in required_callables
        )

    def _get_cached_validation(self, pdf_path: Path) -> tuple[bool, str] | None:
        key = _file_validation_key(pdf_path)
        if key is None:
            return None
        with _validation_cache_lock:
            return _validation_cache.get(key)

    def _set_cached_validation(self, pdf_path: Path, result: tuple[bool, str]) -> None:
        key = _file_validation_key(pdf_path)
        if key is None:
            return
        with _validation_cache_lock:
            _validation_cache[key] = result

    def validate_invoice_pdf(self, pdf_path: Path) -> tuple[bool, str]:
        """Validate a PDF file using existing business rules."""
        cached = self._get_cached_validation(pdf_path)
        if cached is not None:
            return cached

        validator = getattr(self._legacy, "_es_factura_valida", None)
        if not callable(validator):
            raise RuntimeError("Legacy module does not expose _es_factura_valida")

        raw_result = validator(str(pdf_path))
        result = (bool(raw_result[0]), str(raw_result[1]))
        self._set_cached_validation(pdf_path, result)
        return result

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

    def _resolve_workers(self, total_files: int) -> int:
        if total_files <= 1 or not self.settings.processing_parallel_enabled:
            return 1

        if self.settings.processing_max_workers > 0:
            return max(1, min(self.settings.processing_max_workers, total_files))

        cpu_count = os.cpu_count() or 1
        return max(1, min(total_files, min(8, cpu_count)))

    def _collect_pdf_files(self) -> list[Path]:
        files: list[Path] = []
        for name in os.listdir(self.settings.facturas_path):
            if not name.lower().endswith(".pdf"):
                continue
            path = self.settings.facturas_path / name
            if path.is_file():
                files.append(path)
        return files

    def _process_single_pdf(self, pdf_path: Path, mode: str) -> _FileProcessingResult:
        file_name = pdf_path.name
        file_started_at = time.perf_counter()
        current_stage = "validate_invoice_pdf"
        logger.info("Invoice file processing started. file=%s mode=%s", file_name, mode)
        try:
            validate_started_at = time.perf_counter()
            logger.info(
                "Invoice stage start. stage=%s file=%s mode=%s",
                current_stage,
                file_name,
                mode,
            )
            is_valid, reason = self.validate_invoice_pdf(pdf_path)
            logger.info(
                "Invoice stage done. stage=%s file=%s mode=%s elapsed=%.3fs valid=%s",
                current_stage,
                file_name,
                mode,
                time.perf_counter() - validate_started_at,
                is_valid,
            )
            if not is_valid:
                logger.info(
                    "Invoice file rejected. file=%s mode=%s reason=%s",
                    file_name,
                    mode,
                    reason,
                )
                return _FileProcessingResult(
                    file_name=file_name,
                    file_path=pdf_path,
                    valid=False,
                    validation_message=reason,
                    records=[],
                    elapsed_seconds=0.0,
                )

            # For accumulated mode we extract full records first and apply duplicate filtering later.
            extraction_mode = "separado" if mode == "acumular" else mode
            current_stage = "extraer_datos_factura"
            extraction_started_at = time.perf_counter()
            logger.info(
                "Invoice stage start. stage=%s file=%s mode=%s extraction_mode=%s",
                current_stage,
                file_name,
                mode,
                extraction_mode,
            )
            records = self._legacy.extraer_datos_factura(
                str(pdf_path),
                set(),
                100,
                extraction_mode,
            )
            extraction_elapsed = time.perf_counter() - extraction_started_at
            logger.info(
                "Invoice stage done. stage=%s file=%s mode=%s elapsed=%.3fs records=%s",
                current_stage,
                file_name,
                mode,
                extraction_elapsed,
                len(records or []),
            )
            logger.info(
                "Invoice file processing finished. file=%s mode=%s elapsed=%.3fs",
                file_name,
                mode,
                time.perf_counter() - file_started_at,
            )

            return _FileProcessingResult(
                file_name=file_name,
                file_path=pdf_path,
                valid=True,
                validation_message=reason,
                records=list(records or []),
                elapsed_seconds=extraction_elapsed,
            )
        except Exception as exc:
            logger.exception(
                "Invoice file processing failed. file=%s mode=%s stage=%s elapsed=%.3fs",
                file_name,
                mode,
                current_stage,
                time.perf_counter() - file_started_at,
            )
            return _FileProcessingResult(
                file_name=file_name,
                file_path=pdf_path,
                valid=True,
                validation_message="Archivo válido",
                records=[],
                elapsed_seconds=0.0,
                error=str(exc),
            )

    @staticmethod
    def _filter_records_for_accumulated_mode(
        records: list[dict[str, Any]],
        seen_invoices: set[str],
    ) -> list[dict[str, Any]]:
        """Keep only records from invoices not seen before, preserving file order."""
        if not records:
            return []

        accepted_invoices: set[str] = set()
        rejected_invoices: set[str] = set()
        filtered: list[dict[str, Any]] = []

        for record in records:
            invoice_number = str(record.get("numero_factura", ""))

            if invoice_number in accepted_invoices:
                filtered.append(record)
                continue

            if invoice_number in rejected_invoices:
                continue

            if invoice_number in seen_invoices:
                rejected_invoices.add(invoice_number)
                continue

            seen_invoices.add(invoice_number)
            accepted_invoices.add(invoice_number)
            filtered.append(record)

        return filtered

    def _set_legacy_summaries(
        self,
        tiempos: list[dict[str, float | str]],
        rechazados: list[dict[str, str]],
        errores: list[dict[str, str]],
    ) -> None:
        if hasattr(self._legacy, "tiempos_procesamiento"):
            setattr(self._legacy, "tiempos_procesamiento", tiempos.copy())
        if hasattr(self._legacy, "archivos_rechazados_global"):
            setattr(self._legacy, "archivos_rechazados_global", rechazados.copy())
        if hasattr(self._legacy, "facturas_con_errores_global"):
            setattr(self._legacy, "facturas_con_errores_global", errores.copy())

    def _run_optimized_pipeline(self, mode: str) -> ProcessingSummary:
        started_at = time.perf_counter()
        list_started_at = time.perf_counter()
        logger.info("Invoice stage start. stage=collect_pdf_files mode=%s", mode)
        pdf_files = self._collect_pdf_files()
        logger.info(
            "Invoice stage done. stage=collect_pdf_files mode=%s elapsed=%.3fs files=%s",
            mode,
            time.perf_counter() - list_started_at,
            len(pdf_files),
        )

        if not pdf_files:
            total_seconds = time.perf_counter() - started_at
            summary: ProcessingSummary = {
                "excel_path": None,
                "tiempos": [],
                "archivos_rechazados": [],
                "facturas_con_errores": [],
                "total_seconds": total_seconds,
                "facturas_procesadas": 0,
                "facturas_nuevas": 0,
                "facturas_duplicadas": 0,
            }
            self._set_legacy_summaries([], [], [])
            return summary

        seen_invoices: set[str] = set()
        if mode == "acumular":
            load_started_at = time.perf_counter()
            logger.info(
                "Invoice stage start. stage=cargar_facturas_existentes mode=%s excel=%s",
                mode,
                self.settings.excel_salida,
            )
            loaded = self._legacy.cargar_facturas_existentes(
                str(self.settings.excel_salida)
            )
            if isinstance(loaded, set):
                seen_invoices.update(loaded)
            elif loaded:
                seen_invoices.update(str(value) for value in loaded)
            logger.info(
                "Invoice stage done. stage=cargar_facturas_existentes mode=%s elapsed=%.3fs facturas_existentes=%s",
                mode,
                time.perf_counter() - load_started_at,
                len(seen_invoices),
            )

        workers = self._resolve_workers(len(pdf_files))
        logger.info(
            "Invoice optimized pipeline enabled. mode=%s workers=%s", mode, workers
        )

        file_results: dict[Path, _FileProcessingResult] = {}
        if workers == 1:
            for pdf_path in pdf_files:
                file_results[pdf_path] = self._process_single_pdf(pdf_path, mode)
        else:
            with ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="facturas"
            ) as executor:
                future_to_path = {
                    executor.submit(self._process_single_pdf, pdf_path, mode): pdf_path
                    for pdf_path in pdf_files
                }
                for future in as_completed(future_to_path):
                    pdf_path = future_to_path[future]
                    try:
                        file_results[pdf_path] = future.result()
                    except Exception as exc:
                        file_results[pdf_path] = _FileProcessingResult(
                            file_name=pdf_path.name,
                            file_path=pdf_path,
                            valid=True,
                            validation_message="Archivo válido",
                            records=[],
                            elapsed_seconds=0.0,
                            error=str(exc),
                        )

        tiempos_individuales: list[dict[str, float | str]] = []
        archivos_rechazados: list[dict[str, str]] = []
        facturas_con_errores: list[dict[str, str]] = []
        datos_todas: list[dict[str, Any]] = []

        for pdf_path in pdf_files:
            result = file_results[pdf_path]

            if not result.valid:
                archivos_rechazados.append(
                    {"archivo": result.file_name, "razon": result.validation_message}
                )
                self.move_file(
                    pdf_path,
                    self.settings.facturas_rechazados / result.file_name,
                )
                continue

            if result.error:
                facturas_con_errores.append(
                    {
                        "archivo": result.file_name,
                        "razon": "Esta factura no se pudo procesar",
                    }
                )
                self.move_file(
                    pdf_path,
                    self.settings.facturas_errores / result.file_name,
                )
                continue

            tiempos_individuales.append(
                {"archivo": result.file_name, "tiempo": result.elapsed_seconds}
            )

            records = result.records
            if mode == "acumular":
                records = self._filter_records_for_accumulated_mode(
                    records, seen_invoices
                )

            if records:
                datos_todas.extend(records)
                if mode == "acumular":
                    self.move_file(
                        pdf_path,
                        self.settings.facturas_procesadas / result.file_name,
                    )
            else:
                facturas_con_errores.append(
                    {
                        "archivo": result.file_name,
                        "razon": "Esta factura no se pudo procesar",
                    }
                )
                self.move_file(
                    pdf_path,
                    self.settings.facturas_errores / result.file_name,
                )

        self._set_legacy_summaries(
            tiempos_individuales,
            archivos_rechazados,
            facturas_con_errores,
        )

        total_seconds = time.perf_counter() - started_at
        if not datos_todas:
            return {
                "excel_path": None,
                "tiempos": [],
                "archivos_rechazados": archivos_rechazados,
                "facturas_con_errores": facturas_con_errores,
                "total_seconds": total_seconds,
                "facturas_procesadas": 0,
            }

        unicos: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        facturas_nuevas = 0
        facturas_duplicadas = 0

        for record in datos_todas:
            key = (
                str(record.get("numero_factura", "")),
                str(record.get("referencia", "")),
                str(record.get("productos", "")),
                str(record.get("total", "")),
            )
            if key not in unicos:
                unicos[key] = record
                if mode == "acumular":
                    if str(record.get("numero_factura", "")) in seen_invoices:
                        facturas_duplicadas += 1
                    else:
                        facturas_nuevas += 1
                else:
                    facturas_nuevas += 1
            elif mode == "acumular":
                facturas_duplicadas += 1

        save_started_at = time.perf_counter()
        logger.info(
            "Invoice stage start. stage=guardar_en_excel mode=%s registros=%s",
            mode,
            len(unicos),
        )
        excel_path = self._legacy.guardar_en_excel(list(unicos.values()), mode)
        logger.info(
            "Invoice stage done. stage=guardar_en_excel mode=%s elapsed=%.3fs excel=%s",
            mode,
            time.perf_counter() - save_started_at,
            excel_path,
        )
        return {
            "excel_path": excel_path,
            "tiempos": tiempos_individuales,
            "archivos_rechazados": archivos_rechazados,
            "facturas_con_errores": facturas_con_errores,
            "total_seconds": total_seconds,
            "facturas_procesadas": len(unicos),
            "facturas_nuevas": facturas_nuevas,
            "facturas_duplicadas": facturas_duplicadas,
        }

    def process_invoices(self, mode: str = "acumular") -> ProcessingSummary:
        """Process invoices preserving legacy behavior and output format."""
        if mode not in {"acumular", "separado"}:
            raise ValueError("Mode must be either 'acumular' or 'separado'")

        logger.info("Starting invoice processing. mode=%s", mode)
        with self._legacy_runtime_context():
            if self._supports_optimized_pipeline():
                logger.info("Invoice pipeline selected. implementation=optimized")
                try:
                    result = self._run_optimized_pipeline(mode)
                except Exception:
                    logger.exception(
                        "Optimized invoice pipeline failed. Falling back to legacy processor."
                    )
                    logger.info(
                        "Invoice pipeline selected. implementation=legacy-fallback"
                    )
                    result = self._legacy.procesar_facturas(mode)
            else:
                logger.info("Invoice pipeline selected. implementation=legacy")
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
