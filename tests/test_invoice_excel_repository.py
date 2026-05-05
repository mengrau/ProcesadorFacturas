from __future__ import annotations

from pathlib import Path

import openpyxl

from facturas_app.services.invoice_excel_repository import (
    EXCEL_HEADERS,
    InvoiceExcelRepository,
)


def _sample_record(
    invoice_number: str = "FV-001",
    reference: str = "123456",
    product: str = "GASEOSA MANZANA",
    total: str = "2380.00",
) -> dict[str, str]:
    return {
        "id": "abc123",
        "numero_factura": invoice_number,
        "nit_cliente": "900123456",
        "cod_cliente": "1001",
        "nombre_cliente": "Cliente Test",
        "fecha_generacion": "01/02/2025",
        "fecha_expedicion": "03/02/2025",
        "referencia": reference,
        "productos": product,
        "umv": "PZA",
        "unidades": "2",
        "precio_base_unitario": "1000.00",
        "iva": "19.00",
        "total": total,
        "estado": "OK",
    }


def _worksheet_values(excel_path: Path) -> list[tuple]:
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    return rows


def test_save_creates_excel_with_legacy_headers_and_formatted_values(
    tmp_path: Path,
) -> None:
    excel_path = tmp_path / "procesadas.xlsx"
    repository = InvoiceExcelRepository(excel_path)

    saved_path = repository.save([_sample_record()], "separado")

    rows = _worksheet_values(excel_path)

    assert saved_path == str(excel_path)
    assert rows[0] == tuple(EXCEL_HEADERS)
    assert rows[1][1] == "FV-001"
    assert rows[1][11] == "1.000,00"
    assert rows[1][13] == "2.380,00"


def test_load_existing_invoice_numbers_reads_generated_excel(tmp_path: Path) -> None:
    excel_path = tmp_path / "procesadas.xlsx"
    repository = InvoiceExcelRepository(excel_path)
    repository.save([_sample_record(invoice_number="FV-777")], "separado")

    assert repository.load_existing_invoice_numbers() == {"FV-777"}


def test_save_accumulated_mode_preserves_existing_and_deduplicates(
    tmp_path: Path,
) -> None:
    excel_path = tmp_path / "procesadas.xlsx"
    repository = InvoiceExcelRepository(excel_path)

    first_record = _sample_record(invoice_number="FV-001", reference="111111")
    duplicate_record = _sample_record(invoice_number="FV-001", reference="111111")
    new_record = _sample_record(invoice_number="FV-002", reference="222222")

    repository.save([first_record], "separado")
    repository.save([duplicate_record, new_record], "acumular")

    rows = _worksheet_values(excel_path)

    assert len(rows) == 3
    assert rows[1][1] == "FV-001"
    assert rows[2][1] == "FV-002"
    assert repository.load_existing_invoice_numbers() == {"FV-001", "FV-002"}


def test_save_keeps_bol_base_price_without_colombian_formatting(tmp_path: Path) -> None:
    excel_path = tmp_path / "procesadas.xlsx"
    repository = InvoiceExcelRepository(excel_path)
    record = _sample_record()
    record["umv"] = "BOL"
    record["precio_base_unitario"] = "1234,56"

    repository.save([record], "separado")

    rows = _worksheet_values(excel_path)

    assert rows[1][9] == "BOL"
    assert rows[1][11] == "1234.56"
