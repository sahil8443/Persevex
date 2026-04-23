"""
FastAPI application entry point.

Run from `backend/`:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes.invoices import ensure_app_dirs, router as invoices_router
from app.services.ocr_engine import ocr_readiness

logging.basicConfig(level=getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_app_dirs()
    init_db()
    # Startup self-check: don't block API startup, but ensure OCR readiness is visible.
    app.state.ocr_status = ocr_readiness()
    yield


app = FastAPI(
    title="Invoice Processing & Fraud Detection API",
    description="OCR, validation, and ML anomaly detection for invoices.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Run the API with:  cd backend  &&  python -m app.main
# (Requires dependencies in the active environment; prefer backend/launch.py or uvicorn.)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
