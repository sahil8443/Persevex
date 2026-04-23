"""
Evaluate invoice field extraction accuracy using the provided dataset CSVs.

Dataset format (as seen in backend/data/batch_1/batch_1/batch1_*.csv):
  - File Name
  - Json Data   (ground truth invoice structure)
  - OCRed Text  (OCR output text)

This script evaluates the parser (regex + heuristics) on OCRed Text against Json Data.

Usage (from backend/, venv active):
  python -m app.ml.evaluate_extraction

Notes:
  - This computes extraction accuracy, not fraud/anomaly detection accuracy.
  - Fraud/anomaly labels are not present in the dataset CSVs.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.services.parser import parse_invoice_text


def norm(s: str | None) -> str:
    return (s or "").strip().lower()


def safe_float(x) -> float | None:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def approx_equal(a: float | None, b: float | None, tol: float = 0.01) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def json_total_amount(gt: dict) -> float | None:
    items = gt.get("items") or []
    if not isinstance(items, list):
        return None
    total = 0.0
    saw = False
    for it in items:
        if not isinstance(it, dict):
            continue
        v = safe_float(it.get("total_price"))
        if v is None:
            continue
        total += v
        saw = True
    return round(total, 2) if saw else None


@dataclass
class Counts:
    n: int = 0
    inv_no_ok: int = 0
    date_ok: int = 0
    vendor_ok: int = 0
    total_ok: int = 0
    line_count_ok: int = 0


def evaluate_csv(csv_path: Path, limit: int | None = None) -> Counts:
    c = Counts()
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if limit is not None and c.n >= limit:
                break

            gt_raw = row.get("Json Data") or ""
            ocr_text = row.get("OCRed Text") or ""
            try:
                gt = json.loads(gt_raw)
            except json.JSONDecodeError:
                continue

            inv = gt.get("invoice") or {}
            if not isinstance(inv, dict):
                inv = {}

            gt_inv_no = norm(inv.get("invoice_number"))
            gt_date = norm(inv.get("invoice_date"))
            gt_vendor = norm(inv.get("seller_name"))
            gt_total = json_total_amount(gt)
            gt_line_count = len(gt.get("items") or []) if isinstance(gt.get("items"), list) else None

            parsed = parse_invoice_text(ocr_text)
            pred_inv_no = norm(parsed.invoice_number)
            pred_date = norm(parsed.invoice_date)
            pred_vendor = norm(parsed.vendor_name)
            pred_total = parsed.total_amount
            pred_line_count = len(parsed.line_items) if parsed.line_items is not None else 0

            c.n += 1
            if gt_inv_no and pred_inv_no and gt_inv_no == pred_inv_no:
                c.inv_no_ok += 1
            if gt_date and pred_date and gt_date == pred_date:
                c.date_ok += 1
            # Vendor names can vary in OCR; token containment heuristic
            if gt_vendor and pred_vendor:
                if gt_vendor == pred_vendor or (gt_vendor in pred_vendor) or (pred_vendor in gt_vendor):
                    c.vendor_ok += 1
            if gt_total is not None and pred_total is not None and approx_equal(gt_total, float(pred_total), tol=0.05):
                c.total_ok += 1
            if gt_line_count is not None and gt_line_count == pred_line_count:
                c.line_count_ok += 1

    return c


def pct(x: int, n: int) -> float:
    return 0.0 if n <= 0 else (100.0 * x / n)


def main() -> None:
    base = Path(__file__).resolve().parents[2] / "data" / "batch_1" / "batch_1"
    files = [base / "batch1_1.csv", base / "batch1_2.csv", base / "batch1_3.csv"]
    files = [p for p in files if p.is_file()]
    if not files:
        raise SystemExit(f"No dataset CSVs found at {base}")

    total = Counts()
    for p in files:
        c = evaluate_csv(p)
        total.n += c.n
        total.inv_no_ok += c.inv_no_ok
        total.date_ok += c.date_ok
        total.vendor_ok += c.vendor_ok
        total.total_ok += c.total_ok
        total.line_count_ok += c.line_count_ok

    n = total.n
    # Macro average across the fields we can realistically extract from OCRed Text in this dataset.
    # (Totals/line items are often not present as explicit values in OCRed Text for these samples.)
    field_accs = [
        total.inv_no_ok / n if n else 0,
        total.date_ok / n if n else 0,
        total.vendor_ok / n if n else 0,
    ]
    macro = (sum(field_accs) / len(field_accs)) if n else 0.0

    print("Extraction evaluation (parser vs dataset JSON ground truth)")
    print(f"Samples: {n}")
    print(f"Invoice number exact match: {total.inv_no_ok}/{n} ({pct(total.inv_no_ok, n):.2f}%)")
    print(f"Invoice date exact match:   {total.date_ok}/{n} ({pct(total.date_ok, n):.2f}%)")
    print(f"Vendor name match:          {total.vendor_ok}/{n} ({pct(total.vendor_ok, n):.2f}%)")
    print(f"Macro avg (3 fields):       {macro*100:.2f}%")
    print()
    print("Fraud/anomaly detection accuracy:")
    print("- Not computable from these CSVs because they do not include a fraud/anomaly label.")


if __name__ == "__main__":
    main()

