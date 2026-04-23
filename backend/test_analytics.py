#!/usr/bin/env python
"""Test analytics API response."""

import requests
import json

response = requests.get("http://localhost:8000/analytics")
data = response.json()

print("Analytics Response:")
print(f"Total invoices: {data['total_invoices']}")
print(f"Anomaly count: {data['anomaly_count']}")
print(f"Vendors: {data['vendor_counts']}")
print(f"Amounts array: {data['amounts']}")
print(f"Amounts length: {len(data['amounts'])}")
print(f"\nOutliers:")
for o in data['outliers']:
    print(f"  - ID {o['id']}: {o['vendor']} = {o['amount']}")
