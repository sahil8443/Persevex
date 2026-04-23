"""
Structured field extraction from raw OCR text.

Uses regex patterns first, then simple heuristics (first lines for vendor, etc.).
"""

import re
from datetime import datetime
from typing import Any

from app.schemas.invoice import LineItem, ParsedInvoice
from app.config import settings
from app.services.ner_extractor import ner_extract_fields


def _normalize_whitespace(text: str) -> str:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _parse_money(s: str) -> float | None:
    s = s.strip()
    s = re.sub(r"[$€£,\s]", "", s)
    # Handle (123.45) negative accounting style
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def _extract_invoice_number(text: str) -> str | None:
    patterns = [
        # Dataset style: "Invoice no: 51109338" / "Invoice number: ..."
        r"(?:invoice)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        r"(?:invoice|inv\.?|bill)\s*#?\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        r"(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        r"\b(INV[\-_]?\d{4,})\b",
        r"\b(\d{4,}-\d+)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_date(text: str) -> str | None:
    # Common date formats
    patterns = [
        r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",
        r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b",
        r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_vendor(text: str) -> str | None:
    # Dataset style: "Seller: <name>" (sometimes "Seller:" on same line)
    m = re.search(r"\bseller\s*[:\-]\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    if m:
        v = re.sub(r"\s+", " ", m.group(1)).strip()
        if v and len(v) >= 2:
            # Sometimes OCR merges "Seller: Client:" -> keep the seller chunk
            v = re.split(r"\bclient\s*[:\-]\b", v, flags=re.IGNORECASE)[0].strip()
            return v[:200] if v else None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    skip = re.compile(
        r"invoice|bill\s*to|ship\s*to|date|total|subtotal|tax|qty|amount|description",
        re.I,
    )
    for ln in lines[:8]:
        if len(ln) < 3 or skip.search(ln):
            continue
        if re.match(r"^[\d\s$€£.,\-/]+$", ln):
            continue
        return ln[:200]
    return None


def _extract_total(text: str) -> float | None:
    # Prefer explicit "Total" lines
    for m in re.finditer(
        r"(?:grand\s*total|amount\s*due|balance\s*due|total\s*due|total)\s*[:\-]?\s*"
        r"[$€£]?\s*([\d,]+\.?\d*)",
        text,
        re.IGNORECASE,
    ):
        v = _parse_money(m.group(1))
        if v is not None:
            return v
    # Fallback: last currency-like number on a "total" line block
    block = re.search(
        r"(total|due|balance)[^\n]{0,120}",
        text,
        re.IGNORECASE,
    )
    if block:
        nums = re.findall(r"[$€£]?\s*([\d,]+\.?\d*)", block.group(0))
        for n in reversed(nums):
            v = _parse_money(n)
            if v is not None and v > 0:
                return v
    return None


def _extract_line_items(text: str) -> list[LineItem]:
    items: list[LineItem] = []
    # Rows like: Description  2  $10.00  $20.00
    row_pat = re.compile(
        r"^(.{3,80}?)\s+(\d+(?:\.\d+)?)\s+"
        r"[$€£]?\s*([\d,]+\.?\d*)\s+[$€£]?\s*([\d,]+\.?\d*)\s*$",
        re.MULTILINE,
    )
    for m in row_pat.finditer(text):
        desc, qty_s, price_s, total_s = m.groups()
        items.append(
            LineItem(
                description=desc.strip(),
                qty=float(qty_s),
                price=_parse_money(price_s),
                line_total=_parse_money(total_s),
            )
        )
    if items:
        return items

    # Simpler: lines with qty x price = total
    simple = re.compile(
        r"^(.{3,60}?)\s+(\d+)\s*x\s*[$€£]?\s*([\d,]+\.?\d*)",
        re.IGNORECASE | re.MULTILINE,
    )
    for m in simple.finditer(text):
        items.append(
            LineItem(
                description=m.group(1).strip(),
                qty=float(m.group(2)),
                price=_parse_money(m.group(3)),
                line_total=None,
            )
        )
    return items


def parse_invoice_text(raw_text: str) -> ParsedInvoice:
    """Main entry: normalize OCR text and fill ParsedInvoice."""
    text = _normalize_whitespace(raw_text)
    inv_no = _extract_invoice_number(text)
    inv_date = _extract_date(text)
    vendor = _extract_vendor(text)
    total = _extract_total(text)
    lines = _extract_line_items(text)

    # Optional NER fallback when regex/heuristics fail.
    if settings.enable_ner and (vendor is None or inv_date is None or total is None):
        ner = ner_extract_fields(text)
        if vendor is None:
            vendor = ner.get("vendor_name") or vendor
        if inv_date is None:
            inv_date = ner.get("invoice_date") or inv_date
        if total is None and ner.get("total_amount_text"):
            total = _parse_money(str(ner["total_amount_text"])) or total

    # If total missing, sum line totals when possible
    if total is None and lines:
        sub = 0.0
        ok = True
        for li in lines:
            if li.line_total is not None:
                sub += li.line_total
            elif li.qty is not None and li.price is not None:
                sub += li.qty * li.price
            else:
                ok = False
                break
        if ok and sub > 0:
            total = round(sub, 2)

    return ParsedInvoice(
        invoice_number=inv_no,
        invoice_date=inv_date,
        vendor_name=vendor,
        total_amount=total,
        line_items=lines,
    )


def try_parse_iso_date(date_str: str | None) -> datetime | None:
    """Best-effort parse for validation; returns None if unknown format."""
    if not date_str:
        return None
    fmts = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    )
    for fmt in fmts:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
