from __future__ import annotations

import logging
import multiprocessing
import os
import queue
import sys
import time
from pathlib import Path
from typing import Any

import pdfplumber

logger = logging.getLogger(__name__)

PageResult = dict[str, Any]


class PdfTextExtractor:
    """Extract text from PDF pages with timeout and retry support."""

    def extract_page_text_pdfplumber(self, pdf_path: str, page_index: int) -> str:
        with pdfplumber.open(pdf_path) as pdf:
            if page_index < 0 or page_index >= len(pdf.pages):
                raise IndexError("page_index out of range")
            return pdf.pages[page_index].extract_text() or ""

    def _page_text_worker(
        self,
        engine: str,
        pdf_path: str,
        page_index: int,
        result_queue,
    ) -> None:
        started_at = time.perf_counter()
        try:
            if engine == "pdfplumber":
                text = self.extract_page_text_pdfplumber(pdf_path, page_index)
            else:
                raise ValueError(f"Unsupported engine: {engine}")
            result_queue.put(
                {
                    "status": "OK",
                    "text": text,
                    "error": "",
                    "elapsed": time.perf_counter() - started_at,
                    "method": engine,
                }
            )
        except Exception as exc:
            result_queue.put(
                {
                    "status": "ERROR",
                    "text": "",
                    "error": str(exc),
                    "elapsed": time.perf_counter() - started_at,
                    "method": engine,
                }
            )

    def extract_pages_with_timeout(
        self,
        engine: str,
        pdf_path: str,
        page_indices: list[int],
        timeout_seconds: float,
        max_workers: int,
        *,
        source_file: str | None = None,
        page_map: dict[int, int] | None = None,
    ) -> dict[int, PageResult]:
        multiprocessing.set_executable(sys.executable)
        ctx = multiprocessing.get_context("spawn")
        results: dict[int, PageResult] = {}
        pending = list(page_indices)
        active: list[dict[str, Any]] = []

        timeout_seconds = max(0.1, float(timeout_seconds))
        max_workers = max(1, int(max_workers or 1))

        def _start_task(page_index: int) -> dict[str, Any]:
            task_queue = ctx.Queue()
            proc = ctx.Process(
                target=self._page_text_worker,
                args=(engine, pdf_path, page_index, task_queue),
            )
            proc.daemon = True
            proc.start()
            return {
                "page_index": page_index,
                "process": proc,
                "queue": task_queue,
                "start": time.perf_counter(),
            }

        def _log_result(result: PageResult) -> None:
            display_file = source_file or os.path.basename(pdf_path)
            if not display_file:
                return
            raw_index = int(result.get("page_index", 0))
            display_index = (
                page_map.get(raw_index, raw_index) if page_map else raw_index
            )
            logger.info(
                "Page extraction live. file=%s page=%s method=%s status=%s elapsed=%.3fs error=%s",
                display_file,
                display_index + 1,
                result.get("method", engine),
                result.get("status", "ERROR"),
                float(result.get("elapsed", 0.0)),
                result.get("error", ""),
            )

        try:
            while pending or active:
                while pending and len(active) < max_workers:
                    active.append(_start_task(pending.pop(0)))

                for task in list(active):
                    result = None
                    try:
                        result = task["queue"].get_nowait()
                    except queue.Empty:
                        result = None
                    except Exception:
                        result = None

                    if result is not None:
                        result["page_index"] = task["page_index"]
                        results[task["page_index"]] = result
                        _log_result(result)
                        task["process"].join(timeout=0)
                        task["queue"].close()
                        active.remove(task)
                        continue

                    if not task["process"].is_alive():
                        result = {
                            "page_index": task["page_index"],
                            "status": "ERROR",
                            "text": "",
                            "error": "worker_exited_without_result",
                            "elapsed": time.perf_counter() - task["start"],
                            "method": engine,
                        }
                        results[task["page_index"]] = result
                        _log_result(result)
                        task["queue"].close()
                        active.remove(task)
                        continue

                    elapsed = time.perf_counter() - task["start"]
                    if elapsed >= timeout_seconds:
                        task["process"].terminate()
                        task["process"].join(timeout=1)
                        result = {
                            "page_index": task["page_index"],
                            "status": "TIMEOUT",
                            "text": "",
                            "error": f"timeout after {timeout_seconds:.2f}s",
                            "elapsed": elapsed,
                            "method": engine,
                        }
                        results[task["page_index"]] = result
                        _log_result(result)
                        task["queue"].close()
                        active.remove(task)

                if active:
                    time.sleep(0.05)
        except KeyboardInterrupt:
            for task in list(active):
                try:
                    if task["process"].is_alive():
                        task["process"].terminate()
                    task["process"].join(timeout=1)
                except Exception:
                    pass
                try:
                    task["queue"].close()
                except Exception:
                    pass
            raise

        return results

    @staticmethod
    def safe_unlink(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            return

    @staticmethod
    def write_timeout_pages_file(
        output_path: str,
        page_indices: list[int],
        total_pages: int,
        source_file: str,
    ) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        lines = [
            f"file={source_file}",
            f"total_pages={total_pages}",
            "timeout_pages_1_based=" + ",".join(str(i + 1) for i in page_indices),
            "",
        ]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

    def extract_pdf_pages_with_retries(
        self,
        pdf_path: str,
        *,
        timeout_seconds: float,
        max_workers: int,
        temp_dir_root: str,
        fallback_enabled: bool,
        source_file: str | None = None,
    ) -> dict[str, Any]:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

        page_indices = list(range(total_pages))
        timeout_seconds = max(0.1, float(timeout_seconds))
        max_workers = max(1, int(max_workers or 1))
        source_name = source_file or os.path.basename(pdf_path)

        logger.info(
            "Page extraction start. file=%s pages=%s timeout=%.2fs workers=%s engine=pdfplumber",
            source_name,
            total_pages,
            timeout_seconds,
            max_workers,
        )

        primary_results = self.extract_pages_with_timeout(
            "pdfplumber",
            pdf_path,
            page_indices,
            timeout_seconds,
            max_workers,
            source_file=source_name,
        )

        final_texts: dict[int, str] = {}
        final_status: dict[int, str] = {}
        final_method: dict[int, str] = {}
        final_elapsed: dict[int, float] = {}
        final_error: dict[int, str] = {}

        for page_index in page_indices:
            result = primary_results.get(
                page_index,
                {
                    "status": "ERROR",
                    "text": "",
                    "error": "missing_result",
                    "elapsed": 0.0,
                    "method": "pdfplumber",
                },
            )
            final_texts[page_index] = result.get("text", "")
            final_status[page_index] = result.get("status", "ERROR")
            final_method[page_index] = result.get("method", "pdfplumber")
            final_elapsed[page_index] = float(result.get("elapsed", 0.0))
            final_error[page_index] = result.get("error", "")

        timeout_pages = [
            page_index
            for page_index in page_indices
            if final_status.get(page_index) == "TIMEOUT"
        ]

        timeout_list_path: str | None = None
        if timeout_pages:
            temp_dir = os.path.join(temp_dir_root, os.path.splitext(source_name)[0])
            timeout_list_path = os.path.join(temp_dir, "paginas_timeout.txt")
            self.write_timeout_pages_file(
                timeout_list_path,
                timeout_pages,
                total_pages,
                source_name,
            )
            logger.info(
                "Page timeout list saved. file=%s pages=%s path=%s",
                source_name,
                len(timeout_pages),
                timeout_list_path,
            )

            if fallback_enabled:
                retry_timeout = max(timeout_seconds * 2, timeout_seconds + 5)
                logger.info(
                    "Page timeout retry start. file=%s pages=%s timeout=%.2fs workers=1 engine=pdfplumber",
                    source_name,
                    len(timeout_pages),
                    retry_timeout,
                )
                retry_results = self.extract_pages_with_timeout(
                    "pdfplumber",
                    pdf_path,
                    timeout_pages,
                    retry_timeout,
                    1,
                    source_file=source_name,
                )
                for page_index in timeout_pages:
                    retry = retry_results.get(
                        page_index,
                        {
                            "status": "ERROR",
                            "text": "",
                            "error": "missing_result",
                            "elapsed": 0.0,
                            "method": "pdfplumber",
                        },
                    )
                    if retry.get("status") == "OK":
                        final_texts[page_index] = retry.get("text", "")
                        final_status[page_index] = "RECUPERADA"
                        final_method[page_index] = "pdfplumber-retry"
                        final_elapsed[page_index] = float(retry.get("elapsed", 0.0))
                        final_error[page_index] = ""
                    else:
                        final_status[page_index] = retry.get("status", "TIMEOUT")
                        final_method[page_index] = "pdfplumber-retry"
                        final_elapsed[page_index] = float(retry.get("elapsed", 0.0))
                        final_error[page_index] = retry.get("error", "")
            else:
                logger.warning(
                    "Page timeout retry skipped. file=%s",
                    source_name,
                )

        for page_index in page_indices:
            logger.info(
                "Page extraction result. file=%s page=%s method=%s status=%s elapsed=%.3fs error=%s",
                source_name,
                page_index + 1,
                final_method.get(page_index, "pdfplumber"),
                final_status.get(page_index, "ERROR"),
                final_elapsed.get(page_index, 0.0),
                final_error.get(page_index, ""),
            )

        return {
            "total_pages": total_pages,
            "page_indices": page_indices,
            "texts": final_texts,
            "status": final_status,
            "method": final_method,
            "elapsed": final_elapsed,
            "error": final_error,
            "timeout_pages": timeout_pages,
            "timeout_list_path": timeout_list_path,
        }
