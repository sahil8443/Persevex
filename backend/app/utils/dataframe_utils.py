"""
Utilities to build pandas DataFrames from extracted invoices.

SQLite remains the source of truth for persistence, but DataFrames are useful for:
  - analytics
  - export / reporting
  - model training feature tables
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import pandas as pd

from app.models.db_models import InvoiceRecord


def _safe_json_loads(s: str | None) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def to_dataframe(
    invoices: Iterable[InvoiceRecord],
    *,
    explode_line_items: bool = False,
) -> pd.DataFrame:
    """
    Convert InvoiceRecord rows into a pandas DataFrame.

    - If explode_line_items is False (default):
        one row per invoice, with `line_items` as a list[dict] in a single column.
    - If explode_line_items is True:
        one row per line item (invoice columns repeated), with line-item fields flattened.
    """
    base_rows: list[dict[str, Any]] = []
    for r in invoices:
        items = _safe_json_loads(r.line_items_json)
        if items is None:
            items = []
        base_rows.append(
            {
                "id": int(r.id),
                "invoice_number": r.invoice_number,
                "invoice_date": r.invoice_date,
                "vendor_name": r.vendor_name,
                "total_amount": r.total_amount,
                "line_items": items,
                "created_at": r.created_at,
                "is_anomaly": bool(r.is_anomaly),
                "anomaly_reason": r.anomaly_reason,
            }
        )

    df = pd.DataFrame(base_rows)
    if df.empty:
        # Ensure required columns exist even when empty.
        cols = [
            "id",
            "invoice_number",
            "invoice_date",
            "vendor_name",
            "total_amount",
            "line_items",
            "created_at",
            "is_anomaly",
            "anomaly_reason",
        ]
        return pd.DataFrame(columns=cols)

    if not explode_line_items:
        return df

    # Explode nested line_items -> one row per item
    df = df.explode("line_items", ignore_index=True)
    li = pd.json_normalize(df["line_items"]).add_prefix("line_item.")
    df = df.drop(columns=["line_items"]).reset_index(drop=True)
    if not li.empty:
        df = pd.concat([df, li], axis=1)
    else:
        # Add expected line-item columns even if empty
        for c in ["description", "qty", "price", "line_total"]:
            df[f"line_item.{c}"] = pd.NA
    return df

