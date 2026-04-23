"""
End-to-end pipeline: preprocess → OCR → parse → validate → anomaly detection.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.invoice import ParsedInvoice, ValidationResult
from app.services.anomaly_detector import detect_anomalies
from app.services.ocr_engine import extract_text_from_array, extract_text_from_file
from app.services.parser import parse_invoice_text
from app.services.preprocessing import preprocess_for_ocr
from app.services.validator import validate_invoice, validation_dict_for_storage

logger = logging.getLogger(__name__)


def process_invoice_image(image_path: str | Path, session: Session) -> dict[str, Any]:
    """
    Run full processing on a saved image file.

    Uses OpenCV preprocessing when possible; falls back to direct Tesseract on the file
    (helps with some PDFs or unusual encodings).

    Returns dict with keys: ocr_text, parsed, validation, is_anomaly, anomaly_reason, anomaly_details
    """
    path = Path(image_path)
    ocr_text = ""
    try:
        binary = preprocess_for_ocr(path)
        ocr_text = extract_text_from_array(binary)
    except ValueError:
        # e.g. unreadable by OpenCV — try whole-file OCR
        ocr_text = extract_text_from_file(path)
    except RuntimeError:
        # Configuration errors (tesseract/tessdata). Re-raise as-is for API handling.
        raise
    except Exception as e:
        logger.exception("OCR preprocessing/OCR failed for %s", str(path))
        raise RuntimeError(f"OCR failed: {e!s}") from e
    if not (ocr_text or "").strip():
        ocr_text = extract_text_from_file(path)
    parsed = parse_invoice_text(ocr_text)
    validation = validate_invoice(parsed)
    is_anom, reason, details = detect_anomalies(parsed, validation, session, exclude_id=None)

    # Ensure keys are always present for downstream consumers.
    details = details or {}

    return {
        "ocr_text": ocr_text,
        "parsed": parsed,
        "validation": validation,
        "is_anomaly": is_anom,
        "anomaly_reason": reason,
        "anomaly_details": details,
        # Convenience fields expected by callers / API responses
        "validation_flags": details.get("validation_flags", validation_dict_for_storage(validation)),
        "anomaly_score": details.get("anomaly_score", 0.0),
        "duplicate_flag": bool(details.get("duplicate_flag", False)),
        "final_risk_label": str(details.get("final_risk_label", "Low")),
        "validation_dict": validation_dict_for_storage(validation),
    }
