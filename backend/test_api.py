#!/usr/bin/env python
"""Test the API response directly."""

import json
import requests
from pathlib import Path

# Find an uploaded invoice to use for the test
upload_dir = Path("uploads")
files = list(upload_dir.glob("*.png")) + list(upload_dir.glob("*.jpg"))

if files:
    test_file = files[0]
    print(f"Testing POST /upload-invoice with: {test_file}")
    
    with open(test_file, "rb") as f:
        files_payload = {"file": f}
        response = requests.post("http://localhost:8000/upload-invoice", files=files_payload)
    
    print(f"Status: {response.status_code}")
    print(f"Response text (first 2000 chars):")
    print(response.text[:2000])
    
    if response.status_code == 200:
        data = response.json()
        print("\nParsed response keys:", list(data.keys()))
        print("raw_ocr_text present:", "raw_ocr_text" in data)
        print("parsed present:", "parsed" in data)
        if "parsed" in data:
            print("parsed keys:", list(data["parsed"].keys()) if data["parsed"] else "None")
else:
    print("No uploaded files found")
