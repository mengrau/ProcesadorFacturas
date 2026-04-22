from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True, slots=True)
class FileIssue:
    """Represents a rejected file and its reason."""

    archivo: str
    razon: str


class ProcessingSummary(TypedDict, total=False):
    """Typed structure returned after invoice processing."""

    excel_path: str | None
    tiempos: list[dict[str, float | str]]
    archivos_rechazados: list[dict[str, str]]
    facturas_con_errores: list[dict[str, str]]
    total_seconds: float
    facturas_procesadas: int
    facturas_nuevas: int
    facturas_duplicadas: int
