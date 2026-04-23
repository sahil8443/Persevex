"""
Rule-based validation: mathematical consistency and invoice date rules.
"""

from datetime import datetime, timedelta
from typing import Any

from app.schemas.invoice import LineItem, ParsedInvoice, ValidationResult
from app.services.parser import try_parse_iso_date


def _sum_line_items(line_items: list[LineItem]) -> float | None:
    if not line_items:
        return None
    total = 0.0
    for li in line_items:
        if li.line_total is not None:
            total += li.line_total
        elif li.qty is not None and li.price is not None:
            total += li.qty * li.price
        else:
            return None
    return round(total, 2)


def validate_invoice(parsed: ParsedInvoice, tolerance: float = 1.5) -> ValidationResult:
    """
    Validate:
    - Line items sum vs declared total (within tolerance for rounding/OCR noise)
    - Invoice date not in the future
    - Invoice date not older than 90 days (warning-level for fraud heuristics)
    """
    errors: list[str] = []
    warnings: list[str] = []
    math_ok: bool | None = None
    date_ok: bool | None = None

    # Per-line integrity: (qty * unit price) ~= line_total when all are present
    line_mismatch = 0
    for i, li in enumerate(parsed.line_items):
        if li.qty is None or li.price is None or li.line_total is None:
            continue
        expected = round(float(li.qty) * float(li.price), 2)
        if abs(expected - float(li.line_total)) > max(0.05, tolerance / 10):
            line_mismatch += 1
            errors.append(
                f"Line {i+1} integrity failed: qty*price ({expected}) != line_total ({li.line_total})."
            )

    computed = _sum_line_items(parsed.line_items)
    if parsed.total_amount is not None and computed is not None:
        diff = abs(computed - parsed.total_amount)
        math_ok = diff <= tolerance
        if not math_ok:
            errors.append(
                f"Line items sum ({computed}) does not match total ({parsed.total_amount})."
            )
    elif parsed.total_amount is None:
        warnings.append("Total amount not extracted; skipping math check.")
        math_ok = None
    elif not parsed.line_items:
        math_ok = True

    today = datetime.utcnow().date()
    parsed_dt = try_parse_iso_date(parsed.invoice_date)
    if parsed_dt is None and parsed.invoice_date:
        warnings.append(f"Could not parse invoice date: {parsed.invoice_date}")
        date_ok = None
    elif parsed_dt is not None:
        d = parsed_dt.date()
        if d > today:
            errors.append("Invoice date is in the future.")
            date_ok = False
        else:
            date_ok = True
            if today - d > timedelta(days=90):
                warnings.append("Invoice date is more than 90 days old.")

    ok = len(errors) == 0
    return ValidationResult(
        ok=ok,
        errors=errors,
        warnings=warnings,
        math_ok=math_ok,
        date_ok=date_ok,
    )


def validation_dict_for_storage(v: ValidationResult) -> dict[str, Any]:
    return v.model_dump()
