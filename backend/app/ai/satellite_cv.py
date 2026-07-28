"""
Satellite / aerial image land-cover analysis — REAL image processing,
honestly scoped.

WHAT THIS ACTUALLY DOES
--------------------------
Given an uploaded image (an aerial/satellite crop of a claim's parcel),
this module:
  1. Runs K-means clustering (scikit-learn) on pixel colors to group
     the image into a handful of visually distinct regions.
  2. Classifies each cluster into a land-cover type (forest, agricultural
     land, water, homestead/built-up) using HSV color heuristics.
  3. Extracts the actual pixel contours of each region with OpenCV and
     converts them into approximate lat/lon polygons, so they render in
     roughly the right place on the Leaflet map.
  4. Computes each region's share of the image area, scaled against the
     claim's declared acreage.

This genuinely processes the pixels you upload — it is not a lookup
table or a random-number generator. That said, be precise about what it
is NOT:

WHAT THIS IS **NOT**
-----------------------
- It is NOT a trained deep-learning segmentation model. A production
  system (as described in the original SIH problem statement) would use
  a model such as U-Net or DeepLabV3+, fine-tuned on labeled satellite
  imagery (e.g. a LandCover.ai-style dataset), typically consuming
  multispectral bands (including near-infrared, for proper NDVI-based
  vegetation detection) from Sentinel-2 or Bhuvan. None of that — model
  weights, GPU, multispectral imagery, or a live imagery API — is
  available in this build environment (no internet access), so this
  module works only with plain RGB and unsupervised clustering.
- It is NOT scientifically georeferenced. The lat/lon polygon returned
  for each region is a linear approximation assuming the uploaded image
  is centered on the claim's coordinates and covers a small square patch
  of ground (`coverage_deg`, default ~0.01° ≈ ~1 km). A real system
  would carry actual geo-transform metadata from the imagery provider.

HOW TO UPGRADE TO A REAL TRAINED MODEL
------------------------------------------
Replace `_cluster_and_classify()` below with a call to your trained
model's inference (ONNX/TorchScript), and replace the coordinate
approximation in `_pixel_to_latlon()` with the image's real geo-transform.
Everything downstream (the API route, DB storage, DSS scoring, and the
Leaflet map layer) consumes this module's output through one stable
function — `analyze_image()` — so nothing else needs to change.
"""
import numpy as np
import cv2
from sklearn.cluster import KMeans

from app.models import AssetType

N_CLUSTERS = 4
MIN_REGION_AREA_FRACTION = 0.03  # ignore tiny noisy clusters (<3% of image)


def _classify_cluster_color(mean_bgr: np.ndarray) -> AssetType:
    """
    Maps a cluster's mean color (BGR, OpenCV convention) to a land-cover
    class using simple HSV heuristics — the same rule-of-thumb a human
    would use eyeballing a satellite image: green regions are vegetation,
    blue is water, tan/brown/gray is built-up, bare soil, or rooftops.
    """
    bgr = np.uint8([[mean_bgr]])
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
    hue, sat, val = int(hsv[0]), int(hsv[1]), int(hsv[2])

    # OpenCV hue range is 0-179
    if 90 <= hue <= 135 and sat > 30:
        return AssetType.WATER_BODY
    if 35 <= hue <= 95 and sat > 40:
        # Green band: darker/denser -> forest, lighter/patchier -> farmland
        return AssetType.FOREST_COVER if val < 150 else AssetType.AGRICULTURAL_LAND
    if hue < 35 or sat < 40:
        # Tan/brown/red-orange hues, or low-saturation bright grays, read as
        # built-up/bare soil/homestead — rooftops, courtyards, cleared ground.
        return AssetType.HOMESTEAD
    # Fallback: anything else greenish gets treated as cultivated land
    return AssetType.AGRICULTURAL_LAND


def _pixel_to_latlon(x: float, y: float, img_w: int, img_h: int,
                      center_lat: float, center_lon: float, coverage_deg: float) -> list[float]:
    """
    Linear approximation only — see module docstring. Explicitly casts to
    native Python floats: numpy float64 values silently break JSON
    serialization further up the stack (FastAPI/Pydantic and the JSON
    DB column), so this boundary must hand back plain floats.
    """
    lon = center_lon - coverage_deg / 2 + (float(x) / img_w) * coverage_deg
    lat = center_lat + coverage_deg / 2 - (float(y) / img_h) * coverage_deg
    return [round(float(lat), 6), round(float(lon), 6)]


def _cluster_and_classify(image: np.ndarray, n_clusters: int = N_CLUSTERS):
    """
    Runs K-means on the image's pixel colors. Returns, per cluster:
    (mask, mean_color_bgr, pixel_fraction).
    """
    h, w = image.shape[:2]
    pixels = image.reshape(-1, 3).astype(np.float32)

    # Cap cluster count at the number of distinct colors actually present —
    # requesting more clusters than there are distinct colors forces KMeans
    # to arbitrarily split a real region into noisy, meaningless pieces.
    n_unique = len(np.unique(pixels, axis=0))
    effective_k = max(1, min(n_clusters, n_unique))

    kmeans = KMeans(n_clusters=effective_k, n_init=4, random_state=42)
    labels = kmeans.fit_predict(pixels)
    labels_2d = labels.reshape(h, w)

    total_pixels = h * w
    clusters = []
    for cluster_id in range(effective_k):
        mask = (labels_2d == cluster_id).astype(np.uint8)
        pixel_count = int(mask.sum())
        fraction = pixel_count / total_pixels
        if fraction < MIN_REGION_AREA_FRACTION:
            continue
        mean_color = kmeans.cluster_centers_[cluster_id]

        # Cohesion-based confidence: tighter clusters (pixels close to their
        # centroid) get a higher confidence score than diffuse, noisy ones.
        cluster_pixels = pixels[labels == cluster_id]
        spread = float(np.mean(np.linalg.norm(cluster_pixels - mean_color, axis=1)))
        confidence = float(np.clip(1.0 - (spread / 180.0), 0.45, 0.95))

        clusters.append((mask, mean_color, fraction, confidence))

    return clusters


def analyze_image(image_path: str, claim_id: int, center_lat: float, center_lon: float,
                   declared_area_acres: float, coverage_deg: float = 0.01) -> list[dict]:
    """
    Public entry point. Loads the uploaded image, clusters it into
    land-cover regions, and returns a list of asset dicts shaped exactly
    like app/ai/asset_detection.py's output, so the API/DB layer needs
    no special-casing between the two.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not read image file — is it a valid image format?")

    h, w = image.shape[:2]
    clusters = _cluster_and_classify(image)

    results = []
    for mask, mean_color, fraction, confidence in clusters:
        asset_type = _classify_cluster_color(mean_color)

        # Extract the largest contour of this region for a map polygon.
        contours, _ = cv2.findContours(mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        largest = max(contours, key=cv2.contourArea)
        epsilon = 0.01 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)
        # Cap polygon complexity so the map layer stays light.
        points = approx.reshape(-1, 2)[:12]
        if len(points) < 3:
            continue

        geometry = [
            _pixel_to_latlon(px, py, w, h, center_lat, center_lon, coverage_deg)
            for px, py in points
        ]

        results.append({
            "asset_type": asset_type,
            "area_acres": round(float(declared_area_acres * fraction), 2),
            "confidence_score": round(confidence, 2),
            "source": "satellite_cv_kmeans",
            "geometry": geometry,
        })

    return results
