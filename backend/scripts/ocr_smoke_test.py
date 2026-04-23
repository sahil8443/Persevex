"""
OCR + parsing + validation + risk smoke test.

Runs against 2–3 sample invoice images and writes debug artifacts:
  - raw OCR output text files
  - preprocessed preview images

Usage (from backend/):
  .venv\\Scripts\\python.exe scripts\\ocr_smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script while keeping absolute imports (`from app...`) working.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.database import SessionLocal, init_db
from app.services.invoice_pipeline import process_invoice_image
from app.services.ocr_engine import ocr_readiness
from app.services.preprocessing import preprocess_for_ocr, save_preprocessed_preview


def pick_images() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    candidates = []
    for p in (root / "data").rglob("*"):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
            candidates.append(p)
    # Prefer batch images if present
    candidates.sort(key=lambda p: (0 if "batch_" in str(p) else 1, str(p)))
    return candidates[:3]


def main() -> None:
    r = ocr_readiness()
    print("OCR readiness:", r)
    if r["status"] != "READY":
        raise SystemExit("OCR is not READY. Fix Tesseract/tessdata configuration first.")

    init_db()
    db = SessionLocal()
    try:
        images = pick_images()
        if not images:
            raise SystemExit("No sample images found under backend/data/.")

        debug_dir = Path("data") / "ocr_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)

        for i, img in enumerate(images, start=1):
            print("\n===", i, "===", img)
            try:
                binary = preprocess_for_ocr(img)
                save_preprocessed_preview(binary, debug_dir / f"{img.stem}.preprocessed.png")
            except Exception as e:
                print("Preprocess failed:", e)

            result = process_invoice_image(img, db)
            ocr_text = result.get("ocr_text") or ""
            (debug_dir / f"{img.stem}.ocr.txt").write_text(ocr_text, encoding="utf-8", errors="ignore")

            parsed = result["parsed"].model_dump()
            validation = result["validation"].model_dump()

            print("parsed:", parsed)
            print("validation.ok:", validation.get("ok"), "errors:", len(validation.get("errors") or []))
            print(
                "risk:",
                {
                    "final_risk_label": result.get("final_risk_label"),
                    "duplicate_flag": result.get("duplicate_flag"),
                    "anomaly_score": result.get("anomaly_score"),
                    "reason": result.get("anomaly_reason"),
                },
            )
            print("saved:", debug_dir / f"{img.stem}.ocr.txt")

    finally:
        db.close()


if __name__ == "__main__":
    main()

