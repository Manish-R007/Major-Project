import uuid
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Claim, Asset, SatelliteImage, User, UserRole, AuditLog, Scheme, SchemeRecommendation
from app.schemas import AssetOut, DetectRequest, SatelliteImageOut
from app.ai.satellite_cv import analyze_image
from app.ai.scheme_engine import score_claim_against_scheme

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

SATELLITE_UPLOAD_ROOT = Path(settings.UPLOAD_DIR) / "satellite"
SATELLITE_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp"}


def _parcel_coverage_degrees(latitude: float, area_acres: float) -> float:
    """Square imagery footprint: parcel plus enough surrounding context."""
    side_metres = math.sqrt(max(area_acres, 0.01) * 4046.8564224)
    return max((side_metres * 2.5) / (111_320 * max(math.cos(math.radians(latitude)), 0.2)), 0.002)


def _sentinel_output_size(latitude: float, coverage_deg: float) -> int:
    """Keep analysis at Sentinel-2's 10 m native detail; do not upscale pixels."""
    width_metres = coverage_deg * 111_320 * max(math.cos(math.radians(latitude)), 0.2)
    return max(32, min(512, math.ceil(width_metres / 10)))


SENTINEL_LAND_COVER = """
//VERSION=3
function setup() {
  return { input: [\"B02\", \"B03\", \"B04\", \"B08\", \"SCL\"], output: { bands: 3 } };
}
function evaluatePixel(sample) {
  // Sentinel-2 Level-2A Scene Classification (SCL): 4 vegetation, 5 bare
  // soil, 6 water. Encode these in stable analysis colours before sending the
  // image to the parcel classifier. Clouds/shadows/no-data remain neutral.
  if ([0, 1, 3, 8, 9, 10, 11].includes(sample.SCL)) return [0.5, 0.5, 0.5];
  if (sample.SCL === 6) return [0.02, 0.25, 0.85]; // water
  if (sample.SCL === 5) return [0.72, 0.58, 0.18]; // bare/harvested field
  if (sample.SCL === 4) {
    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.00001);
    return ndvi >= 0.55 ? [0.04, 0.30, 0.04] : [0.72, 0.66, 0.16];
  }
  return [0.5, 0.5, 0.5];
}
"""


def _fetch_sentinel_image(claim: Claim, coverage_deg: float) -> bytes:
    """Request a cloud-minimised Sentinel-2 L2A true-colour image from CDSE."""
    if not settings.COPERNICUS_CLIENT_ID or not settings.COPERNICUS_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Sentinel analysis is not configured. Set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET on the backend.")
    try:
        token_response = httpx.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": settings.COPERNICUS_CLIENT_ID,
                  "client_secret": settings.COPERNICUS_CLIENT_SECRET}, timeout=20,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=180)
        bbox = [claim.longitude - coverage_deg / 2, claim.latitude - coverage_deg / 2,
                claim.longitude + coverage_deg / 2, claim.latitude + coverage_deg / 2]
        output_size = _sentinel_output_size(claim.latitude, coverage_deg)
        payload = {
            "input": {"bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
                      "data": [{"type": "sentinel-2-l2a", "dataFilter": {
                          "timeRange": {"from": start.strftime("%Y-%m-%dT00:00:00Z"), "to": now.strftime("%Y-%m-%dT23:59:59Z")},
                          "mosaickingOrder": "leastCC"}}]},
            "output": {"width": output_size, "height": output_size, "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
            "evalscript": SENTINEL_LAND_COVER,
        }
        image_response = httpx.post("https://sh.dataspace.copernicus.eu/process/v1", json=payload,
                                    headers={"Authorization": f"Bearer {access_token}"}, timeout=60)
        image_response.raise_for_status()
        if not image_response.headers.get("content-type", "").startswith("image/"):
            raise ValueError("Copernicus did not return an image")
        return image_response.content
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not acquire Sentinel-2 imagery: {exc}")


def _refresh_recommendations(db: Session, claim: Claim) -> int:
    db.query(SchemeRecommendation).filter(SchemeRecommendation.claim_id == claim.id).delete()
    created = 0
    for scheme in db.query(Scheme).all():
        score, reasons = score_claim_against_scheme(claim, scheme.eligibility_rules)
        if score > 0:
            db.add(SchemeRecommendation(claim_id=claim.id, scheme_id=scheme.id, score=score, reasons=reasons))
            created += 1
    return created


def _apply_detected_land_cover(db: Session, claim: Claim, detected: list[dict]) -> int:
    """Store the dominant analysed cover and replace stale scheme matches."""
    dominant = max(detected, key=lambda item: item["area_acres"])["asset_type"]
    claim.land_type = {
        "agricultural_land": "cultivable", "forest_cover": "forest",
        "water_body": "waterlogged", "homestead": "homestead",
    }.get(dominant.value, claim.land_type)
    return _refresh_recommendations(db, claim)


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
    raise HTTPException(
        status_code=410,
        detail="Satellite images are acquired automatically from Sentinel-2; uploads are disabled.",
    )

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
    "/claims/{claim_id}/analyze-satellite",
    response_model=list[AssetOut],
    dependencies=[Depends(require_roles(
        UserRole.VILLAGE_OFFICIAL, UserRole.DISTRICT_OFFICER,
        UserRole.STATE_OFFICER, UserRole.ADMIN,
    ))],
)
def acquire_and_analyze_satellite_image(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch Sentinel-2 imagery for the parcel and analyse it; no user upload."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    coverage_deg = _parcel_coverage_degrees(claim.latitude, claim.area_acres)
    image_bytes = _fetch_sentinel_image(claim, coverage_deg)

    existing = db.query(SatelliteImage).filter(SatelliteImage.claim_id == claim.id).first()
    if existing:
        (SATELLITE_UPLOAD_ROOT / str(claim.id) / existing.stored_filename).unlink(missing_ok=True)
        db.delete(existing)
        db.flush()
    claim_dir = SATELLITE_UPLOAD_ROOT / str(claim.id)
    claim_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"sentinel2_{uuid.uuid4().hex}.png"
    image_path = claim_dir / stored_filename
    image_path.write_bytes(image_bytes)
    db.add(SatelliteImage(claim_id=claim.id, original_filename="Sentinel-2 imagery (automatic)",
                          stored_filename=stored_filename, coverage_deg=coverage_deg,
                          uploaded_by_id=current_user.id))

    db.query(Asset).filter(Asset.claim_id == claim.id, Asset.source == "satellite_cv_kmeans").delete(synchronize_session=False)
    try:
        detected = analyze_image(str(image_path), claim.id, claim.latitude, claim.longitude,
                                 claim.area_acres, coverage_deg,
                                 claim.parcel_geometry or parcel_boundary(claim.latitude, claim.longitude, claim.area_acres))
    except Exception as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Satellite image analysis failed: {exc}")
    if not detected:
        raise HTTPException(status_code=422, detail="No reliable land-cover regions were found in the satellite image.")
    for item in detected:
        db.add(Asset(claim_id=claim.id, **item))

    recommendation_count = _apply_detected_land_cover(db, claim, detected)
    db.add(AuditLog(user_id=current_user.id, action="satellite_image_acquired_and_analyzed",
                    entity_type="claim", entity_id=claim.id,
                    detail=f"Sentinel-2 image analysed; dominant={claim.land_type}; {recommendation_count} schemes matched"))
    db.commit()
    return db.query(Asset).filter(Asset.claim_id == claim.id, Asset.source == "satellite_cv_kmeans").all()


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

    # Clear existing real AI-generated assets before re-running detection.
    db.query(Asset).filter(Asset.claim_id == claim.id, Asset.source == "satellite_cv_kmeans").delete(synchronize_session=False)

    satellite_image = db.query(SatelliteImage).filter(SatelliteImage.claim_id == claim.id).first()

    if satellite_image:
        image_path = SATELLITE_UPLOAD_ROOT / str(claim.id) / satellite_image.stored_filename
        try:
            detected = analyze_image(
                str(image_path), claim.id, claim.latitude, claim.longitude,
                claim.area_acres, satellite_image.coverage_deg,
                claim.parcel_geometry or parcel_boundary(claim.latitude, claim.longitude, claim.area_acres),
            )
            detection_mode = "real_cv"
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Image analysis failed: {e}")
    else:
        raise HTTPException(status_code=409, detail="No automatically acquired satellite image exists. Use Analyze satellite image first.")

    new_assets = []
    for item in detected:
        asset = Asset(claim_id=claim.id, **item)
        db.add(asset)
        new_assets.append(asset)

    recommendation_count = _apply_detected_land_cover(db, claim, detected)
    db.add(AuditLog(user_id=current_user.id, action="asset_detection_run",
                     entity_type="claim", entity_id=claim.id,
                     detail=f"{len(new_assets)} assets detected ({detection_mode}); {recommendation_count} schemes matched"))
    db.commit()
    for a in new_assets:
        db.refresh(a)

    return new_assets
