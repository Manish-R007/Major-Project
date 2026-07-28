"""
Parses key fields out of OCR-extracted text from an uploaded legacy
claim document, then cross-checks them against what the claimant
declared when submitting the claim in the system.

WHAT THIS ACTUALLY DOES
--------------------------
This is genuine, functional regex-based field extraction — it looks for
label/value patterns like "Patta No: MP-BLG-0001" or "Area: 1.8 acres"
in the raw OCR text and pulls out the value. It then compares each
parsed value against the claim's own declared fields (fuzzy-matching
names, tolerant-matching area) and returns a verification status plus a
list of any mismatches.

WHAT THIS IS NOT
-------------------
It is not a layout-aware model — it has no idea where a field sits on
the page, only what text label precedes it. Legacy forms with unusual
phrasing, poor scan quality, or handwriting (which the OCR step itself
already struggles with — see app/ai/ocr.py) will often fail to parse at
all, which is why "unparseable" is a first-class status here rather
than something the caller has to guess at. A production upgrade path is
a layout-aware model (LayoutLMv3/Donut) trained on real FRA form
layouts, which understands *where* the claimant-name field is rather
than pattern-matching text that happens to precede a value.

WHY MATCH STATUS ONLY, NOT RAW TEXT, ON THE MAP
----------------------------------------------------
The WebGIS atlas is a broader-visibility surface than a single claim's
detail page. This module deliberately returns a compact status + a list
of field names that mismatched — never the raw OCR text or the parsed
values themselves — so callers building a map layer can show "⚠ name
mismatch flagged" without also having to reason about whether it's safe
to put someone's extracted personal details on a map view.
"""
import re
import difflib
import enum


class VerificationStatus(str, enum.Enum):
    MATCHED = "matched"           # every field we could parse agrees with the claim
    MISMATCH = "mismatch"         # at least one parsed field disagrees
    UNPARSEABLE = "unparseable"   # OCR text existed but no recognizable fields found
    NOT_AVAILABLE = "not_available"  # no OCR text to parse (OCR unavailable/failed, or non-image file)


_PATTA_PATTERN = re.compile(
    r"patta\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9\-\/]{4,20})", re.IGNORECASE
)
_NAME_PATTERN = re.compile(
    r"(?:claimant|name of claimant|applicant)\s*(?:name)?\s*[:\-]\s*([A-Za-z .]{3,60})",
    re.IGNORECASE,
)
_AREA_PATTERN = re.compile(
    r"area\s*[:\-]?\s*([\d]+\.?\d*)\s*(?:acres?|ac\.?)?", re.IGNORECASE
)

AREA_TOLERANCE_FRACTION = 0.15   # allow 15% difference before flagging area as a mismatch
NAME_SIMILARITY_THRESHOLD = 0.7  # difflib ratio; handles OCR noise / minor spelling differences


def parse_fields(text: str) -> dict:
    """Extracts whatever recognizable fields it can from raw OCR text."""
    if not text or not text.strip():
        return {}

    parsed = {}

    patta_match = _PATTA_PATTERN.search(text)
    if patta_match:
        parsed["patta_number"] = patta_match.group(1).strip()

    name_match = _NAME_PATTERN.search(text)
    if name_match:
        parsed["claimant_name"] = name_match.group(1).strip()

    area_match = _AREA_PATTERN.search(text)
    if area_match:
        try:
            parsed["area_acres"] = float(area_match.group(1))
        except ValueError:
            pass

    return parsed


def _names_match(a: str, b: str) -> bool:
    ratio = difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()
    return ratio >= NAME_SIMILARITY_THRESHOLD


def _area_matches(parsed_area: float, declared_area: float) -> bool:
    if declared_area == 0:
        return parsed_area == 0
    return abs(parsed_area - declared_area) / declared_area <= AREA_TOLERANCE_FRACTION


def verify_against_claim(parsed: dict, claim) -> tuple[str, list[str]]:
    """
    Compares parsed fields against the claim's declared values.
    Returns (VerificationStatus value, list of mismatched field names).
    Only fields we actually managed to parse are checked — we never
    penalize a document for a field the OCR/parser simply didn't find.
    """
    if not parsed:
        return VerificationStatus.UNPARSEABLE.value, []

    mismatches = []

    if "patta_number" in parsed:
        if parsed["patta_number"].strip().upper() != claim.patta_number.strip().upper():
            mismatches.append("patta_number")

    if "claimant_name" in parsed:
        if not _names_match(parsed["claimant_name"], claim.claimant_name):
            mismatches.append("claimant_name")

    if "area_acres" in parsed:
        if not _area_matches(parsed["area_acres"], claim.area_acres):
            mismatches.append("area_acres")

    status = VerificationStatus.MISMATCH.value if mismatches else VerificationStatus.MATCHED.value
    return status, mismatches
