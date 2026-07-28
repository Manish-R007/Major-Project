"""
OCR for uploaded legacy claim documents (scanned pattas, old paper FRA
forms, survey sketches).

WHAT THIS DOES
----------------
Wraps `pytesseract` (a Python binding for the open-source Tesseract OCR
engine) to pull raw text out of an uploaded image or PDF page. This is
genuinely real OCR — not simulated — but it depends on the Tesseract
binary being installed on the host machine, separately from the Python
package. If it isn't installed, this module degrades gracefully: uploads
still succeed, and the document is marked `ocr_status=unavailable`
instead of the request failing.

INSTALLING TESSERACT (one-time, OS-level, not via pip)
----------------------------------------------------------
  macOS   : brew install tesseract
  Ubuntu  : sudo apt-get install tesseract-ocr
  Windows : https://github.com/UB-Mannheim/tesseract/wiki

For scanned Hindi/regional-language forms, also install the matching
language pack (e.g. `tesseract-ocr-hin` on Ubuntu) and pass
lang="hin+eng" to `extract_text_from_image`.

UPGRADING BEYOND THIS SCAFFOLD
----------------------------------
Legacy FRA forms are often handwritten and semi-structured. Plain OCR
(this module) reads printed text reasonably well but struggles with
handwriting and doesn't understand form layout. For production quality,
replace/augment this with a layout-aware model such as LayoutLMv3 or
Donut, which understands where the "claimant name" field is on the page
rather than just reading characters left to right.
"""
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


def is_ocr_available() -> bool:
    return _OCR_AVAILABLE


def extract_text_from_image(file_path: str, lang: str = "eng") -> tuple[str | None, str]:
    """
    Returns (extracted_text_or_None, status) where status is one of:
    "complete", "unavailable", "failed".
    Only handles image formats (jpg/png). PDFs are not rasterized here —
    see module docstring for the production upgrade path.
    """
    if not _OCR_AVAILABLE:
        return None, "unavailable"

    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip(), "complete"
    except Exception:
        # Covers: tesseract binary missing at runtime, corrupt image, etc.
        return None, "failed"


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def should_attempt_ocr(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS
