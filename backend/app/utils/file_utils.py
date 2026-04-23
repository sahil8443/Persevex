"""Safe file naming and path helpers."""

import re
import uuid
from pathlib import Path


def safe_filename(original: str) -> str:
    """Strip dangerous characters; keep extension."""
    stem = Path(original).stem
    ext = Path(original).suffix.lower() or ".png"
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem)[:80]
    if not clean:
        clean = "invoice"
    return f"{clean}_{uuid.uuid4().hex[:8]}{ext}"
