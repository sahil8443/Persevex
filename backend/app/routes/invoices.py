"""Invoice upload, listing, detail, and analytics endpoints."""

import csv
import io
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.db_models import InvoiceRecord
from app.utils.dataframe_utils import to_dataframe
from app.schemas.invoice import (
    AnalyticsResponse,
    InvoiceCreateResponse,
    InvoiceDetail,
    InvoiceListItem,
    LineItem,
    ParsedInvoice,
    ValidationResult,
)
from app.services.invoice_pipeline import process_invoice_image
from app.services.ocr_engine import ocr_readiness
from app.utils.file_utils import safe_filename

router = APIRouter(prefix="", tags=["invoices"])


def ensure_app_dirs() -> None:
    """Create upload, artifact, DB, and training-data parent directories."""
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    settings.training_dataset_file.parent.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        rel = settings.database_url.replace("sqlite:///", "")
        if not rel.startswith(":"):
            p = Path(rel)
            if p.parent != Path("."):
                p.parent.mkdir(parents=True, exist_ok=True)


@router.get("/ocr-status")
def ocr_status():
    r = ocr_readiness()
    return r


@router.post("/upload-invoice", response_model=InvoiceCreateResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Accept an invoice image, run OCR + parsing + validation + anomaly detection, persist row.
    """
    ensure_app_dirs()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    fname = safe_filename(file.filename)
    dest = settings.upload_path / fname
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    dest.write_bytes(content)

    try:
        result = process_invoice_image(dest, db)
    except RuntimeError as e:
        # OCR engine errors (most commonly missing Tesseract)
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {e!s}") from e

    parsed: ParsedInvoice = result["parsed"]
    validation: ValidationResult = result["validation"]

    row = InvoiceRecord(
        file_path=str(dest),
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
    db.commit()
    db.refresh(row)

    return InvoiceCreateResponse(
        id=row.id,
        message="Invoice processed successfully",
        raw_ocr_text=result["ocr_text"] or "",
        parsed=parsed,
        validation=validation,
        is_anomaly=row.is_anomaly,
        anomaly_reason=row.anomaly_reason,
        anomaly_details=json.loads(row.anomaly_details_json or "{}"),
        validation_flags=result.get("validation_flags") or {},
        anomaly_score=result.get("anomaly_score"),
        duplicate_flag=bool(result.get("duplicate_flag") or False),
        final_risk_label=str(result.get("final_risk_label") or "Low"),
    )


@router.get("/invoices", response_model=list[InvoiceListItem])
def list_invoices(db: Session = Depends(get_db)):
    rows = db.query(InvoiceRecord).order_by(InvoiceRecord.created_at.desc()).all()
    return [
        InvoiceListItem(
            id=r.id,
            invoice_number=r.invoice_number,
            vendor_name=r.vendor_name,
            total_amount=r.total_amount,
            is_anomaly=r.is_anomaly,
            anomaly_reason=r.anomaly_reason,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/invoice/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    r = db.query(InvoiceRecord).filter(InvoiceRecord.id == invoice_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Invoice not found")

    items_raw: list[dict[str, Any]] = []
    if r.line_items_json:
        try:
            items_raw = json.loads(r.line_items_json)
        except json.JSONDecodeError:
            items_raw = []

    line_items = [LineItem.model_validate(it) for it in items_raw] if items_raw else []

    val_dict: dict[str, Any] = {}
    if r.validation_json:
        try:
            val_dict = json.loads(r.validation_json)
        except json.JSONDecodeError:
            val_dict = {}

    validation = ValidationResult.model_validate(val_dict) if val_dict else ValidationResult()

    parsed = ParsedInvoice(
        invoice_number=r.invoice_number,
        invoice_date=r.invoice_date,
        vendor_name=r.vendor_name,
        total_amount=r.total_amount,
        line_items=line_items,
    )

    ad: dict[str, Any] = {}
    if r.anomaly_details_json:
        try:
            ad = json.loads(r.anomaly_details_json)
        except json.JSONDecodeError:
            ad = {}

    return InvoiceDetail(
        id=r.id,
        file_path=r.file_path,
        raw_ocr_text=r.raw_ocr_text,
        parsed=parsed,
        validation=validation,
        is_anomaly=r.is_anomaly,
        anomaly_reason=r.anomaly_reason,
        anomaly_details=ad,
        validation_flags=(ad or {}).get("validation_flags") or {},
        anomaly_score=(ad or {}).get("anomaly_score"),
        duplicate_flag=bool((ad or {}).get("duplicate_flag") or False),
        final_risk_label=str((ad or {}).get("final_risk_label") or ("Medium" if r.is_anomaly else "Low")),
        created_at=r.created_at.isoformat() if r.created_at else "",
    )


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    rows = db.query(InvoiceRecord).all()
    df = to_dataframe(rows, explode_line_items=False)
    amounts = [float(x) for x in df["total_amount"].dropna().tolist()] if not df.empty else []
    vendor_counts = (
        df["vendor_name"].fillna("Unknown").astype(str).value_counts().to_dict() if not df.empty else {}
    )

    outliers = [
        {
            "id": r.id,
            "vendor": r.vendor_name,
            "amount": r.total_amount,
            "reason": r.anomaly_reason,
        }
        for r in rows
        if r.is_anomaly
    ]

    return AnalyticsResponse(
        total_invoices=len(rows),
        anomaly_count=sum(1 for r in rows if r.is_anomaly),
        amounts=amounts,
        vendor_counts=vendor_counts,
        outliers=outliers,
    )


@router.get("/export-dataset")
def export_dataset(db: Session = Depends(get_db)):
    """
    Export all processed invoices as a CSV file.
    
    Columns:
    - invoice_number
    - invoice_date
    - vendor_name
    - total_amount
    - is_anomaly (True/False)
    - anomaly_reason
    """
    rows = db.query(InvoiceRecord).all()
    
    if not rows:
        return StreamingResponse(
            iter([""]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=invoice_dataset.csv"}
        )
    
    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "invoice_id",
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "total_amount",
        "is_anomaly",
        "anomaly_reason",
    ])
    
    # Write data rows
    for row in rows:
        writer.writerow([
            row.id,
            row.invoice_number or "",
            row.invoice_date or "",
            row.vendor_name or "",
            row.total_amount or "",
            str(row.is_anomaly),
            row.anomaly_reason or "",
        ])
    
    # Convert to byte stream
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoice_dataset.csv"}
    )
