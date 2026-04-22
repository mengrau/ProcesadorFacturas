from __future__ import annotations

import importlib
from functools import lru_cache
from types import ModuleType


@lru_cache(maxsize=1)
def get_server_legacy() -> ModuleType:
    """Load and cache the legacy Flask module."""
    return importlib.import_module("facturas_app.legacy.server_legacy")


@lru_cache(maxsize=1)
def get_invoice_legacy() -> ModuleType:
    """Load and cache the legacy invoice processor module."""
    return importlib.import_module("facturas_app.legacy.invoice_legacy")
