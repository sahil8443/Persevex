"""
Anomaly & fraud detection for invoices.

This module is intentionally self-contained so it can be used in:
  - the live OCR pipeline (per-invoice scoring)
  - offline training scripts (rebuild artifact from DB / CSV)

Outputs are designed for API consumption:
  - validation_flags (derived from ValidationResult + additional signals)
  - anomaly_score (0..1-ish risk score)
  - duplicate_flag + duplicate_matches
  - final_risk_label: Low / Medium / High
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from joblib import dump, load
from rapidfuzz import fuzz, process
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import InvoiceRecord
from app.schemas.invoice import ParsedInvoice, ValidationResult


ARTIFACT_NAME = "isolation_forest.joblib"


@dataclass(frozen=True)
class DuplicateMatch:
    id: int
    kind: str  # "exact" | "fuzzy"
    score: float | None
    invoice_number: str | None
    vendor_name: str | None
    total_amount: float | None


def _safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _artifact_path() -> Path:
    return settings.artifacts_path / ARTIFACT_NAME


def _line_item_count(parsed: ParsedInvoice) -> int:
    return int(len(parsed.line_items or []))


def _vendor_key(vendor_name: str | None) -> str:
    v = (vendor_name or "").strip()
    return v if v else "Unknown"


def normalize_vendor_name(vendor_name: str | None) -> str:
    """
    Normalization used for grouping/clustering.
    """
    v = (vendor_name or "").lower().strip()
    if not v:
        return "unknown"
    # Remove punctuation-like characters and collapse spaces.
    out = []
    last_space = False
    for ch in v:
        if ch.isalnum():
            out.append(ch)
            last_space = False
        else:
            if not last_space:
                out.append(" ")
                last_space = True
    norm = "".join(out)
    norm = " ".join(norm.split())
    return norm or "unknown"


def cluster_vendors(vendors: Iterable[str]) -> dict[str, str]:
    """
    Greedy fuzzy clustering of vendor names.

    Returns a mapping from original vendor string -> cluster_key (normalized representative).
    """
    originals = [v for v in vendors if (v or "").strip()]
    if not originals:
        return {}

    # Work in normalized space first (fast + robust).
    norm_map = {v: normalize_vendor_name(v) for v in originals}
    unique_norms = sorted(set(norm_map.values()))

    clusters: list[str] = []
    rep_for_norm: dict[str, str] = {}
    for n in unique_norms:
        if not clusters:
            clusters.append(n)
            rep_for_norm[n] = n
            continue
        best = process.extractOne(n, clusters, scorer=fuzz.ratio)
        if best and best[1] >= 92:
            rep_for_norm[n] = best[0]
        else:
            clusters.append(n)
            rep_for_norm[n] = n

    return {orig: rep_for_norm.get(norm, norm) for orig, norm in norm_map.items()}


def _amount(parsed: ParsedInvoice) -> float | None:
    return _safe_float(parsed.total_amount)


def _validation_flags(parsed: ParsedInvoice, validation: ValidationResult) -> dict[str, Any]:
    """
    Convert existing ValidationResult into structured flags suitable for scoring.
    """
    has_errors = bool(validation.errors)
    has_warnings = bool(validation.warnings)

    # Keep both detailed lists and coarse booleans.
    flags: dict[str, Any] = {
        "ok": bool(validation.ok),
        "has_errors": has_errors,
        "has_warnings": has_warnings,
        "errors": list(validation.errors or []),
        "warnings": list(validation.warnings or []),
        "math_ok": validation.math_ok,
        "date_ok": validation.date_ok,
        "missing_total_amount": _amount(parsed) is None,
        "missing_invoice_number": not bool((parsed.invoice_number or "").strip()),
        "missing_vendor_name": not bool((parsed.vendor_name or "").strip()),
        "line_item_count": _line_item_count(parsed),
    }
    return flags


def _fetch_invoice_rows(db: Session, exclude_id: int | None) -> list[InvoiceRecord]:
    q = db.query(InvoiceRecord)
    if exclude_id is not None:
        q = q.filter(InvoiceRecord.id != exclude_id)
    return q.all()


def _duplicate_detection(
    parsed: ParsedInvoice,
    db: Session,
    *,
    exclude_id: int | None,
    fuzzy_threshold: int = 92,
    amount_tolerance: float = 1.0,
) -> tuple[bool, list[DuplicateMatch]]:
    inv_no = (parsed.invoice_number or "").strip()
    amt = _amount(parsed)
    vend_norm = normalize_vendor_name(parsed.vendor_name)
    if not inv_no or amt is None:
        return False, []

    matches: list[DuplicateMatch] = []
    rows = _fetch_invoice_rows(db, exclude_id)

    for r in rows:
        r_no = (r.invoice_number or "").strip()
        r_amt = _safe_float(r.total_amount)
        r_vend_norm = normalize_vendor_name(r.vendor_name)
        if not r_no or r_amt is None:
            continue

        # Vendor is a strong signal, but OCR vendor extraction can be noisy; require either same vendor
        # OR an extremely high invoice-number similarity.
        same_vendor = (r_vend_norm == vend_norm)

        # Exact duplicate: same invoice number + amount (and usually same vendor).
        if r_no.lower() == inv_no.lower() and abs(r_amt - amt) <= amount_tolerance and same_vendor:
            matches.append(
                DuplicateMatch(
                    id=int(r.id),
                    kind="exact",
                    score=None,
                    invoice_number=r.invoice_number,
                    vendor_name=r.vendor_name,
                    total_amount=r_amt,
                )
            )
            continue

        # Fuzzy duplicate: invoice numbers very similar + amounts close; vendor should match unless
        # invoice number similarity is near-perfect.
        sim = fuzz.ratio(r_no.lower(), inv_no.lower())
        if sim >= fuzzy_threshold and abs(r_amt - amt) <= max(amount_tolerance, 0.01 * max(amt, 1.0)):
            if same_vendor or sim >= 98:
                matches.append(
                    DuplicateMatch(
                        id=int(r.id),
                        kind="fuzzy",
                        score=float(sim),
                        invoice_number=r.invoice_number,
                        vendor_name=r.vendor_name,
                        total_amount=r_amt,
                    )
                )

    duplicate_flag = len(matches) > 0
    # Prefer exact matches first, then highest similarity.
    matches.sort(key=lambda m: (0 if m.kind == "exact" else 1, -(m.score or 0.0)))
    return duplicate_flag, matches[:10]


def _vendor_zscore(
    parsed: ParsedInvoice,
    db: Session,
    *,
    exclude_id: int | None,
) -> tuple[float | None, dict[str, Any]]:
    """
    Compute per-vendor z-score from historical DB amounts.

    Returns (zscore, metadata). zscore may be None if insufficient history.
    """
    vend_raw = _vendor_key(parsed.vendor_name)
    vend_norm = normalize_vendor_name(parsed.vendor_name)
    amt = _amount(parsed)
    if amt is None:
        return None, {"vendor": vend_raw, "vendor_norm": vend_norm, "history_n": 0}

    rows = _fetch_invoice_rows(db, exclude_id)
    vendor_map = cluster_vendors([r.vendor_name or "" for r in rows])
    # Determine this invoice's cluster key. If vendor is missing, fall back to unknown.
    this_cluster = vend_norm
    if parsed.vendor_name and parsed.vendor_name in vendor_map:
        this_cluster = vendor_map[parsed.vendor_name]

    # Vendor history (clustered)
    vendor_amounts: list[float] = []
    global_amounts: list[float] = []
    for r in rows:
        a = _safe_float(r.total_amount)
        if a is None:
            continue
        global_amounts.append(a)
        key = vendor_map.get(r.vendor_name or "", normalize_vendor_name(r.vendor_name))
        if key == this_cluster:
            vendor_amounts.append(a)

    amounts = vendor_amounts if len(vendor_amounts) >= 5 else global_amounts
    scope = "vendor" if len(vendor_amounts) >= 5 else "global"
    if len(amounts) < 5:
        return None, {
            "vendor": vend_raw,
            "vendor_norm": vend_norm,
            "cluster_key": this_cluster,
            "scope": scope,
            "history_n": len(vendor_amounts),
            "global_n": len(global_amounts),
        }

    s = pd.Series(amounts, dtype="float64")
    mean = float(s.mean())
    std = float(s.std(ddof=0))
    if std <= 1e-9:
        return 0.0, {
            "vendor": vend_raw,
            "vendor_norm": vend_norm,
            "cluster_key": this_cluster,
            "scope": scope,
            "history_n": len(vendor_amounts),
            "used_n": len(amounts),
            "mean": mean,
            "std": std,
        }

    z = float((amt - mean) / std)
    return z, {
        "vendor": vend_raw,
        "vendor_norm": vend_norm,
        "cluster_key": this_cluster,
        "scope": scope,
        "history_n": len(vendor_amounts),
        "used_n": len(amounts),
        "mean": mean,
        "std": std,
    }


def _feature_frame_from_records(records: Iterable[InvoiceRecord]) -> pd.DataFrame:
    """
    Build a feature dataframe from DB rows.
    Features intentionally simple/robust against missing OCR extraction:
      - log1p(amount)
      - vendor_frequency (count of that vendor in DB)
      - line_item_count (derived from stored JSON size if possible; else 0)
    """
    rows = list(records)
    vendor_map = cluster_vendors([r.vendor_name or "" for r in rows])
    vendor_counts: dict[str, int] = {}
    for r in rows:
        key = vendor_map.get(r.vendor_name or "", normalize_vendor_name(r.vendor_name))
        vendor_counts[key] = vendor_counts.get(key, 0) + 1

    feats: list[dict[str, Any]] = []
    for r in rows:
        amt = _safe_float(r.total_amount)
        vend = vendor_map.get(r.vendor_name or "", normalize_vendor_name(r.vendor_name))
        # line_items_json is stored list[LineItem]; avoid JSON parse cost here by heuristic count.
        li_count = 0
        if r.line_items_json:
            # cheap-ish count: occurrences of "description" keys
            li_count = r.line_items_json.count('"description"')
        feats.append(
            {
                "amount": amt,
                "log_amount": math.log1p(amt) if amt is not None and amt > -1 else None,
                "vendor_frequency": float(vendor_counts.get(vend, 1)),
                "line_item_count": float(li_count),
            }
        )
    df = pd.DataFrame(feats)
    df = df.fillna({"log_amount": 0.0, "vendor_frequency": 1.0, "line_item_count": 0.0})
    return df[["log_amount", "vendor_frequency", "line_item_count"]]


def _feature_frame_for_invoice(parsed: ParsedInvoice, db: Session) -> pd.DataFrame:
    amt = _amount(parsed)
    vend_norm = normalize_vendor_name(parsed.vendor_name)
    # vendor frequency from DB using normalized clustering
    rows = _fetch_invoice_rows(db, exclude_id=None)
    vendor_map = cluster_vendors([r.vendor_name or "" for r in rows])
    this_cluster = vend_norm
    if parsed.vendor_name and parsed.vendor_name in vendor_map:
        this_cluster = vendor_map[parsed.vendor_name]
    vendor_frequency = 0.0
    for r in rows:
        key = vendor_map.get(r.vendor_name or "", normalize_vendor_name(r.vendor_name))
        if key == this_cluster:
            vendor_frequency += 1.0
    vendor_frequency = max(vendor_frequency, 1.0)
    li_count = float(_line_item_count(parsed))
    log_amount = float(math.log1p(amt)) if amt is not None and amt > -1 else 0.0
    return pd.DataFrame(
        [
            {
                "log_amount": log_amount,
                "vendor_frequency": vendor_frequency,
                "line_item_count": li_count,
            }
        ]
    )


def training_data_report(db: Session) -> dict[str, Any]:
    """
    Return counts/paths useful for CLI scripts before refresh_model_from_db().
    """
    csv_path = str(settings.training_dataset_file)
    artifact_path = str(_artifact_path())

    db_rows = db.query(InvoiceRecord).count()
    csv_rows = 0
    if settings.training_dataset_file.exists():
        try:
            csv = pd.read_csv(settings.training_dataset_file)
            csv_rows = int(len(csv))
        except Exception:
            csv_rows = 0

    # Total matrix rows is approximate because refresh_model_from_db adds bootstrap rows.
    total_matrix_rows = int(db_rows + csv_rows + 64)
    return {
        "csv_path": csv_path,
        "artifact_path": artifact_path,
        "database_rows": int(db_rows),
        "csv_rows": int(csv_rows),
        "total_matrix_rows": total_matrix_rows,
    }


def refresh_model_from_db(db: Session) -> Path:
    """
    Train an IsolationForest using:
      - features derived from InvoiceRecord rows
      - optional CSV rows at TRAINING_DATASET_PATH (if present)
      - small synthetic bootstrap for stability
    Saves to artifacts/isolation_forest.joblib and returns the path.
    """
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    out_path = _artifact_path()

    records = db.query(InvoiceRecord).all()
    X_db = _feature_frame_from_records(records)

    # Optional CSV with columns: total_amount,vendor_frequency,line_item_count
    X_csv = None
    if settings.training_dataset_file.exists():
        try:
            csv = pd.read_csv(settings.training_dataset_file)
            if {"total_amount", "vendor_frequency", "line_item_count"}.issubset(set(csv.columns)):
                amt = pd.to_numeric(csv["total_amount"], errors="coerce").fillna(0.0)
                X_csv = pd.DataFrame(
                    {
                        "log_amount": np.log1p(np.clip(amt.to_numpy(dtype="float64"), a_min=0.0, a_max=None)),
                        "vendor_frequency": pd.to_numeric(csv["vendor_frequency"], errors="coerce").fillna(1.0),
                        "line_item_count": pd.to_numeric(csv["line_item_count"], errors="coerce").fillna(0.0),
                    }
                )
        except Exception:
            X_csv = None

    # Bootstrap: helps when DB is tiny / uniform.
    rng = np.random.default_rng(7)
    boot = pd.DataFrame(
        {
            "log_amount": rng.normal(loc=math.log1p(250.0), scale=0.6, size=64),
            "vendor_frequency": rng.integers(low=1, high=12, size=64).astype("float64"),
            "line_item_count": rng.integers(low=0, high=20, size=64).astype("float64"),
        }
    )

    frames = [X_db, boot]
    if X_csv is not None and len(X_csv) > 0:
        frames.insert(1, X_csv)
    X = pd.concat(frames, ignore_index=True)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X.to_numpy(dtype="float64"))

    model = IsolationForest(
        n_estimators=300,
        contamination="auto",
        random_state=7,
    )
    model.fit(X_scaled)

    dump(
        {
            "model": model,
            "scaler": scaler,
            "feature_columns": ["log_amount", "vendor_frequency", "line_item_count"],
        },
        out_path,
    )
    return out_path


def _load_or_train_model(db: Session) -> dict[str, Any]:
    p = _artifact_path()
    if p.exists():
        try:
            return load(p)
        except Exception:
            # corrupted artifact; rebuild
            pass
    refresh_model_from_db(db)
    return load(p)


def _isoforest_score(db: Session, parsed: ParsedInvoice) -> tuple[float | None, dict[str, Any]]:
    """
    Return (score_0_1, metadata).
    Uses IsolationForest decision_function; lower means more anomalous.
    """
    amt = _amount(parsed)
    if amt is None:
        return None, {"available": False, "reason": "missing_total_amount"}

    bundle = _load_or_train_model(db)
    model: IsolationForest = bundle["model"]
    scaler: StandardScaler | None = bundle.get("scaler")

    feature_df = _feature_frame_for_invoice(parsed, db)
    X = feature_df.to_numpy(dtype="float64")
    Xs = scaler.transform(X) if scaler is not None else X
    # decision_function: higher = more normal. Typical range roughly [-0.5, 0.5] but not guaranteed.
    raw = float(model.decision_function(Xs)[0])

    # Map raw score into a 0..1-ish risk score (heuristic; stable for UI use).
    # Shift + scale then squash.
    risk = 1.0 / (1.0 + math.exp(6.0 * (raw - 0.0)))
    return float(risk), {
        "available": True,
        "raw_decision_function": raw,
        "feature_columns": list(feature_df.columns),
        "features": {k: float(v) for k, v in feature_df.iloc[0].to_dict().items()},
    }


def _final_risk_label(
    *,
    validation_flags: dict[str, Any],
    zscore: float | None,
    isoforest_risk: float | None,
    duplicate_flag: bool,
) -> str:
    """
    Combine signals into a Low/Medium/High label.
    Conservative bias: hard validation errors + duplicates push to High.
    """
    if duplicate_flag:
        return "High"
    if validation_flags.get("has_errors"):
        return "High"

    # Medium for strong statistical outliers or ML risk.
    if zscore is not None and abs(float(zscore)) > 3.0:
        return "Medium"
    if isoforest_risk is not None and float(isoforest_risk) >= 0.85:
        return "Medium"

    # Warnings (old invoice date, unparsed date, missing total) get Medium if combined with some ML signal.
    if validation_flags.get("has_warnings") and isoforest_risk is not None and float(isoforest_risk) >= 0.65:
        return "Medium"

    return "Low"


def detect_anomalies(
    parsed: ParsedInvoice,
    validation: ValidationResult,
    db: Session,
    *,
    exclude_id: int | None,
) -> tuple[bool, str | None, dict[str, Any]]:
    """
    Main scoring entrypoint used by the live pipeline.

    Returns:
      (is_anomaly, anomaly_reason, anomaly_details)
    """
    flags = _validation_flags(parsed, validation)
    dup_flag, dup_matches = _duplicate_detection(parsed, db, exclude_id=exclude_id)

    z, zmeta = _vendor_zscore(parsed, db, exclude_id=exclude_id)
    ml_risk, isof_meta = _isoforest_score(db, parsed)

    # Always provide a stable combined anomaly_score for downstream systems.
    score = 0.0
    if z is not None:
        score = max(score, min(1.0, abs(float(z)) / 6.0))
    if ml_risk is not None:
        score = max(score, float(ml_risk))
    if flags.get("has_errors"):
        score = max(score, 0.95)
    if dup_flag:
        score = 1.0

    label = _final_risk_label(
        validation_flags=flags,
        zscore=z,
        isoforest_risk=ml_risk,
        duplicate_flag=dup_flag,
    )

    # Reason is a compact “primary driver” string used in list views.
    if dup_flag:
        reason = "duplicate"
    elif flags.get("has_errors"):
        reason = "validation_error"
    elif z is not None and abs(float(z)) > 3.0:
        reason = "amount_outlier_zscore"
    elif ml_risk is not None and float(ml_risk) >= 0.85:
        reason = "amount_outlier_ml"
    else:
        reason = None

    details: dict[str, Any] = {
        "validation_flags": flags,
        "duplicate_flag": bool(dup_flag),
        "duplicate_matches": [
            {
                "id": m.id,
                "kind": m.kind,
                "score": m.score,
                "invoice_number": m.invoice_number,
                "vendor_name": m.vendor_name,
                "total_amount": m.total_amount,
            }
            for m in dup_matches
        ],
        "zscore": z,
        "zscore_meta": zmeta,
        "anomaly_score": float(score),
        "ml_anomaly_score": ml_risk,
        "ml_meta": isof_meta,
        "final_risk_label": label,
    }

    is_anomaly = label in {"Medium", "High"}
    return is_anomaly, reason, details