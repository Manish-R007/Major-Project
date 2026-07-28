import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Claim, ClaimDocument, User, UserRole, AuditLog, OcrStatus, DocumentVerificationStatus
from app.schemas import ClaimCreate, ClaimOut, ClaimUpdateStatus, ClaimDocumentOut
from app.ai.ocr import extract_text_from_image, should_attempt_ocr
from app.ai.document_parser import parse_fields, verify_against_claim

router = APIRouter(prefix="/api/claims", tags=["claims"])

UPLOAD_ROOT = Path(settings.UPLOAD_DIR)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp",
    "application/pdf",
}


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
            verification_status_str, mismatched_fields = verify_against_claim(parsed, claim)
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
