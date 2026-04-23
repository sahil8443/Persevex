"""
Generate synthetic invoice PNG images for local testing (no Tesseract required to create files).

Run from project root:
    python scripts/generate_sample_invoices.py

Outputs to sample_data/invoices/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def write_invoice(path: Path, lines: list[str], size=(900, 1100)):
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    font = _font(22)
    title_font = _font(28)
    y = 40
    draw.text((40, y), "INVOICE", fill="black", font=title_font)
    y += 50
    for ln in lines:
        draw.text((40, y), ln, fill="black", font=font)
        y += 32
    img.save(path)


def main():
    out = Path(__file__).resolve().parent.parent / "sample_data" / "invoices"
    out.mkdir(parents=True, exist_ok=True)

    write_invoice(
        out / "invoice_acme_normal.png",
        [
            "Acme Office Supplies LLC",
            "Invoice #: INV-2024-1001",
            "Date: 2026-03-15",
            "",
            "Description          Qty   Price    Total",
            "Printer Paper A4      10   12.50    125.00",
            "Toner Cartridge        2   45.00     90.00",
            "",
            "Subtotal: 215.00",
            "Tax: 17.20",
            "Grand Total: 232.20",
        ],
    )

    write_invoice(
        out / "invoice_acme_duplicate.png",
        [
            "Acme Office Supplies LLC",
            "Invoice #: INV-2024-1001",
            "Date: 2026-03-16",
            "",
            "Description          Qty   Price    Total",
            "Printer Paper A4      10   12.50    125.00",
            "Toner Cartridge        2   45.00     90.00",
            "",
            "Grand Total: 232.20",
        ],
    )

    write_invoice(
        out / "invoice_future_date.png",
        [
            "Globex Corporation",
            "Invoice #: GLOBEX-7788",
            "Date: 2030-01-01",
            "",
            "Consulting Services    1  5000.00  5000.00",
            "Grand Total: 5000.00",
        ],
    )

    write_invoice(
        out / "invoice_outlier_amount.png",
        [
            "Initech Supplies",
            "Invoice #: INI-99999",
            "Date: 2026-02-01",
            "",
            "Industrial Laser Unit  1  999999.00  999999.00",
            "Grand Total: 999999.00",
        ],
    )

    write_invoice(
        out / "invoice_stale.png",
        [
            "Umbrella Labs",
            "Invoice #: UMB-OLD-1",
            "Date: 2024-01-10",
            "",
            "Reagents               3   200.00   600.00",
            "Grand Total: 600.00",
        ],
    )

    print(f"Wrote sample invoices to {out}")


if __name__ == "__main__":
    main()
