from __future__ import annotations

from pathlib import Path

from facturas_app.utils.file_security import (
    clear_directory_files,
    is_allowed_extension,
    resolve_safe_path,
    sanitize_filename,
)


def test_sanitize_filename_returns_safe_name() -> None:
    unsafe = "../..\\factura final?.pdf"
    safe = sanitize_filename(unsafe)
    assert safe
    assert "/" not in safe
    assert "\\" not in safe


def test_is_allowed_extension_respects_allowlist() -> None:
    allowed = (".pdf", ".xlsx")
    assert is_allowed_extension("archivo.PDF", allowed)
    assert not is_allowed_extension("archivo.exe", allowed)


def test_resolve_safe_path_stays_inside_base(tmp_path: Path) -> None:
    resolved = resolve_safe_path(tmp_path, "../../data.pdf")
    assert resolved.parent == tmp_path.resolve()


def test_clear_directory_files_by_suffix(tmp_path: Path) -> None:
    keep_file = tmp_path / "keep.txt"
    delete_pdf = tmp_path / "a.pdf"
    delete_xlsx = tmp_path / "b.xlsx"

    keep_file.write_text("x", encoding="utf-8")
    delete_pdf.write_text("x", encoding="utf-8")
    delete_xlsx.write_text("x", encoding="utf-8")

    clear_directory_files(tmp_path, (".pdf", ".xlsx"))

    assert keep_file.exists()
    assert not delete_pdf.exists()
    assert not delete_xlsx.exists()
