"""Import authorised village cadastral data used for OCR-to-parcel matching."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import CadastralParcel, User, UserRole
from app.cadastral_loader import parcel_values

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
        values = parcel_values(feature.get("properties") or {}, feature.get("geometry") or {})
        if not values:
            rejected.append(index)
            continue
        existing = db.query(CadastralParcel).filter(
            CadastralParcel.state.ilike(values["state"]),
            CadastralParcel.district.ilike(values["district"]),
            CadastralParcel.village.ilike(values["village"]),
            CadastralParcel.survey_number.ilike(values["survey_number"]),
        ).first()
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(CadastralParcel(**values))
        imported += 1
    db.commit()
    return {"imported": imported, "rejected_feature_numbers": rejected}
