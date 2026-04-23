"""
OpenCV-based image preprocessing for OCR.

Pipeline: BGR read → grayscale → denoise → adaptive threshold.
"""

from pathlib import Path

import cv2
import numpy as np


def preprocess_for_ocr(image_path: str | Path) -> np.ndarray:
    """
    Load an image and return a binary uint8 array optimized for Tesseract.

    Steps:
    1. Grayscale
    2. Non-local means denoising (preserves edges better than Gaussian blur)
    3. Adaptive Gaussian threshold (handles uneven lighting)
    """
    path = Path(image_path)
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Could not read image: {path}")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        2,
    )
    return binary


def save_preprocessed_preview(binary: np.ndarray, out_path: str | Path) -> None:
    """Optional: persist preprocessed image for debugging or UI preview."""
    cv2.imwrite(str(out_path), binary)
