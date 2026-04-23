#!/usr/bin/env python
"""Check what data is in the database."""

from app.database import SessionLocal, init_db
from app.models.db_models import InvoiceRecord
import json

init_db()
session = SessionLocal()

invoices = session.query(InvoiceRecord).all()
print(f"Total invoices in DB: {len(invoices)}")

total_amounts = []
vendors = set()
anomalies = 0

for inv in invoices:
    print(f"\nInvoice {inv.id}:")
    print(f"  Invoice #: {inv.invoice_number}")
    print(f"  Vendor: {inv.vendor_name}")
    print(f"  Total: {inv.total_amount}")
    print(f"  Is Anomaly: {inv.is_anomaly}")
    
    if inv.total_amount is not None:
        total_amounts.append(inv.total_amount)
    
    if inv.vendor_name:
        vendors.add(inv.vendor_name)
    
    if inv.is_anomaly:
        anomalies += 1

print(f"\n\nSummary:")
print(f"Total amounts: {total_amounts}")
print(f"Unique vendors: {len(vendors)}")
print(f"Anomalies: {anomalies}")

session.close()
