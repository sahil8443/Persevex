"""
Bulk import invoice images from backend/data batches into SQLite, then train the model.

This is the recommended way to "train from invoice images" because it uses the same
OCR → parsing → validation pipeline as the live `/upload-invoice` endpoint.

Prerequisite: Tesseract must be installed (or TESSERACT_CMD set in backend/.env).

Usage (from backend/, venv active):
    python -m app.ml.import_and_train

Configuration:
    TRAINING_IMAGE_DIRS in .env (comma-separated) defaults to:
      ./data/batch_1,./data/batch_2,./data/batch_3
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import settings
from app.database import SessionLocal, init_db
from app.models.db_models import InvoiceRecord
from app.services.anomaly_detector import refresh_model_from_db, training_data_report
from app.services.invoice_pipeline import process_invoice_image


def iter_invoice_images(dirs: list[Path]) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
    out: list[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for root, _sub, files in os.walk(d):
            for fn in files:
                p = Path(root) / fn
                if p.suffix.lower() in exts:
                    out.append(p)
    return out


def main() -> None:
    init_db()
    # Ensure training dirs exist (but don't create batches)
    settings.training_dataset_file.parent.mkdir(parents=True, exist_ok=True)

    dirs = settings.training_image_dirs_list
    print(f"Using TRAINING_IMAGE_DIRS={settings.training_image_dirs}", flush=True)
    images = iter_invoice_images(dirs)
    print(f"Found {len(images)} invoice images across: {[str(d) for d in dirs]}", flush=True)

    db = SessionLocal()
    imported = 0
    skipped = 0
    failed = 0
    try:
        existing_paths = {p for (p,) in db.query(InvoiceRecord.file_path).all()}
        print(f"Existing DB rows: {len(existing_paths)}", flush=True)
        for p in images:
            sp = str(p)
            if sp in existing_paths:
                skipped += 1
                if (skipped + imported + failed) % 500 == 0:
                    print(
                        f"Progress {skipped + imported + failed}/{len(images)} "
                        f"(imported={imported}, skipped={skipped}, failed={failed})",
                        flush=True,
                    )
                continue

            try:
                result = process_invoice_image(p, db)
            except RuntimeError as e:
                # OCR engine errors (most commonly missing Tesseract)
                raise SystemExit(str(e)) from e
            except Exception:
                failed += 1
                if (skipped + imported + failed) % 200 == 0:
                    print(
                        f"Progress {skipped + imported + failed}/{len(images)} "
                        f"(imported={imported}, skipped={skipped}, failed={failed})",
                        flush=True,
                    )
                continue

            parsed = result["parsed"]
            row = InvoiceRecord(
                file_path=sp,
                raw_ocr_text=result["ocr_text"],
                invoice_number=parsed.invoice_number,
                invoice_date=parsed.invoice_date,
                vendor_name=parsed.vendor_name,
                total_amount=parsed.total_amount,
                line_items_json=json.dumps([li.model_dump() for li in parsed.line_items]),
                validation_json=json.dumps(result["validation_dict"]),
                is_anomaly=result["is_anomaly"],
                anomaly_reason=result["anomaly_reason"],
                anomaly_details_json=json.dumps(result["anomaly_details"]),
            )
            db.add(row)
            # Commit in chunks to keep memory bounded
            if (imported + 1) % 100 == 0:
                db.commit()
                print(f"Processed {imported + 1}/{len(images)} (imported={imported + 1}, skipped={skipped}, failed={failed})", flush=True)
            imported += 1
            existing_paths.add(sp)

        db.commit()
        print(f"Imported: {imported}, skipped(existing): {skipped}, failed: {failed}")

        before = training_data_report(db)
        refresh_model_from_db(db)
        print("Isolation Forest trained and saved.")
        print(f"  CSV dataset: {before['csv_path']}")
        print(f"  Rows from database (feature rows): {before['database_rows']}")
        print(f"  Rows from CSV: {before['csv_rows']}")
        print(f"  Total training matrix rows (incl. bootstrap): {before['total_matrix_rows']}")
        print(f"  Artifact: {before['artifact_path']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

