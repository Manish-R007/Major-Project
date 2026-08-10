import uuid
import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Claim, Asset, SatelliteImage, User, UserRole, AuditLog
from app.schemas import AssetOut, DetectRequest, SatelliteImageOut
from app.ai.asset_detection import detect_assets
from app.ai.satellite_cv import analyze_image

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

SATELLITE_UPLOAD_ROOT = Path(settings.UPLOAD_DIR) / "satellite"
SATELLITE_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp"}


def parcel_boundary(latitude: float, longitude: float, area_acres: float) -> list[list[float]]:
    """Square parcel outline centred at the surveyed point, scaled to its claimed area."""
    side_metres = math.sqrt(max(area_acres, 0.01) * 4046.8564224)
    lat_delta = (side_metres / 2) / 111_320
    lng_delta = (side_metres / 2) / max(111_320 * math.cos(math.radians(latitude)), 1)
    return [[latitude - lat_delta, longitude - lng_delta], [latitude - lat_delta, longitude + lng_delta],
            [latitude + lat_delta, longitude + lng_delta], [latitude + lat_delta, longitude - lng_delta]]


@router.get("/layers")
def get_atlas_layers(
    state: Optional[str] = None,
    district: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns claim points + their detected assets in a simple GeoJSON-like
    shape the frontend map layer can render directly with Leaflet.
    """
    query = db.query(Claim)

    if current_user.role == UserRole.CITIZEN:
        query = query.filter(Claim.owner_id == current_user.id)
    elif current_user.role == UserRole.VILLAGE_OFFICIAL:
        query = query.filter(Claim.state == current_user.state,
                              Claim.district == current_user.district,
                              Claim.village == current_user.village)
    elif current_user.role == UserRole.DISTRICT_OFFICER:
        query = query.filter(Claim.state == current_user.state,
                              Claim.district == current_user.district)
    elif current_user.role == UserRole.STATE_OFFICER:
        query = query.filter(Claim.state == current_user.state)

    if state:
        query = query.filter(Claim.state == state)
    if district:
        query = query.filter(Claim.district == district)

    claims = query.all()

    features = []
    for claim in claims:
        # Aggregate document verification across all uploaded documents for
        # this claim into a single status. "mismatch" wins if any document
        # flagged one — an official reviewing the map should see the worst
        # case, not an average. Deliberately exposes status only, never the
        # raw OCR text or parsed field values — see app/ai/document_parser.py
        # docstring for why the atlas (a broader-visibility surface than a
        # single claim's detail page) only gets a match/mismatch signal.
        doc_statuses = [d.verification_status.value for d in claim.documents]
        if "mismatch" in doc_statuses:
            document_status = "mismatch"
        elif "matched" in doc_statuses:
            document_status = "matched"
        elif "unparseable" in doc_statuses:
            document_status = "unparseable"
        elif doc_statuses:
            document_status = "not_available"
        else:
            document_status = "no_document"

        features.append({
            "id": claim.id,
            "patta_number": claim.patta_number,
            "claimant_name": claim.claimant_name,
            "claim_type": claim.claim_type.value,
            "status": claim.status.value,
            "state": claim.state,
            "district": claim.district,
            "village": claim.village,
            "lat": claim.latitude,
            "lng": claim.longitude,
            "area_acres": claim.area_acres,
            "parcel_geometry": claim.parcel_geometry or parcel_boundary(claim.latitude, claim.longitude, claim.area_acres),
            "parcel_source": claim.parcel_source or "estimated",
            "document_status": document_status,
            "assets": [
                {
                    "asset_type": a.asset_type.value,
                    "area_acres": a.area_acres,
                    "confidence_score": a.confidence_score,
                    "geometry": a.geometry,
                    "source": a.source,
                }
                for a in claim.assets
            ],
        })

    return {"count": len(features), "claims": features}


@router.post(
    "/claims/{claim_id}/satellite-image",
    response_model=SatelliteImageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(
        UserRole.VILLAGE_OFFICIAL, UserRole.DISTRICT_OFFICER,
        UserRole.STATE_OFFICER, UserRole.ADMIN,
    ))],
)
def upload_satellite_image(
    claim_id: int,
    coverage_deg: float = 0.01,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an aerial/satellite crop for a claim's parcel. This is what
    app/ai/satellite_cv.py analyzes when /atlas/detect is next called
    for this claim — see that module's docstring for what the analysis
    actually is (classical CV, not a trained deep-learning model).
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{file.content_type}'. Allowed: PNG, JPEG, TIFF, BMP.",
        )

    contents = file.file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Max is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # Replace any previously uploaded image for this claim - one active image per claim.
    existing = db.query(SatelliteImage).filter(SatelliteImage.claim_id == claim.id).first()
    if existing:
        old_path = SATELLITE_UPLOAD_ROOT / str(claim.id) / existing.stored_filename
        old_path.unlink(missing_ok=True)
        db.delete(existing)
        db.flush()

    claim_dir = SATELLITE_UPLOAD_ROOT / str(claim.id)
    claim_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix or ".png"
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    (claim_dir / stored_filename).write_bytes(contents)

    image = SatelliteImage(
        claim_id=claim.id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        coverage_deg=coverage_deg,
        uploaded_by_id=current_user.id,
    )
    db.add(image)
    db.add(AuditLog(user_id=current_user.id, action="satellite_image_uploaded",
                     entity_type="claim", entity_id=claim.id, detail=file.filename))
    db.commit()
    db.refresh(image)
    return image


@router.get("/claims/{claim_id}/satellite-image", response_model=Optional[SatelliteImageOut])
def get_satellite_image(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(SatelliteImage).filter(SatelliteImage.claim_id == claim_id).first()


@router.post(
    "/detect",
    response_model=list[AssetOut],
    dependencies=[Depends(require_roles(
        UserRole.VILLAGE_OFFICIAL, UserRole.DISTRICT_OFFICER,
        UserRole.STATE_OFFICER, UserRole.ADMIN,
    ))],
)
def run_asset_detection(
    payload: DetectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers asset detection for a claim.

    If an aerial/satellite image has been uploaded for this claim, this
    runs the REAL classical-CV pipeline (K-means clustering + contour
    extraction) on those actual pixels — see app/ai/satellite_cv.py.

    If no image has been uploaded, it falls back to the clearly-labeled
    SIMULATION in app/ai/asset_detection.py, so the demo still works
    end-to-end without requiring every claim to have imagery attached.
    """
    claim = db.query(Claim).filter(Claim.id == payload.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Clear existing AI-generated assets before re-running detection.
    db.query(Asset).filter(
        Asset.claim_id == claim.id,
        Asset.source.in_(["satellite_ai_simulated", "satellite_cv_kmeans"]),
    ).delete(synchronize_session=False)

    satellite_image = db.query(SatelliteImage).filter(SatelliteImage.claim_id == claim.id).first()

    if satellite_image:
        image_path = SATELLITE_UPLOAD_ROOT / str(claim.id) / satellite_image.stored_filename
        try:
            detected = analyze_image(
                str(image_path), claim.id, claim.latitude, claim.longitude,
                claim.area_acres, satellite_image.coverage_deg,
            )
            detection_mode = "real_cv"
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Image analysis failed: {e}")
    else:
        detected = detect_assets(claim.id, claim.latitude, claim.longitude,
                                  claim.area_acres, claim.land_type)
        detection_mode = "simulated"

    new_assets = []
    for item in detected:
        asset = Asset(claim_id=claim.id, **item)
        db.add(asset)
        new_assets.append(asset)

    db.add(AuditLog(user_id=current_user.id, action="asset_detection_run",
                     entity_type="claim", entity_id=claim.id,
                     detail=f"{len(new_assets)} assets detected ({detection_mode})"))
    db.commit()
    for a in new_assets:
        db.refresh(a)

    return new_assets
