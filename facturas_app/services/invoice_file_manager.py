from __future__ import annotations

import random
import shutil
import time
from collections.abc import Callable


class InvoiceFileManager:
    """Resilient file operations used by invoice processing workflows."""

    def __init__(
        self,
        *,
        message_callback: Callable[[str], None] | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
        gc_collect_func: Callable[[], None] | None = None,
    ) -> None:
        self._message_callback = message_callback
        self._sleep = sleep_func
        self._gc_collect = gc_collect_func

    def _message(self, text: str) -> None:
        if self._message_callback is not None:
            self._message_callback(text)

    def move_file_securely(
        self,
        source: str,
        destination: str,
        max_attempts: int = 5,
    ) -> bool:
        """Move a file with retries to handle transient file locks on Windows."""
        for attempt in range(max_attempts):
            try:
                shutil.move(source, destination)
                self._message(
                    f"    [OK] Archivo movido exitosamente en intento {attempt + 1}"
                )
                return True
            except (PermissionError, OSError) as exc:
                self._message(
                    f"    [WARN] Intento {attempt + 1}/{max_attempts} falló: {exc}"
                )
                if attempt < max_attempts - 1:
                    wait_seconds = random.uniform(1.0, 3.0) + (attempt * 0.5)
                    self._message(
                        f"    [WAIT] Esperando {wait_seconds:.1f} segundos antes del siguiente intento..."
                    )
                    self._sleep(wait_seconds)

                    if self._gc_collect is not None:
                        try:
                            self._gc_collect()
                        except Exception:
                            pass
                    else:
                        try:
                            import gc

                            gc.collect()
                        except Exception:
                            pass
                else:
                    self._message(
                        f"    [ERROR] No se pudo mover el archivo después de {max_attempts} intentos"
                    )
                    self._message(
                        "    [INFO] Sugerencia: Cierra cualquier programa que pueda estar usando el archivo"
                    )
                    return False
        return False


def move_file_securely(
    source: str,
    destination: str,
    *,
    max_attempts: int = 5,
    message_callback: Callable[[str], None] | None = None,
) -> bool:
    """Compatibility helper for secure file moves."""
    return InvoiceFileManager(message_callback=message_callback).move_file_securely(
        source,
        destination,
        max_attempts=max_attempts,
    )
