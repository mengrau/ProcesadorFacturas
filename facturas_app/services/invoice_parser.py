from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from typing import Any

ProductTuple = tuple[str, str, str, str, str, str, str, str, str, str]


def normalize_number(value: str) -> str:
    """Normalize numeric text from Colombian/US formats to a float-friendly string."""
    if not value:
        return ""
    normalized = value.strip()
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "")
            normalized = normalized.replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
        return normalized
    if "," in normalized:
        decimal_part = normalized.split(",")[-1]
        if len(decimal_part) in (2, 3):
            return normalized.replace(",", ".")
        return normalized.replace(",", "")
    return normalized


def format_number(value: str) -> str:
    """Format a numeric value using Colombian thousands/decimal separators."""
    try:
        number = float(value)
        value_str = str(value).replace(",", ".")
        if "." in value_str:
            decimals = len(value_str.split(".")[1])
            if decimals >= 3:
                return (
                    f"{number:,.3f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

        return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return value


def extract_invoice_number(text: str) -> str | None:
    """Extract the invoice number from invoice text."""
    patterns = [
        r"FACTURA\s*(?:ELECTR[ÓO]NICA\s*DE\s*VENTA)?\s*No\.?\s*([A-Z0-9\-]+)",
        r"FACTURA\.?\s*N[°o]\s*([A-Z0-9\-]+)",
        r"FACTURA\s*DE\s*VENTA\s*No\.?\s*([A-Z0-9\-]+)",
        r"FACTURA\s+([A-Z0-9\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def normalize_customer_name(line: str) -> str:
    """Normalize a customer name line extracted from the invoice text."""
    cleaned = re.sub(r"\bGREEN\s*POINT\b", "", line, flags=re.IGNORECASE)
    upper_value = cleaned.upper()
    upper_value = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s\.]", "", upper_value)
    upper_value = re.sub(r"\s+", " ", upper_value).strip()
    return upper_value.title()


def extract_customer(text: str) -> tuple[str, str, str]:
    """Extract customer NIT, customer name and customer code from invoice text."""
    lines = [line.strip() for line in text.splitlines()]
    customer_nit = ""
    customer_name = ""
    customer_code = ""

    for index, line in enumerate(lines):
        if "CLIENTE" in line.upper():
            match = re.search(r"CLIENTE\s*:?\s*([\d\.\-]+)", line, flags=re.IGNORECASE)
            if match and not customer_nit:
                customer_nit = match.group(1).strip()

            if not customer_name:
                for next_index in range(index + 1, min(index + 6, len(lines))):
                    next_line = lines[next_index].strip()
                    if not next_line:
                        continue
                    if re.search(r"^DESPACHADO\s*A", next_line, re.IGNORECASE):
                        break
                    if re.search(r"^COD\.?\s*CLIENTE", next_line, re.IGNORECASE):
                        break
                    if re.search(r"^FECHA", next_line, re.IGNORECASE):
                        break
                    if re.match(
                        r"^(Tel|Tel\.|Teléfono|Telefono|Email|Mail|Direcci[oó]n|www\.)",
                        next_line,
                        re.IGNORECASE,
                    ):
                        continue
                    if re.match(r"^\d", next_line):
                        continue
                    customer_name = normalize_customer_name(next_line)
                    break

        if "COD. CLIENTE" in line.upper():
            match = re.search(r"COD\.?\s*CLIENTE\s*([\d]+)", line, flags=re.IGNORECASE)
            if match:
                customer_code = match.group(1).strip()

    return customer_nit, customer_name, customer_code


def extract_generation_date(text: str) -> str:
    """Extract invoice generation date from text."""
    match = re.search(
        r"FECHA\s*GENERACI[ÓO]N.*?(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        full_date = match.group(1)
        return full_date.split()[0]

    match = re.search(
        r"FECHA\s*GENERACI[ÓO]N.*?(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)

    match = re.search(
        r"FECHA\s*:?\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        full_date = match.group(1)
        return full_date.split()[0]

    match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    return match.group(1) if match else ""


def extract_expedition_date(
    text: str,
    *,
    debug_callback: Callable[[str], None] | None = None,
) -> str:
    """Extract invoice expedition date from text.

    The optional debug callback preserves legacy logging behavior without making
    the parser print by default.
    """

    def debug(message: str) -> None:
        if debug_callback is not None:
            debug_callback(message)

    debug("    [DEBUG] Extrayendo fecha de expedición...")
    debug(f"    [DEBUG] Texto a analizar (primeros 500 chars): {text[:500]}")

    def is_valid_context(value: str) -> bool:
        upper_value = value.upper()
        return not any(item in upper_value for item in ["LUGAR", "CEDI", "CIUDAD"])

    match = re.search(
        r"FECHA\s*(DE\s*)?EXPEDICI[ÓO]N\s*:?\s*(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        debug(f"    [DEBUG] Caso 1 encontrado: {match.group(2)}")
        return match.group(2)

    match = re.search(
        r"(?<!LUGAR\sDE\s)EXPEDICI[ÓO]N\s*:?\s*(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        debug(f"    [DEBUG] Caso 2 encontrado: {match.group(1)}")
        return match.group(1)

    match = re.search(
        r"FECHA\s+DE\s+EXPEDICI[ÓO]N\s*:?\s*(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        debug(f"    [DEBUG] Caso 3 encontrado: {match.group(1)}")
        return match.group(1)

    lines = text.splitlines()
    for index, line in enumerate(lines):
        line_upper = line.upper()

        if "EXPEDICI" in line_upper and "LUGAR" not in line_upper:
            debug(f"    [DEBUG] Línea candidata: '{line}'")

            match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
            if match:
                debug(f"    [DEBUG] Caso 4.1 (misma línea): {match.group(1)}")
                return match.group(1)

            window = " ".join(lines[index : index + 3])
            debug(f"    [DEBUG] Ventana analizada: '{window}'")

            match = re.search(r"(\d{2}/\d{2}/\d{4})", window)
            if match and is_valid_context(window):
                debug(f"    [DEBUG] Caso 4.2 (ventana): {match.group(1)}")
                return match.group(1)

    match = re.search(
        r"(?<!LUGAR\sDE\s)(EXPEDICI[ÓO]N|EMISI[ÓO]N|EMITIDO|FECHA\s+DE\s+EMISI[ÓO]N)[^\n]{0,50}?(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        context = text[max(0, match.start() - 50) : match.start()]
        if is_valid_context(context):
            debug(f"    [DEBUG] Caso 5 encontrado: {match.group(2)}")
            return match.group(2)

    debug("    [DEBUG] No se encontró fecha de expedición")
    return ""


def clean_product_description(description: str) -> str:
    """Clean a product description extracted from a product line."""
    cleaned = re.sub(r"^\s*\d+[\.\-\|]*", "", description)
    cleaned = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ\.\-/ ]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_products(text: str) -> list[ProductTuple]:
    """Extract invoice product lines from page text."""
    products: list[ProductTuple] = []
    lines = text.splitlines()

    def to_float_safe(value: str) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        reference_match = re.match(r"^(\d{3,6})\b", line)
        unit_match = re.search(
            r"\b(PZA|UNIDAD|SIX|Caja|BOL)\b", line, flags=re.IGNORECASE
        )
        if not reference_match or not unit_match:
            continue

        reference = reference_match.group(1)
        unit = unit_match.group(1)

        description_start = reference_match.end()
        description_end = unit_match.start()
        raw_description = line[description_start:description_end].strip()
        description = clean_product_description(raw_description)
        product = description

        numbers = re.findall(r"[\d\.,]+", line[unit_match.end() :])
        normalized_numbers = [normalize_number(number) for number in numbers]

        if len(normalized_numbers) < 3:
            continue

        quantity = normalized_numbers[0]
        base_price = normalized_numbers[1]
        subtotal = normalized_numbers[2]
        total = normalized_numbers[-1]

        iva = "0.00"
        subtotal_float = to_float_safe(subtotal)

        for number in normalized_numbers[3:]:
            numeric_value = to_float_safe(number)
            if numeric_value is not None and 0 <= numeric_value <= 100:
                iva = f"{numeric_value:.2f}"
                break

        total_float = to_float_safe(total)
        if subtotal_float is not None and (
            total_float is None or total_float < subtotal_float - 0.01
        ):
            chosen = None
            max_lookup = min(3, len(normalized_numbers))
            for offset in range(1, max_lookup + 1):
                candidate = normalized_numbers[-offset]
                candidate_float = to_float_safe(candidate)
                if candidate_float is None:
                    continue
                if candidate_float >= subtotal_float - 0.01:
                    chosen = candidate
                    break
            if chosen is None:
                chosen = normalized_numbers[-1]
            total = chosen

        if description and quantity and total:
            products.append(
                (
                    reference,
                    description,
                    unit,
                    quantity,
                    base_price,
                    iva,
                    total,
                    "OK",
                    product,
                    "",
                )
            )

    return products


class InvoiceParser:
    """Parse extracted PDF page text into invoice records."""

    def parse_pages(
        self,
        page_texts: dict[int, str] | list[str],
        *,
        seen_invoices: set[str] | None = None,
        pages_per_block: int = 100,
        mode: str = "acumular",
        source_file: str = "",
        total_pages: int | None = None,
        debug_callback: Callable[[str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse page texts preserving the legacy invoice-boundary behavior."""
        if isinstance(page_texts, list):
            texts_by_page = {index: text for index, text in enumerate(page_texts)}
            inferred_total_pages = len(page_texts)
        else:
            texts_by_page = dict(page_texts)
            inferred_total_pages = max(texts_by_page.keys(), default=-1) + 1

        total_pages = total_pages if total_pages is not None else inferred_total_pages
        pages_per_block = max(1, int(pages_per_block or 1))
        seen = seen_invoices if seen_invoices is not None else set()
        records: list[dict[str, Any]] = []

        invoice_number: str | None = None
        customer_nit, customer_name, customer_code = "", "", ""
        generation_date, expedition_date = "", ""
        accumulated_products: list[ProductTuple] = []

        def debug(message: str) -> None:
            if debug_callback is not None:
                debug_callback(message)

        def commit_invoice() -> None:
            nonlocal accumulated_products
            if not invoice_number or not accumulated_products:
                return

            should_process = False
            if mode == "separado":
                should_process = True
            elif mode == "acumular" and invoice_number not in seen:
                should_process = True
                seen.add(invoice_number)

            if not should_process:
                return

            for (
                reference,
                _description,
                unit,
                quantity,
                base_price,
                tax,
                total,
                line_status,
                product,
                _milliliters,
            ) in accumulated_products:
                records.append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "numero_factura": invoice_number,
                        "nit_cliente": customer_nit,
                        "nombre_cliente": customer_name,
                        "cod_cliente": customer_code,
                        "fecha_generacion": generation_date,
                        "fecha_expedicion": expedition_date,
                        "referencia": reference,
                        "productos": product,
                        "umv": unit,
                        "unidades": quantity,
                        "precio_base_unitario": base_price,
                        "iva": tax,
                        "total": total,
                        "estado": line_status,
                    }
                )

        for start in range(0, total_pages, pages_per_block):
            end = min(start + pages_per_block, total_pages)
            for page_index in range(start, end):
                text = texts_by_page.get(page_index, "")
                if not text.strip():
                    continue

                match = re.search(
                    r"FACTURA\s+ELECTR[ÓO]NICA\s+DE\s+VENTA\s+No\.?\s*([A-Z0-9\-]+)",
                    text,
                    flags=re.IGNORECASE,
                )
                if match:
                    new_invoice_number = match.group(1).strip()
                    if invoice_number and new_invoice_number != invoice_number:
                        commit_invoice()
                        accumulated_products = []
                    invoice_number = new_invoice_number
                    customer_nit, customer_name, customer_code = extract_customer(text)
                    generation_date = extract_generation_date(text)
                    expedition_date = extract_expedition_date(
                        text,
                        debug_callback=debug,
                    )

                products = extract_products(text)
                if products:
                    accumulated_products.extend(products)

        commit_invoice()
        return records


# Spanish aliases kept to ease gradual migration from legacy names.
normalizar_numero = normalize_number
formatear_numero = format_number
extraer_numero_factura = extract_invoice_number
normalizar_nombre_cliente = normalize_customer_name
extraer_cliente = extract_customer
extraer_fecha_generacion = extract_generation_date
extraer_fecha_expedicion = extract_expedition_date
limpiar_producto = clean_product_description
extraer_productos = extract_products
