"""Loads the bundled development cadastral parcel once, without overwriting official imports."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import CadastralParcel


DEMO_FILE = Path(__file__).resolve().parents[1] / "data" / "baihar-cadastral-demo.geojson"


def load_bundled_demo_parcel(db: Session) -> None:
    """Seed the documented Baihar sample so the OCR demo works after a normal restart."""
    if not DEMO_FILE.exists():
        return
    feature = json.loads(DEMO_FILE.read_text(encoding="utf-8"))["features"][0]
    props = feature["properties"]
    existing = db.query(CadastralParcel).filter(
        CadastralParcel.state == props["state"],
        CadastralParcel.district == props["district"],
        CadastralParcel.village == props["village"],
        CadastralParcel.survey_number == props["survey_number"],
    ).first()
    if existing:
        return
    # GeoJSON stores longitude first; the application map stores latitude first.
    polygon = [[point[1], point[0]] for point in feature["geometry"]["coordinates"][0]]
    db.add(CadastralParcel(
        state=props["state"], district=props["district"], village=props["village"],
        survey_number=props["survey_number"], area_acres=props["area_acres"], geometry=polygon,
    ))
    db.commit()
