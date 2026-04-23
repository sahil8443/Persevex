"""
Start the API from the backend folder (fixes import path and uses your venv).

Usage (PowerShell):
    cd backend
    .\\.venv\\Scripts\\activate
    python launch.py

Or without activating venv:
    .\\.venv\\Scripts\\python launch.py
"""

import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    # Ensure local .env is loaded (TESSDATA_PREFIX / TESSERACT_CMD for OCR).
    load_dotenv()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
