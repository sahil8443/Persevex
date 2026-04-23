"""SQLAlchemy ORM models for persisted invoices."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvoiceRecord(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice_number: Mapped[str | None] = mapped_column(String(256), nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # JSON strings for portability without extra deps
    line_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    anomaly_details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
