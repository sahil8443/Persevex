"""
OCR extraction using Tesseract (via pytesseract).

This project targets production-style invoice OCR. For reliable results, install
Tesseract OCR on the host machine. On Windows, we auto-detect common install
paths; otherwise set TESSERACT_CMD in `backend/.env`.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

from app.config import settings

_WINDOWS_TESSERACT_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def resolve_tesseract_executable() -> str | None:
    """Return path to tesseract binary, or None if not found."""
    if settings.tesseract_cmd:
        p = Path(settings.tesseract_cmd)
        if p.is_file():
            return str(p)
    found = shutil.which("tesseract")
    if found:
        return found
    if platform.system() == "Windows":
        for cand in _WINDOWS_TESSERACT_CANDIDATES:
            if Path(cand).is_file():
                return cand
    return None


def _candidate_tessdata_dirs(tesseract_exe: str | None) -> list[Path]:
    """
    Return candidate *tessdata* directories.

    Tesseract expects language files like `eng.traineddata` to live under a `tessdata` dir.
    `TESSDATA_PREFIX` can point to either:
      - the parent directory containing `tessdata/`, OR
      - the `tessdata/` directory itself
    """
    out: list[Path] = []

    # Highest priority: explicit setting (from backend/.env)
    if settings.tessdata_prefix:
        p = Path(settings.tessdata_prefix)
        out.append(p / "tessdata")
        out.append(p)

    # Next: environment variable (in case host sets it)
    env = os.environ.get("TESSDATA_PREFIX") or os.environ.get("tessdata_prefix")
    if env:
        p = Path(env)
        out.append(p / "tessdata")
        out.append(p)

    # Derive from executable location: .../Tesseract-OCR/tesseract.exe -> .../Tesseract-OCR/tessdata
    if tesseract_exe:
        exe_path = Path(tesseract_exe)
        out.append(exe_path.parent / "tessdata")

    # Common Windows install locations
    if platform.system() == "Windows":
        out.extend(
            [
                Path(r"C:\Program Files\Tesseract-OCR\tessdata"),
                Path(r"C:\Program Files (x86)\Tesseract-OCR\tessdata"),
            ]
        )

    # De-dupe while preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        sp = str(p.resolve()) if p.exists() else str(p)
        if sp in seen:
            continue
        seen.add(sp)
        uniq.append(p)
    return uniq


def resolve_tessdata_dir() -> Path | None:
    """
    Return the tessdata directory that contains `eng.traineddata`, or None.
    """
    exe = resolve_tesseract_executable()
    for p in _candidate_tessdata_dirs(exe):
        try:
            if p.is_dir() and (p / "eng.traineddata").is_file():
                return p
        except OSError:
            continue
    return None


def ocr_readiness() -> dict[str, Any]:
    """
    Return a structured readiness status for OCR.
    """
    exe = resolve_tesseract_executable()
    tessdata = resolve_tessdata_dir()
    if exe and tessdata:
        status = "READY"
    elif exe and not tessdata:
        status = "PARTIAL"
    else:
        status = "FAILED"
    return {
        "status": status,
        "tesseract_exe": exe or "",
        "tessdata_dir": str(tessdata) if tessdata else "",
        "has_eng_traineddata": bool(tessdata),
        "hint": (
            ""
            if status == "READY"
            else "Install Tesseract language data (eng.traineddata) and set TESSDATA_PREFIX to your tessdata folder."
        ),
    }


def _configure_tesseract() -> None:
    exe = resolve_tesseract_executable()
    if not exe:
        raise RuntimeError(
            "tesseract is not installed or it's not in your PATH. "
            "Install Tesseract (Windows: UB Mannheim build) or set TESSERACT_CMD in backend/.env."
        )
    pytesseract.pytesseract.tesseract_cmd = exe

    # Ensure language data exists; without this, pytesseract raises a confusing runtime error.
    tessdata = resolve_tessdata_dir()
    if not tessdata:
        raise RuntimeError(
            "Tesseract executable was found, but language data is missing. "
            "Could not locate `eng.traineddata`. "
            "Fix by installing the English language pack and setting TESSDATA_PREFIX in backend/.env "
            "to the folder containing `tessdata` (or to `tessdata` itself)."
        )
    # Point tesseract to the directory containing traineddata files.
    os.environ["TESSDATA_PREFIX"] = str(tessdata)


def extract_text_from_array(binary_image: np.ndarray) -> str:
    """Run Tesseract on a numpy image (binary/grayscale is recommended)."""
    _configure_tesseract()
    pil = Image.fromarray(binary_image)
    return pytesseract.image_to_string(pil, config="--psm 6") or ""


def extract_text_with_confidence_from_array(binary_image: np.ndarray) -> tuple[str, float | None]:
    """
    Return (text, mean_confidence) where mean_confidence is 0..100, or None if unavailable.
    """
    _configure_tesseract()
    pil = Image.fromarray(binary_image)
    text = pytesseract.image_to_string(pil, config="--psm 6") or ""
    try:
        data = pytesseract.image_to_data(pil, config="--psm 6", output_type=Output.DICT)
        confs = []
        for c in data.get("conf", []) or []:
            try:
                v = float(c)
                if v >= 0:
                    confs.append(v)
            except Exception:
                continue
        mean_conf = float(np.mean(confs)) if confs else None
    except Exception:
        mean_conf = None
    return text, mean_conf


def extract_text_from_file(image_path: str | Path) -> str:
    """Run Tesseract on an image file via PIL."""
    _configure_tesseract()
    path = Path(image_path)
    pil = Image.open(path).convert("RGB")
    return pytesseract.image_to_string(pil, config="--psm 6") or ""


def extract_text_with_confidence_from_file(image_path: str | Path) -> tuple[str, float | None]:
    _configure_tesseract()
    path = Path(image_path)
    pil = Image.open(path).convert("RGB")
    text = pytesseract.image_to_string(pil, config="--psm 6") or ""
    try:
        data = pytesseract.image_to_data(pil, config="--psm 6", output_type=Output.DICT)
        confs = []
        for c in data.get("conf", []) or []:
            try:
                v = float(c)
                if v >= 0:
                    confs.append(v)
            except Exception:
                continue
        mean_conf = float(np.mean(confs)) if confs else None
    except Exception:
        mean_conf = None
    return text, mean_conf
