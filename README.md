# Invoice Processing & Fraud Detection System

Production-style monorepo: **FastAPI** backend (OCR, rules, scikit-learn Isolation Forest, SQLite), **React + Vite + Tailwind** dashboard (Recharts), and scripts for **sample invoice images**.

## Folder structure

```
persevex/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + CORS + lifespan
│   │   ├── config.py               # Settings from .env
│   │   ├── database.py             # SQLAlchemy engine & sessions
│   │   ├── routes/
│   │   │   └── invoices.py         # REST endpoints
│   │   ├── services/
│   │   │   ├── preprocessing.py    # OpenCV grayscale / denoise / threshold
│   │   │   ├── ocr_engine.py       # pytesseract
│   │   │   ├── parser.py           # Regex + heuristics → structured fields
│   │   │   ├── validator.py        # Math + date rules
│   │   │   ├── anomaly_detector.py  # Isolation Forest + z-score + fuzzy duplicates
│   │   │   └── invoice_pipeline.py
│   │   ├── models/
│   │   │   └── db_models.py
│   │   ├── schemas/
│   │   │   └── invoice.py
│   │   ├── ml/
│   │   │   └── train_model.py      # Offline retrain → artifacts/
│   │   └── utils/
│   │       └── file_utils.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── data/                       # SQLite file (created at runtime)
│   ├── uploads/                    # Uploaded images
│   └── artifacts/                # Trained isolation_forest.joblib
├── frontend/
│   ├── package.json
│   ├── vite.config.js              # Dev proxy → :8000
│   ├── tailwind.config.js
│   └── src/                        # Pages: Upload, Dashboard, Detail, Analytics
├── scripts/
│   └── generate_sample_invoices.py # Renders PNG invoices with Pillow
├── sample_data/invoices/           # Generated sample PNGs (after running script)
└── README.md
```

## Prerequisites

- **Python 3.11+** (3.10+ should work; tested with 3.13 via `py -3` on Windows)
- **Node.js 18+**
- **Tesseract OCR** installed and on `PATH`  
  - Windows: install from [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki) or the official installer, then optionally set `TESSERACT_CMD` in `.env` to the full path of `tesseract.exe`.

## Backend setup

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

If `python` is not on your PATH, use `py -3` instead of `python` for all commands below.

Edit `.env` if needed (database path, `TESSERACT_CMD`, CORS origins).

### Run API

Do **not** open `app/main.py` and click Run in the IDE with the system Python: dependencies live in the venv and imports expect the **`backend`** folder as the working directory.

**Recommended** (from `backend/`):

```powershell
cd backend
.\.venv\Scripts\python.exe launch.py
```

Equivalent:

```powershell
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: `GET /health`

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload-invoice` | Multipart file field `file` — processes and stores invoice |
| GET | `/invoices` | List invoices |
| GET | `/invoice/{id}` | Detail + validation + anomaly metadata |
| GET | `/analytics` | Aggregates for charts |

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies API calls to port **8000**.

### Production build

```powershell
cd frontend
npm run build
npm run preview
```

Set `VITE_API_URL` to your API origin if the UI is not served with a proxy (e.g. `VITE_API_URL=https://api.example.com`).

## Sample invoice images

From the **repository root** (with backend venv active so `Pillow` is available):

```powershell
cd c:\Users\Admin\Desktop\persevex
.\backend\.venv\Scripts\activate
pip install pillow
python scripts\generate_sample_invoices.py
```

Files are written to `sample_data/invoices/`. Upload them from the UI to exercise **normal**, **duplicate**, **future date**, **extreme amount**, and **stale date** scenarios (exact flags depend on OCR quality and parser).

## Train / refresh the ML model

The service **auto-creates** `artifacts/isolation_forest.joblib` on first use (bootstrap + DB history). After importing many invoices, retrain from the database:

```powershell
cd backend
.\.venv\Scripts\activate
python -m app.ml.train_model
```

### Train from your invoice image dataset (`backend/data/batch_*`)

If you already have invoice images under `backend/data/batch_1`, `batch_2`, `batch_3`, the most faithful training path is:

- **bulk import** all images through the same pipeline used by `/upload-invoice`
- **persist** parsed invoices to SQLite
- **train** the IsolationForest model from the resulting feature rows

Run:

```powershell
cd backend
.\.venv\Scripts\activate
python -m app.ml.import_and_train
```

If your dataset is in different folders, set `TRAINING_IMAGE_DIRS` in `backend/.env` (comma-separated).

This fits **IsolationForest** on features: `log1p(amount)`, normalized **vendor frequency**, and **line item count** (same features used at inference).

## Anomaly reasons

| `anomaly_reason` | Meaning |
|------------------|---------|
| `date_issue` | Rule engine: e.g. future invoice date |
| `duplicate` | Fuzzy vendor / number match with similar amount to an existing row |
| `amount_outlier` | Isolation Forest outlier and/or extreme amount z-score |

## Environment variables

See `backend/.env.example`:

- `DATABASE_URL` — default SQLite file under `backend/data/`
- `UPLOAD_DIR`, `ARTIFACTS_DIR`
- `TESSERACT_CMD` — optional explicit path to Tesseract
- `CORS_ORIGINS` — comma-separated origins for the SPA

## Notes

- **OCR quality** depends on image resolution and Tesseract language packs; this project uses default English.
- **PDFs**: some PDFs are not readable by OpenCV; the pipeline falls back to Tesseract on the file. Multi-page PDFs are not specially handled.
- **Security**: For real production, add authentication, virus scanning on uploads, and move storage to object storage (S3, etc.).

## License

MIT (demo project).
