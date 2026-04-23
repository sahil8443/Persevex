"""
Offline training for the Isolation Forest anomaly detector.

Uses:
  - All historical rows from SQLite (derived features)
  - Rows from TRAINING_DATASET_PATH CSV (default: data/training/invoice_training_features.csv)
  - A small synthetic bootstrap for numerical stability

Usage (from backend/ directory, venv active):
    python -m app.ml.train_model

Regenerate the CSV (optional) from repo root:
    py scripts/generate_invoice_training_csv.py

If you have invoice images, prefer:
    python -m app.ml.import_and_train
"""

from app.database import SessionLocal, init_db
from app.services.anomaly_detector import refresh_model_from_db, training_data_report


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
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
