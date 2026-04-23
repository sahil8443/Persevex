"""
Optional NER-based extraction.

This is a best-effort fallback used when regex extraction fails.
It is gated by `settings.enable_ner` and must not break the pipeline if spaCy
or the language model isn't installed.
"""

from __future__ import annotations

from typing import Any

from app.config import settings


def ner_extract_fields(text: str) -> dict[str, Any]:
    """
    Return best-effort fields:
      - vendor_name (ORG)
      - invoice_date (DATE)
      - total_amount (MONEY)
    """
    if not settings.enable_ner:
        return {}

    try:
        import spacy  # type: ignore
    except Exception:
        return {"_ner_error": "spaCy not installed"}

    try:
        nlp = spacy.load(settings.spacy_model)
    except Exception as e:
        return {"_ner_error": f"spaCy model not available: {settings.spacy_model} ({e})"}

    doc = nlp(text or "")

    vendor = None
    date = None
    money = None

    # Simple heuristics: first ORG, first DATE, largest MONEY-like number.
    money_candidates: list[tuple[float, str]] = []
    for ent in doc.ents:
        if ent.label_ == "ORG" and not vendor:
            vendor = ent.text.strip()
        elif ent.label_ == "DATE" and not date:
            date = ent.text.strip()
        elif ent.label_ == "MONEY":
            raw = ent.text.strip()
            # Extract numeric component
            num = "".join(ch for ch in raw if ch.isdigit() or ch in ".-,")
            try:
                v = float(num.replace(",", ""))
                money_candidates.append((v, raw))
            except Exception:
                continue

    if money_candidates:
        money_candidates.sort(key=lambda t: t[0], reverse=True)
        money = money_candidates[0][1]

    out: dict[str, Any] = {}
    if vendor:
        out["vendor_name"] = vendor[:200]
    if date:
        out["invoice_date"] = date[:64]
    if money:
        out["total_amount_text"] = money
    return out

