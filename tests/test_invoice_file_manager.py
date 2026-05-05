from __future__ import annotations

from pathlib import Path

from facturas_app.services import invoice_file_manager
from facturas_app.services.invoice_file_manager import (
    InvoiceFileManager,
    move_file_securely,
)


def test_move_file_securely_moves_file_on_first_try(tmp_path: Path) -> None:
    source = tmp_path / "origen.txt"
    destination = tmp_path / "destino.txt"
    source.write_text("ok", encoding="utf-8")

    manager = InvoiceFileManager()

    moved = manager.move_file_securely(str(source), str(destination))

    assert moved is True
    assert destination.exists()
    assert destination.read_text(encoding="utf-8") == "ok"
    assert not source.exists()


def test_move_file_securely_retries_and_succeeds(monkeypatch) -> None:
    calls: dict[str, int] = {"move": 0, "sleep": 0, "gc": 0}

    def fake_move(_source: str, _destination: str) -> None:
        calls["move"] += 1
        if calls["move"] == 1:
            raise PermissionError("locked")

    def fake_sleep(_seconds: float) -> None:
        calls["sleep"] += 1

    def fake_gc_collect() -> None:
        calls["gc"] += 1

    monkeypatch.setattr(invoice_file_manager.shutil, "move", fake_move)
    monkeypatch.setattr(invoice_file_manager.random, "uniform", lambda _a, _b: 0.0)

    manager = InvoiceFileManager(sleep_func=fake_sleep, gc_collect_func=fake_gc_collect)

    moved = manager.move_file_securely("a.txt", "b.txt", max_attempts=3)

    assert moved is True
    assert calls["move"] == 2
    assert calls["sleep"] == 1
    assert calls["gc"] == 1


def test_move_file_securely_returns_false_after_all_attempts_fail(monkeypatch) -> None:
    calls: dict[str, int] = {"move": 0, "sleep": 0}

    def fake_move(_source: str, _destination: str) -> None:
        calls["move"] += 1
        raise OSError("still locked")

    def fake_sleep(_seconds: float) -> None:
        calls["sleep"] += 1

    monkeypatch.setattr(invoice_file_manager.shutil, "move", fake_move)
    monkeypatch.setattr(invoice_file_manager.random, "uniform", lambda _a, _b: 0.0)

    manager = InvoiceFileManager(sleep_func=fake_sleep)
    moved = manager.move_file_securely("a.txt", "b.txt", max_attempts=3)

    assert moved is False
    assert calls["move"] == 3
    assert calls["sleep"] == 2


def test_move_file_securely_emits_messages_when_callback_is_defined(
    tmp_path: Path,
) -> None:
    messages: list[str] = []
    source = tmp_path / "origen.txt"
    destination = tmp_path / "destino.txt"
    source.write_text("ok", encoding="utf-8")

    manager = InvoiceFileManager(message_callback=messages.append)
    manager.move_file_securely(str(source), str(destination))

    assert any("Archivo movido exitosamente" in message for message in messages)


def test_functional_helper_uses_manager_and_moves_file(tmp_path: Path) -> None:
    source = tmp_path / "origen.txt"
    destination = tmp_path / "destino.txt"
    source.write_text("ok", encoding="utf-8")

    moved = move_file_securely(str(source), str(destination))

    assert moved is True
    assert destination.exists()
