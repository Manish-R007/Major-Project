"""Load every bundled local cadastral GeoJSON file into the parcel registry."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import CadastralParcel


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _text(properties: dict, *keys: str) -> str | None:
    for key in keys:
        value = properties.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _area(properties: dict) -> float | None:
    value = properties.get("area_acres", properties.get("area_acres_decimal"))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parcel_values(properties: dict, geometry: dict) -> dict | None:
    required = {key: _text(properties, key, key.upper(), key.title()) for key in ("state", "district", "village", "survey_number")}
    rings = geometry.get("coordinates") or []
    if not all(required.values()) or geometry.get("type") != "Polygon" or not rings or len(rings[0]) < 3:
        return None
    # GeoJSON is longitude/latitude; map data is latitude/longitude.
    return {
        **required,
        "geometry": [[point[1], point[0]] for point in rings[0]],
        "area_acres": _area(properties),
        "record_identifier": _text(properties, "pattadar_account_no", "khata_number", "patta_number"),
        "landholder_name": _text(properties, "landholder_name", "claimant_name", "owner_name"),
        "land_type": _text(properties, "land_type"),
    }


def load_bundled_parcels(db: Session) -> int:
    """Upsert all local GeoJSON parcels. This is the sole OCR verification source."""
    loaded = 0
    for path in DATA_DIR.glob("*.geojson"):
        try:
            features = json.loads(path.read_text(encoding="utf-8")).get("features", [])
        except (OSError, ValueError):
            continue
        for feature in features:
            values = parcel_values(feature.get("properties") or {}, feature.get("geometry") or {})
            if not values:
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
            loaded += 1
    db.commit()
    return loaded
