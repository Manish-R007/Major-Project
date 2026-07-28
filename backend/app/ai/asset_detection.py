"""
Satellite asset-detection interface.

WHAT THIS IS IN A REAL DEPLOYMENT
----------------------------------
In production this module wraps a trained semantic-segmentation model
(e.g. U-Net / DeepLabV3+ fine-tuned on Sentinel-2 or Bhuvan imagery,
similar to models trained on the LandCover.ai dataset) that takes a
satellite image tile centered on a claim's coordinates and returns
per-pixel land-cover classes (agricultural land, forest cover, water
body, homestead, encroachment).

WHAT THIS FILE ACTUALLY DOES RIGHT NOW
----------------------------------------
No GPU, model weights, or satellite imagery API access are available
in this environment, so `detect_assets()` below is a clearly-labelled
SIMULATION: it deterministically derives plausible-looking detections
from the claim's own declared data (area, land type) plus a seeded
random component, so demos are repeatable. It is NOT running a real
neural network. Swap `_simulate_detection()` for a real call to your
trained model's inference endpoint and the rest of the API (routes,
DB storage, DSS scoring) needs no changes — that's the point of
keeping this behind one function.

HOW TO PLUG IN A REAL MODEL
-----------------------------
1. Train / fine-tune a segmentation model (see README.md for dataset
   pointers) and export it (ONNX / TorchScript).
2. Replace the body of `detect_assets()` with:
       image = fetch_satellite_tile(lat, lon)   # Sentinel Hub / Bhuvan API
       mask = model.predict(image)               # your U-Net / DeepLabV3+
       return polygons_from_mask(mask)
3. Keep the return shape (list[dict]) identical so `routers/atlas.py`
   keeps working unmodified.
"""
import hashlib
import random

from app.models import AssetType

ASSET_MIX_BY_LAND_TYPE = {
    "cultivable": [AssetType.AGRICULTURAL_LAND, AssetType.HOMESTEAD],
    "homestead": [AssetType.HOMESTEAD, AssetType.AGRICULTURAL_LAND],
    "forest": [AssetType.FOREST_COVER, AssetType.AGRICULTURAL_LAND],
    "waterlogged": [AssetType.WATER_BODY, AssetType.AGRICULTURAL_LAND],
}


def _seeded_random(claim_id: int) -> random.Random:
    """Deterministic RNG per claim so re-running a demo gives stable results."""
    seed = int(hashlib.sha256(str(claim_id).encode()).hexdigest(), 16) % (10 ** 8)
    return random.Random(seed)


def _simulate_detection(claim_id: int, lat: float, lon: float,
                         declared_area: float, land_type: str | None) -> list[dict]:
    rng = _seeded_random(claim_id)
    asset_types = ASSET_MIX_BY_LAND_TYPE.get(land_type or "cultivable",
                                              [AssetType.AGRICULTURAL_LAND, AssetType.FOREST_COVER])

    results = []
    remaining = declared_area
    for i, asset_type in enumerate(asset_types):
        is_last = i == len(asset_types) - 1
        share = remaining if is_last else remaining * rng.uniform(0.4, 0.7)
        share = round(max(share, 0.05), 2)
        remaining = round(remaining - share, 2)

        # A small synthetic square "footprint" around the claim's point,
        # standing in for a real detected polygon from the segmentation mask.
        offset = 0.0008 * (i + 1)
        geometry = [
            [lat - offset, lon - offset],
            [lat - offset, lon + offset],
            [lat + offset, lon + offset],
            [lat + offset, lon - offset],
        ]

        results.append({
            "asset_type": asset_type,
            "area_acres": share,
            "confidence_score": round(rng.uniform(0.72, 0.96), 2),
            "source": "satellite_ai_simulated",
            "geometry": geometry,
        })

        if remaining <= 0.05:
            break

    # Occasionally flag a possible encroachment near the parcel boundary,
    # mirroring the "change detection" use case described in the brief.
    if rng.random() < 0.25:
        offset = 0.0015
        results.append({
            "asset_type": AssetType.ENCROACHMENT,
            "area_acres": round(rng.uniform(0.05, 0.3), 2),
            "confidence_score": round(rng.uniform(0.55, 0.8), 2),
            "source": "satellite_ai_simulated",
            "geometry": [
                [lat + offset, lon + offset],
                [lat + offset, lon + offset * 2],
                [lat + offset * 2, lon + offset * 2],
                [lat + offset * 2, lon + offset],
            ],
        })

    return results


def detect_assets(claim_id: int, lat: float, lon: float,
                   declared_area: float, land_type: str | None = None) -> list[dict]:
    """Public entry point used by the API layer. See module docstring."""
    return _simulate_detection(claim_id, lat, lon, declared_area, land_type)
