# FRA Atlas & WebGIS-based DSS
### SIH25108 — AI-powered FRA Atlas and Decision Support System for FRA Implementation
Ministry of Tribal Affairs · Focus states: Madhya Pradesh, Tripura, Odisha, Telangana

A full-stack reference implementation: digitized claim registry, WebGIS atlas
with AI-based asset detection, a rule-based Decision Support System (DSS) for
government scheme matching, and role-based authentication for the five actor
types in the FRA workflow (claimant → village → district → state → admin).

---

## 1. Project structure

```
fra-atlas-dss/
├── backend/                     FastAPI + SQLAlchemy + JWT auth
│   ├── app/
│   │   ├── main.py               App entrypoint, router registration
│   │   ├── config.py             Settings (env-driven)
│   │   ├── database.py           SQLAlchemy engine/session
│   │   ├── models.py              ORM models: User, Claim, Asset, Scheme, ...
│   │   ├── schemas.py             Pydantic request/response models
│   │   ├── security.py            Password hashing + JWT issue/verify
│   │   ├── deps.py                 get_current_user, require_roles, jurisdiction scoping
│   │   ├── seed_data.py            Demo users / schemes / sample claims
│   │   ├── routers/
│   │   │   ├── auth.py             /api/auth  (register [citizen-only], login, refresh, me)
│   │   │   ├── claims.py           /api/claims (CRUD + status workflow + document upload/OCR)
│   │   │   ├── atlas.py            /api/atlas  (map layers + satellite image upload + detection)
│   │   │   ├── dss.py              /api/dss    (scheme catalogue + recommendations)
│   │   │   └── users.py            /api/users  (admin listing + admin-provisioned official accounts)
│   │   └── ai/
│   │       ├── asset_detection.py  Simulated fallback detection (see §4)
│   │       ├── satellite_cv.py     REAL K-means/contour land-cover analysis (see §4)
│   │       ├── ocr.py              OCR for uploaded legacy claim documents (see §4)
│   │       ├── document_parser.py  OCR-to-atlas verification bridge (see §4)
│   │       ├── scheme_engine.py    Rule-based DSS scoring engine
│   │       └── schemes_data.py     Seed catalogue of govt schemes
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/                    React + Vite + Tailwind + Leaflet
    ├── src/
    │   ├── api/client.js         Axios instance, JWT attach + silent refresh
    │   ├── context/AuthContext.jsx
    │   ├── components/           Navbar, ProtectedRoute, StatCard, ClaimStatusBadge
    │   └── pages/
    │       ├── Login.jsx          Sign-in
    │       ├── Register.jsx       Public citizen self-registration
    │       ├── Dashboard.jsx      Role-aware overview + stats
    │       ├── Atlas.jsx          Leaflet WebGIS map, satellite image upload + detection
    │       ├── Claims.jsx         Claim registry, filters, new-claim form
    │       ├── ClaimDetail.jsx    Claim detail, status workflow, documents, DSS recommendations
    │       ├── DSS.jsx            Scheme catalogue
    │       └── Users.jsx          Admin user list
    ├── tailwind.config.js
    └── package.json
```

## 2. Running it locally

**⚠️ Note:** this project was built in a sandboxed environment with no
internet access, so end-to-end server boot has not been run here. That
said, this iteration goes further than a syntax check: every backend
file passes `py_compile`, every frontend file was actually compiled
through esbuild (not just eyeballed), and the K-means/contour land-cover
pipeline in `app/ai/satellite_cv.py` was executed against synthetic test
images and verified to (a) correctly distinguish forest/water/homestead/
agricultural regions and (b) produce valid, JSON-serializable output —
an earlier version of this code had a numpy-float64 serialization bug
that would have broken at the API layer, caught here before shipping.
Please still run the full stack yourself per the steps below and flag
anything that doesn't line up.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Create tables + demo data (5 users, 7 schemes, 5 sample claims)
python -m app.seed_data

uvicorn app.main:app --reload --port 8000
```

**Optional — enable OCR on uploaded claim documents:** the `pytesseract`
Python package alone isn't enough; it needs the Tesseract engine
installed at the OS level:

```bash
brew install tesseract              # macOS
sudo apt-get install tesseract-ocr  # Ubuntu/Debian
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

Without this, document upload still works fine — extracted text is
just marked "unavailable" instead of populated.

### Local cadastral OCR verification

At startup the backend imports every GeoJSON file in `backend/data/` into
the local parcel registry. A scanned document is accepted only when OCR
finds a matching state, district, village, and survey number in that local
registry. Its boundary, area, and available record metadata come from the
matching local parcel; no external cadastral service is used.

API docs (Swagger UI): http://localhost:8000/docs

**Demo logins** (also shown on the login screen):

| Username            | Password      | Role                  |
|----------------------|--------------|-----------------------|
| `citizen1`           | password123  | Claimant              |
| `village_official`   | password123  | Village Official      |
| `district_officer`   | password123  | District Officer      |
| `state_officer`      | password123  | State Nodal Officer   |
| `admin`              | admin123     | Administrator         |

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` to
`localhost:8000`, so both must be running.

## 3. Authentication & roles

JWT access tokens (30 min) + refresh tokens (7 days), bcrypt-hashed
passwords. Every protected endpoint resolves the current user from the
token and checks their role via `require_roles(...)`. Data visibility is
additionally **scoped by jurisdiction** — a district officer only ever
sees claims in their own district; a state officer sees their whole
state; citizens see only their own claims. See `app/deps.py`.

**Registration model:** `/register` is public and always creates a
Citizen account — it deliberately does not accept a `role` field in the
request body, since letting a client choose their own role would be a
privilege-escalation bug (anyone could register as `admin`). Officials
(village/district/state) are provisioned by an Administrator via
`POST /api/users` (`AdminUserCreate` schema, role-gated to `admin`),
mirroring how real government portals provision official accounts.

An `AuditLog` table records logins, registrations, claim status changes,
detection runs, and DSS recommendation generation — every write to a
legally significant record is attributable.

Production hardening notes (kept out of this scaffold to stay
buildable without infra): Aadhaar/e-Pramaan SSO for government users,
rate-limiting on `/auth/login`, HTTPS termination, and moving from
SQLite to PostgreSQL + PostGIS for real spatial queries.

## 4. About the "AI" components — what's real vs. simulated here

Being upfront about this so nothing is oversold in a demo or report:

- **`app/ai/satellite_cv.py`** runs **real image processing** — it is
  not simulated. Upload an aerial/satellite image for a claim (from the
  Atlas page), and it genuinely: (1) runs K-means color clustering
  (scikit-learn) on the actual pixels, (2) classifies each cluster into
  a land-cover type using HSV color heuristics, (3) extracts real pixel
  contours with OpenCV and converts them into map polygons. This has
  been tested end-to-end in this environment with synthetic imagery and
  correctly distinguishes forest/water/homestead/agricultural regions.
  What it is **not**: a trained deep-learning segmentation model. A
  production system (per the original SIH brief) would use a U-Net or
  DeepLabV3+ fine-tuned on labeled multispectral satellite imagery
  (Sentinel-2/Bhuvan, ideally with near-infrared bands for proper NDVI
  vegetation detection). None of that — GPU, model weights, multispectral
  imagery, or a live imagery API — is available in this build environment
  (no internet access), so this is an honest classical-CV approximation,
  not a lookup table or random-number simulation. The module's docstring
  spells out exactly how to swap in a trained model later.
- **`app/ai/asset_detection.py`** is a clearly-labeled **simulation**,
  kept as a fallback: if a claim has no uploaded satellite image, running
  detection on it uses this instead, so the demo still works end-to-end
  without requiring imagery for every claim. It deterministically derives
  plausible detections from the claim's declared area/land type — no
  neural network involved.
- **`app/ai/scheme_engine.py`** is a genuine, fully working **rule-based
  DSS** — not simulated. It's deliberately rule-based rather than a
  black-box classifier, because a scheme-eligibility decision needs to
  be explainable to an official and auditable, not just scored.
- **`app/ai/document_parser.py`** is the bridge between OCR and the atlas
  that was previously missing: genuine regex-based extraction of key
  fields (patta number, claimant name, area) from OCR text, cross-checked
  against the claim's declared data (fuzzy name matching, tolerant area
  matching, so OCR noise doesn't cause false mismatches — tested against
  synthetic OCR-like text including intentional noise and real
  mismatches). Deliberately surfaces only a status
  (matched/mismatch/unparseable) plus which fields disagreed — never the
  raw OCR text or parsed values — on the WebGIS atlas view, since a map
  is a broader-visibility surface than a single claim's detail page. The
  full extracted text and per-field detail remain on the claim detail
  page, under the same jurisdiction/ownership access control as
  everything else there. This is pattern-based text extraction, not a
  layout-aware model — see the module's docstring for the upgrade path
  (LayoutLMv3/Donut) for messier real-world forms.
- **`app/ai/ocr.py`** — document digitization is genuinely implemented
  (upload a scanned patta/FRA form on a claim's detail page and it runs
  OCR), but it depends on the Tesseract binary being installed
  separately at the OS level (not via pip — see the module's docstring
  for install commands per platform). If Tesseract isn't installed, the
  upload still succeeds; the document is just marked `ocr_status:
  unavailable` instead of the request failing. Plain OCR also reads
  printed text far better than handwriting — the docstring notes the
  upgrade path to a layout-aware model (LayoutLMv3/Donut) for messier
  legacy handwritten forms. PDF uploads are stored but not yet
  rasterized for OCR in this scaffold (image formats only for now).

## 5. Data model summary

`User` (role + jurisdiction) → `Claim` (patta, type, status, geo-point) →
`Asset` (AI/manual detections, polygon geometry) and `SchemeRecommendation`
(generated by matching a claim against the `Scheme` catalogue). See
`app/models.py` for full field definitions.
