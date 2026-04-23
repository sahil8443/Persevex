"""Application configuration from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/invoices.db"
    upload_dir: str = "./uploads"
    artifacts_dir: str = "./artifacts"
    # If empty, pytesseract uses system PATH
    tesseract_cmd: str = ""
    # Optional: points to the *directory containing* the `tessdata` folder,
    # or directly to the `tessdata` folder itself. If empty, we auto-detect.
    tessdata_prefix: str = ""
    # Toggle optional NER fallback for extraction
    enable_ner: bool = False
    spacy_model: str = "en_core_web_sm"
    log_level: str = "INFO"
    # Extra rows for IsolationForest training (CSV with header: total_amount,vendor_frequency,line_item_count)
    training_dataset_path: str = "./data/training/invoice_training_features.csv"
    # Directories containing invoice images for bulk import/training
    training_image_dirs: str = "./data/batch_1,./data/batch_2,./data/batch_3"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def artifacts_path(self) -> Path:
        return Path(self.artifacts_dir).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def training_dataset_file(self) -> Path:
        p = Path(self.training_dataset_path)
        if not p.is_absolute():
            # Resolve relative to backend/ when cwd is backend
            return p.resolve()
        return p

    @property
    def training_image_dirs_list(self) -> list[Path]:
        parts = [p.strip() for p in (self.training_image_dirs or "").split(",") if p.strip()]
        out: list[Path] = []
        for part in parts:
            pp = Path(part)
            out.append(pp.resolve() if not pp.is_absolute() else pp)
        return out


settings = Settings()
