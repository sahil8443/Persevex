#!/usr/bin/env python
"""Debug script to check last invoice."""

from app.database import SessionLocal, init_db
from app.models.db_models import InvoiceRecord

init_db()
session = SessionLocal()

invoices = session.query(InvoiceRecord).order_by(InvoiceRecord.created_at.desc()).limit(1).all()
if invoices:
    for inv in invoices:
        print(f'ID: {inv.id}')
        print(f'Invoice Number: {inv.invoice_number}')
        print(f'Vendor: {inv.vendor_name}')
        print(f'Total: {inv.total_amount}')
        ocr_len = len(inv.raw_ocr_text) if inv.raw_ocr_text else 0
        print(f'Raw OCR Text length: {ocr_len}')
        print(f'Is Anomaly: {inv.is_anomaly}')
        print(f'Anomaly Reason: {inv.anomaly_reason}')
        if inv.raw_ocr_text:
            print(f'Raw OCR (first 250 chars):\n{inv.raw_ocr_text[:250]}')
else:
    print('No invoices found')

session.close()
