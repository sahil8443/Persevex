"""
Build the tabular dataset used to train the Isolation Forest (alongside SQLite history).

Creates: backend/data/training/invoice_training_features.csv

Columns:
  total_amount        — raw invoice total (training converts with log1p)
  vendor_frequency    — 0–1 style relative frequency proxy (same scale as live features)
  line_item_count     — number of lines

Run from repo root:
    py scripts/generate_invoice_training_csv.py
"""

import csv
import random
from pathlib import Path


def main() -> None:
    random.seed(42)
    backend_training = (
        Path(__file__).resolve().parent.parent / "backend" / "data" / "training"
    )
    backend_training.mkdir(parents=True, exist_ok=True)
    path = backend_training / "invoice_training_features.csv"

    rows: list[dict[str, float | int]] = []
    for i in range(260):
        vendor_frequency = random.choice(
            [0.06, 0.09, 0.12, 0.16, 0.2, 0.25, 0.3, 0.38, 0.45, 0.55, 0.7, 0.88, 0.95]
        )
        line_item_count = int(
            random.choices(
                range(1, 14),
                weights=[20, 22, 18, 14, 10, 6, 4, 3, 1, 1, 1, 1, 1],
            )[0]
        )
        # Typical SMB invoice amounts (log-normal)
        total_amount = random.lognormvariate(5.05, 0.52)
        total_amount = max(total_amount, 0.01)

        # Inject a few extremes so the forest learns tail behavior
        if i % 41 == 0:
            total_amount *= random.choice([40.0, 0.03])
        if i % 53 == 0:
            vendor_frequency = random.choice([0.02, 0.99])
        if i % 67 == 0:
            line_item_count = random.choice([1, 25, 40])

        rows.append(
            {
                "total_amount": round(total_amount, 2),
                "vendor_frequency": round(vendor_frequency, 4),
                "line_item_count": line_item_count,
            }
        )

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["total_amount", "vendor_frequency", "line_item_count"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
