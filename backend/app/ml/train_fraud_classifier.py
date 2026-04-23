"""
Train/evaluate a supervised fraud classifier using the provided label file.

Inputs:
  - backend/invoice_labels_sample.csv
      columns: invoice_image_name,label (0=normal,1=fraud)
  - backend/data/batch_1/batch_1/batch1_*.csv
      columns: File Name, Json Data, OCRed Text

The sample label file uses names like inv_0001.jpg. The dataset images use names
like batch1-0001.jpg. We map inv_XXXX.jpg → batch1-XXXX.jpg and join to ground-truth
JSON rows from the dataset CSVs.

Features (simple but effective):
  - amount_total (sum of item total_price)
  - line_item_count
  - vendor_frequency (relative frequency of seller_name in labeled subset)

Outputs:
  - backend/artifacts/fraud_classifier.joblib
  - prints accuracy, precision, recall, F1, ROC-AUC on a stratified holdout set

Run (from backend/, venv active):
  python -m app.ml.train_fraud_classifier
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]  # backend/app/ml -> backend/


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


def compute_total_amount(gt: dict[str, Any]) -> float | None:
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
        total += float(v)
        saw = True
    return round(total, 2) if saw else None


def norm(s: str | None) -> str:
    return (s or "").strip().lower()


def map_inv_to_batch(name: str) -> str:
    """
    inv_0001.jpg -> batch1-0001.jpg
    If pattern doesn't match, return original.
    """
    n = name.strip()
    if n.lower().startswith("inv_") and len(n) >= 8:
        core = n[4:8]
        if core.isdigit():
            return f"batch1-{core}.jpg"
    return n


def load_dataset_index() -> dict[str, dict[str, Any]]:
    """
    Build mapping: filename -> ground truth json dict
    from batch1_1.csv, batch1_2.csv, batch1_3.csv.
    """
    base = ROOT / "data" / "batch_1" / "batch_1"
    csvs = [base / "batch1_1.csv", base / "batch1_2.csv", base / "batch1_3.csv"]
    idx: dict[str, dict[str, Any]] = {}
    for p in csvs:
        if not p.is_file():
            continue
        with p.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fn = (row.get("File Name") or "").strip()
                raw = row.get("Json Data") or ""
                if not fn or not raw:
                    continue
                try:
                    gt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                idx[fn] = gt
    return idx


def main() -> None:
    label_path = ROOT / "invoice_labels_sample.csv"
    if not label_path.is_file():
        raise SystemExit(f"Label file not found: {label_path}")

    idx = load_dataset_index()
    if not idx:
        raise SystemExit("Dataset index is empty. Expected batch1_*.csv under backend/data/batch_1/batch_1/")

    # Load labels and join
    rows: list[tuple[str, int, dict[str, Any]]] = []
    with label_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            inv_name = (r.get("invoice_image_name") or "").strip()
            y_raw = (r.get("label") or "").strip()
            if not inv_name or y_raw not in {"0", "1"}:
                continue
            mapped = map_inv_to_batch(inv_name)
            gt = idx.get(mapped)
            if not gt:
                continue
            rows.append((mapped, int(y_raw), gt))

    if len(rows) < 30:
        raise SystemExit(
            f"Only matched {len(rows)} labeled samples to dataset CSVs. "
            "Check naming / mapping between invoice_labels_sample.csv and batch1-XXXX.jpg."
        )

    # Compute vendor frequency within labeled subset
    vendor_counts: dict[str, int] = {}
    for _fn, _y, gt in rows:
        inv = gt.get("invoice") or {}
        seller = norm(inv.get("seller_name") if isinstance(inv, dict) else None)
        vendor_counts[seller] = vendor_counts.get(seller, 0) + 1
    max_c = max(vendor_counts.values(), default=1)

    X_list: list[list[float]] = []
    y_list: list[int] = []
    kept_names: list[str] = []

    for fn, y, gt in rows:
        inv = gt.get("invoice") or {}
        seller = norm(inv.get("seller_name") if isinstance(inv, dict) else None)
        amount = compute_total_amount(gt)
        items = gt.get("items") or []
        line_count = len(items) if isinstance(items, list) else 0
        vendor_freq = (vendor_counts.get(seller, 0) / max_c) if seller else 0.0

        # Basic feature cleanup
        amt = float(amount) if amount is not None else 0.0
        X_list.append([math.log1p(max(amt, 0.0)), vendor_freq, float(line_count)])
        y_list.append(int(y))
        kept_names.append(fn)

    X = np.array(X_list, dtype=float)
    y = np.array(y_list, dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    clf = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
        ]
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else float("nan")

    out_path = ROOT / "artifacts" / "fraud_classifier.joblib"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": clf,
            "features": ["log1p_total_amount", "vendor_frequency", "line_item_count"],
            "label_path": str(label_path),
            "matched_samples": int(len(rows)),
        },
        out_path,
    )

    print("Supervised fraud classifier evaluation")
    print(f"Matched labeled samples: {len(rows)}")
    print(f"Holdout size: {len(y_test)}")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1:        {f1:.4f}")
    print(f"ROC-AUC:   {auc:.4f}")
    print(f"Saved model: {out_path}")


if __name__ == "__main__":
    main()

