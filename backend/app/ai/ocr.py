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


# Keep the language files alongside the application so OCR does not depend on
# write access to the system-wide Tesseract installation (Program Files is
# commonly protected on Windows).
TESSDATA_DIR = Path(__file__).resolve().parents[2] / "tessdata"


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
        config = f'--tessdata-dir "{TESSDATA_DIR}"' if TESSDATA_DIR.is_dir() else ""
        text = pytesseract.image_to_string(image, lang=lang, config=config)
        return text.strip(), "complete"
    except pytesseract.TesseractNotFoundError:
        # The Python package can be installed even when the Tesseract binary
        # is not. This is an environment limitation, not a bad upload.
        return None, "unavailable"
    except pytesseract.TesseractError as error:
        # A Tesseract installation without its requested language data (for
        # example eng.traineddata) raises TesseractError. Treat that exactly
        # like a missing engine so the UI does not report a misleading upload
        # failure to the claimant.
        message = str(error).lower()
        unavailable_markers = (
            "error opening data file",
            "failed loading language",
            "couldn't load any languages",
            "could not initialize tesseract",
        )
        if any(marker in message for marker in unavailable_markers):
            return None, "unavailable"
        return None, "failed"
    except (OSError, ValueError):
        # Covers unreadable/corrupt image files without leaking internal
        # exception details to the API response.
        return None, "failed"


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def should_attempt_ocr(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS
