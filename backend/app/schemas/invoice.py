"""Pydantic schemas for API request/response bodies."""

from typing import Any

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = ""
    qty: float | None = None
    price: float | None = None
    line_total: float | None = None


class ParsedInvoice(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    vendor_name: str | None = None
    total_amount: float | None = None
    line_items: list[LineItem] = Field(default_factory=list)


class ValidationResult(BaseModel):
    ok: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    math_ok: bool | None = None
    date_ok: bool | None = None


class InvoiceListItem(BaseModel):
    id: int
    invoice_number: str | None
    vendor_name: str | None
    total_amount: float | None
    is_anomaly: bool
    anomaly_reason: str | None
    created_at: str


class InvoiceDetail(BaseModel):
    id: int
    file_path: str
    raw_ocr_text: str | None
    parsed: ParsedInvoice
    validation: ValidationResult
    is_anomaly: bool
    anomaly_reason: str | None
    anomaly_details: dict[str, Any] = Field(default_factory=dict)
    # Enhanced fraud signals (also duplicated inside anomaly_details for backward compatibility)
    validation_flags: dict[str, Any] = Field(default_factory=dict)
    anomaly_score: float | None = None
    duplicate_flag: bool = False
    final_risk_label: str = "Low"
    created_at: str


class InvoiceCreateResponse(BaseModel):
    id: int
    message: str
    raw_ocr_text: str = ""
    parsed: ParsedInvoice
    validation: ValidationResult
    is_anomaly: bool
    anomaly_reason: str | None
    anomaly_details: dict[str, Any] = Field(default_factory=dict)
    validation_flags: dict[str, Any] = Field(default_factory=dict)
    anomaly_score: float | None = None
    duplicate_flag: bool = False
    final_risk_label: str = "Low"


class AnalyticsResponse(BaseModel):
    total_invoices: int
    anomaly_count: int
    amounts: list[float]
    vendor_counts: dict[str, int]
    outliers: list[dict[str, Any]]
