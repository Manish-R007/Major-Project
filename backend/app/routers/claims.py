import uuid
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Claim, ClaimDocument, CadastralParcel, User, UserRole, ClaimType, AuditLog, OcrStatus, DocumentVerificationStatus
from app.schemas import ClaimCreate, ClaimOut, ClaimUpdateStatus, ClaimDocumentOut
from app.ai.ocr import extract_text_from_image, should_attempt_ocr
from app.ai.document_parser import parse_fields, verify_against_parcel

router = APIRouter(prefix="/api/claims", tags=["claims"])

UPLOAD_ROOT = Path(settings.UPLOAD_DIR)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp",
    "application/pdf",
}

# These are the fields shared by every local GeoJSON record. A document that
# does not identify one of these cannot be verified from backend/data.
OCR_PARCEL_FIELDS = {"state", "district", "village", "survey_number"}


@router.post("/from-document", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def create_claim_from_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a claim directly from a labelled scanned FRA/patta document."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPEG, TIFF, BMP, or PDF document.")
    if not should_attempt_ocr(file.filename):
        raise HTTPException(status_code=422, detail="Please upload a clear image scan. PDF OCR is not configured on this server.")

    contents = file.file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.")

    staging_dir = UPLOAD_ROOT / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(file.filename).suffix or ".png"
    staged_path = staging_dir / f"{uuid.uuid4().hex}{extension}"
    staged_path.write_bytes(contents)
    extracted_text, ocr_status = extract_text_from_image(str(staged_path))
    if ocr_status != OcrStatus.COMPLETE.value:
        staged_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="OCR could not read this scan. Upload a sharper, well-lit document image.")

    parsed = parse_fields(extracted_text or "")
    missing = sorted(OCR_PARCEL_FIELDS - parsed.keys())
    if missing:
        staged_path.unlink(missing_ok=True)
        readable = ", ".join(field.replace("_", " ") for field in missing)
        raise HTTPException(status_code=422, detail=f"OCR could not find: {readable}. Use a labelled claim document with these details visible.")
    parcel = db.query(CadastralParcel).filter(
        CadastralParcel.state.ilike(parsed["state"]), CadastralParcel.district.ilike(parsed["district"]),
        CadastralParcel.village.ilike(parsed["village"]), CadastralParcel.survey_number.ilike(parsed["survey_number"]),
    ).first()
    if not parcel:
        staged_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=("No official cadastral parcel was found for this survey number. "
            "An administrator must import the village GeoJSON before this claim can be mapped."))

    verification_status, mismatches = verify_against_parcel(parsed, parcel)
    if verification_status != DocumentVerificationStatus.MATCHED.value:
        staged_path.unlink(missing_ok=True)
        readable = ", ".join(field.replace("_", " ") for field in mismatches)
        raise HTTPException(status_code=422, detail=f"Document does not match the local cadastral record: {readable}.")

    # Use local-record identifiers/attributes wherever the data provides them.
    # This keeps a successful OCR claim tied to backend/data rather than an
    # unverified patta number from the upload.
    # Account/khata numbers are often only unique within a village. Prefix the
    # local identifier with its local jurisdiction and survey number so Claim's
    # globally-unique patta column remains safe across bundled datasets.
    local_key = "-".join(filter(None, [parcel.state, parcel.district, parcel.village,
                                      parcel.survey_number, parcel.record_identifier or str(parcel.id)]))
    patta_number = "LOCAL-" + re.sub(r"[^A-Za-z0-9]+", "-", local_key).strip("-").upper()[:58]
    if db.query(Claim).filter(Claim.patta_number == patta_number).first():
        staged_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="A claim already exists for this local cadastral record.")

    vertices = parcel.geometry
    latitude = sum(point[0] for point in vertices) / len(vertices)
    longitude = sum(point[1] for point in vertices) / len(vertices)
    claim = Claim(
        patta_number=patta_number,
        claimant_name=parcel.landholder_name or parsed.get("claimant_name", "Local parcel claimant"),
        claim_type=ClaimType(parsed.get("claim_type", "IFR").upper()), state=parcel.state,
        district=parcel.district, village=parcel.village, latitude=latitude,
        longitude=longitude, area_acres=parcel.area_acres or parsed["area_acres"],
        land_type=(parcel.land_type or parsed.get("land_type") or "not recorded").lower(), survey_number=parcel.survey_number,
        parcel_geometry=vertices, parcel_source="cadastral_registry", owner_id=current_user.id,
    )
    db.add(claim)
    db.flush()
    claim_dir = UPLOAD_ROOT / str(claim.id)
    claim_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    staged_path.replace(claim_dir / stored_filename)
    db.add(ClaimDocument(
        claim_id=claim.id, original_filename=file.filename, stored_filename=stored_filename,
        content_type=file.content_type, file_size_bytes=len(contents), ocr_status=OcrStatus.COMPLETE,
        extracted_text=extracted_text, verification_status=DocumentVerificationStatus.MATCHED,
        mismatched_fields=mismatches, uploaded_by_id=current_user.id,
    ))
    db.add(AuditLog(user_id=current_user.id, action="claim_created_from_ocr", entity_type="claim", entity_id=claim.id))
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def create_claim(
    payload: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if db.query(Claim).filter(Claim.patta_number == payload.patta_number).first():
        raise HTTPException(status_code=400, detail="Patta number already exists")

    claim = Claim(**payload.model_dump(), owner_id=current_user.id)
    db.add(claim)
    db.commit()
    db.refresh(claim)

    db.add(AuditLog(
        user_id=current_user.id, action="claim_created",
        entity_type="claim", entity_id=claim.id,
    ))
    db.commit()
    return claim


@router.get("/", response_model=list[ClaimOut])
def list_claims(
    state: Optional[str] = None,
    district: Optional[str] = None,
    village: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Citizens only see their own claims.
    Village/district/state officials are auto-scoped to their jurisdiction
    unless they narrow it further with query params.
    """
    query = db.query(Claim)

    if current_user.role == UserRole.CITIZEN:
        query = query.filter(Claim.owner_id == current_user.id)
    elif current_user.role == UserRole.VILLAGE_OFFICIAL:
        query = query.filter(
            Claim.state == current_user.state,
            Claim.district == current_user.district,
            Claim.village == current_user.village,
        )
    elif current_user.role == UserRole.DISTRICT_OFFICER:
        query = query.filter(
            Claim.state == current_user.state,
            Claim.district == current_user.district,
        )
    elif current_user.role == UserRole.STATE_OFFICER:
        query = query.filter(Claim.state == current_user.state)
    # ADMIN: no restriction

    if state:
        query = query.filter(Claim.state == state)
    if district:
        query = query.filter(Claim.district == district)
    if village:
        query = query.filter(Claim.village == village)
    if status_filter:
        query = query.filter(Claim.status == status_filter)

    return query.order_by(Claim.submitted_date.desc()).all()


@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if current_user.role == UserRole.CITIZEN and claim.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this claim")

    return claim


@router.patch(
    "/{claim_id}/status",
    response_model=ClaimOut,
    dependencies=[Depends(require_roles(
        UserRole.VILLAGE_OFFICIAL, UserRole.DISTRICT_OFFICER,
        UserRole.STATE_OFFICER, UserRole.ADMIN,
    ))],
)
def update_claim_status(
    claim_id: int,
    payload: ClaimUpdateStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime

    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim.status = payload.status
    claim.reviewer_notes = payload.reviewer_notes
    claim.reviewed_date = datetime.utcnow()
    db.commit()
    db.refresh(claim)

    db.add(AuditLog(
        user_id=current_user.id, action=f"claim_status_{payload.status.value}",
        entity_type="claim", entity_id=claim.id, detail=payload.reviewer_notes,
    ))
    db.commit()
    return claim


def _get_claim_or_403(claim_id: int, db: Session, current_user: User) -> Claim:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if current_user.role == UserRole.CITIZEN and claim.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this claim")
    return claim


def _find_local_parcel_for_claim(db: Session, claim: Claim) -> CadastralParcel | None:
    """Return the bundled/imported parcel backing this claim, if any."""
    if not claim.survey_number:
        return None
    return db.query(CadastralParcel).filter(
        CadastralParcel.state.ilike(claim.state),
        CadastralParcel.district.ilike(claim.district),
        CadastralParcel.village.ilike(claim.village),
        CadastralParcel.survey_number.ilike(claim.survey_number),
    ).first()


@router.post(
    "/{claim_id}/documents",
    response_model=ClaimDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_claim_document(
    claim_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a scanned legacy claim document (patta, old FRA form, survey
    sketch). Runs OCR on image files when the Tesseract engine is
    installed; otherwise stores the file and marks OCR as unavailable
    rather than failing the upload. See app/ai/ocr.py.
    """
    claim = _get_claim_or_403(claim_id, db, current_user)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
                    "Allowed: PNG, JPEG, TIFF, BMP, PDF.",
        )

    contents = file.file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Max is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    claim_dir = UPLOAD_ROOT / str(claim.id)
    claim_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    stored_path = claim_dir / stored_filename
    stored_path.write_bytes(contents)

    extracted_text = None
    ocr_status = OcrStatus.PENDING
    verification_status = DocumentVerificationStatus.NOT_AVAILABLE
    mismatched_fields = None

    if should_attempt_ocr(file.filename):
        extracted_text, status_str = extract_text_from_image(str(stored_path))
        ocr_status = OcrStatus(status_str)

        if ocr_status == OcrStatus.COMPLETE:
            parsed = parse_fields(extracted_text or "")
            parcel = _find_local_parcel_for_claim(db, claim)
            if parcel:
                verification_status_str, mismatched_fields = verify_against_parcel(parsed, parcel)
            else:
                verification_status_str, mismatched_fields = DocumentVerificationStatus.NOT_AVAILABLE.value, []
            verification_status = DocumentVerificationStatus(verification_status_str)
    else:
        # PDFs: OCR pipeline in this scaffold only reads image files directly —
        # see app/ai/ocr.py docstring for the PDF-rasterization upgrade path.
        ocr_status = OcrStatus.UNAVAILABLE

    document = ClaimDocument(
        claim_id=claim.id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        content_type=file.content_type,
        file_size_bytes=len(contents),
        ocr_status=ocr_status,
        extracted_text=extracted_text,
        verification_status=verification_status,
        mismatched_fields=mismatched_fields,
        uploaded_by_id=current_user.id,
    )
    db.add(document)
    db.add(AuditLog(
        user_id=current_user.id, action="document_uploaded",
        entity_type="claim", entity_id=claim.id,
        detail=f"{file.filename} (verification: {verification_status.value})",
    ))
    db.commit()
    db.refresh(document)
    return document


@router.get("/{claim_id}/documents", response_model=list[ClaimDocumentOut])
def list_claim_documents(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_403(claim_id, db, current_user)
    return (
        db.query(ClaimDocument)
        .filter(ClaimDocument.claim_id == claim.id)
        .order_by(ClaimDocument.uploaded_at.desc())
        .all()
    )


@router.post("/{claim_id}/documents/{document_id}/retry-ocr", response_model=ClaimDocumentOut)
def retry_document_ocr(
    claim_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reprocess an existing image after the server OCR setup is repaired."""
    claim = _get_claim_or_403(claim_id, db, current_user)
    document = (
        db.query(ClaimDocument)
        .filter(ClaimDocument.id == document_id, ClaimDocument.claim_id == claim.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not should_attempt_ocr(document.original_filename):
        document.ocr_status = OcrStatus.UNAVAILABLE
        document.extracted_text = None
        document.verification_status = DocumentVerificationStatus.NOT_AVAILABLE
        document.mismatched_fields = None
    else:
        file_path = UPLOAD_ROOT / str(claim.id) / document.stored_filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File missing from storage")

        extracted_text, status_str = extract_text_from_image(str(file_path))
        document.ocr_status = OcrStatus(status_str)
        document.extracted_text = extracted_text
        document.verification_status = DocumentVerificationStatus.NOT_AVAILABLE
        document.mismatched_fields = None

        if document.ocr_status == OcrStatus.COMPLETE:
            parsed = parse_fields(extracted_text or "")
            parcel = _find_local_parcel_for_claim(db, claim)
            if parcel:
                verification_status, mismatched_fields = verify_against_parcel(parsed, parcel)
                document.verification_status = DocumentVerificationStatus(verification_status)
                document.mismatched_fields = mismatched_fields

    db.add(AuditLog(
        user_id=current_user.id, action="document_ocr_retried",
        entity_type="claim", entity_id=claim.id,
    ))
    db.commit()
    db.refresh(document)
    return document


@router.get("/{claim_id}/documents/{document_id}/file")
def download_claim_document(
    claim_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_403(claim_id, db, current_user)
    document = (
        db.query(ClaimDocument)
        .filter(ClaimDocument.id == document_id, ClaimDocument.claim_id == claim.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = UPLOAD_ROOT / str(claim.id) / document.stored_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing from storage")

    return FileResponse(
        path=file_path,
        media_type=document.content_type or "application/octet-stream",
        filename=document.original_filename,
    )
