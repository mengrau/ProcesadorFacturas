from __future__ import annotations

from pathlib import Path
from typing import Iterable
from uuid import uuid4

from werkzeug.utils import secure_filename


class UnsafePathError(ValueError):
    """Raised when a file path escapes an allowed directory."""


def sanitize_filename(filename: str) -> str:
    """Return a safe filename suitable for local storage."""
    sanitized = secure_filename(filename or "")
    return sanitized or f"upload_{uuid4().hex}"


def is_allowed_extension(filename: str, allowed_extensions: Iterable[str]) -> bool:
    """Validate file extension against a predefined allowlist."""
    if not filename:
        return False
    lower_name = filename.lower()
    return any(lower_name.endswith(ext.lower()) for ext in allowed_extensions)


def resolve_safe_path(base_dir: Path, filename: str) -> Path:
    """Resolve a path in base_dir and block traversal attempts."""
    base = base_dir.resolve()
    target = (base / sanitize_filename(filename)).resolve()

    try:
        target.relative_to(base)
    except ValueError as exc:
        raise UnsafePathError(
            f"Path traversal blocked. base={base} target={target}"
        ) from exc

    return target


def clear_directory_files(directory: Path, suffixes: tuple[str, ...]) -> None:
    """Delete files in a directory matching allowed suffixes."""
    for item in directory.iterdir():
        if not item.is_file():
            continue
        if suffixes and item.suffix.lower() not in {s.lower() for s in suffixes}:
            continue
        item.unlink(missing_ok=True)
