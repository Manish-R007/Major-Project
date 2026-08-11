"""Import authorised village cadastral data used for OCR-to-parcel matching."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import CadastralParcel, User, UserRole

router = APIRouter(prefix="/api/cadastral", tags=["cadastral"])


def _value(properties: dict, key: str) -> str:
    value = properties.get(key) or properties.get(key.upper()) or properties.get(key.title())
    return str(value).strip() if value is not None else ""


@router.post("/import", dependencies=[Depends(require_roles(UserRole.ADMIN))])
def import_cadastral_geojson(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load a GeoJSON FeatureCollection with state, district, village and survey_number properties."""
    try:
        geojson = json.loads(file.file.read())
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Upload a valid GeoJSON file.")
    features = geojson.get("features", [])
    if geojson.get("type") != "FeatureCollection" or not features:
        raise HTTPException(status_code=400, detail="GeoJSON must be a non-empty FeatureCollection.")

    imported = 0
    rejected = []
    for index, feature in enumerate(features, start=1):
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        required = {key: _value(properties, key) for key in ("state", "district", "village", "survey_number")}
        if not all(required.values()) or geometry.get("type") != "Polygon":
            rejected.append(index)
            continue
        rings = geometry.get("coordinates") or []
        if not rings or len(rings[0]) < 3:
            rejected.append(index)
            continue
        # GeoJSON is [longitude, latitude]; the map API internally uses [latitude, longitude].
        polygon = [[point[1], point[0]] for point in rings[0]]
        existing = db.query(CadastralParcel).filter(
            CadastralParcel.state.ilike(required["state"]),
            CadastralParcel.district.ilike(required["district"]),
            CadastralParcel.village.ilike(required["village"]),
            CadastralParcel.survey_number.ilike(required["survey_number"]),
        ).first()
        if existing:
            existing.geometry = polygon
            existing.area_acres = properties.get("area_acres")
        else:
            db.add(CadastralParcel(**required, geometry=polygon, area_acres=properties.get("area_acres")))
        imported += 1
    db.commit()
    return {"imported": imported, "rejected_feature_numbers": rejected}
