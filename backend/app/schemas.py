from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import UserRole, ClaimType, ClaimStatus, AssetType, OcrStatus, DocumentVerificationStatus


# ---------- Auth ----------

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- Users ----------

class UserCreate(BaseModel):
    """
    Public self-registration payload. Deliberately has NO `role` field —
    letting a client pick their own role here would be a privilege-
    escalation bug (anyone could register as `admin`). Self-registration
    always creates a Citizen account; officials are provisioned by an
    Administrator via AdminUserCreate below, mirroring how real
    government portals provision official accounts rather than letting
    them self-register.
    """
    username: str
    email: Optional[str] = None
    full_name: str
    password: str
    state: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None


class AdminUserCreate(BaseModel):
    """Used by Administrators to provision official accounts with a chosen role."""
    username: str
    email: Optional[str] = None
    full_name: str
    password: str
    role: UserRole = UserRole.CITIZEN
    state: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str]
    full_name: str
    role: UserRole
    state: Optional[str]
    district: Optional[str]
    village: Optional[str]
    is_active: bool


# ---------- Claims ----------

class ClaimCreate(BaseModel):
    patta_number: str
    claimant_name: str
    claim_type: ClaimType
    state: str
    district: str
    village: str
    latitude: float
    longitude: float
    area_acres: float
    land_type: Optional[str] = None


class ClaimUpdateStatus(BaseModel):
    status: ClaimStatus
    reviewer_notes: Optional[str] = None


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patta_number: str
    claimant_name: str
    claim_type: ClaimType
    status: ClaimStatus
    state: str
    district: str
    village: str
    latitude: float
    longitude: float
    area_acres: float
    land_type: Optional[str]
    submitted_date: datetime
    reviewed_date: Optional[datetime]
    reviewer_notes: Optional[str]
    owner_id: Optional[int]
    survey_number: Optional[str] = None
    parcel_geometry: Optional[list] = None
    parcel_source: Optional[str] = None


# ---------- Assets ----------

class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    asset_type: AssetType
    area_acres: float
    confidence_score: float
    source: str
    geometry: Optional[list]
    detected_at: datetime


class DetectRequest(BaseModel):
    claim_id: int


class SatelliteImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    original_filename: str
    coverage_deg: float
    uploaded_at: datetime


# ---------- Claim Documents ----------

class ClaimDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    original_filename: str
    content_type: Optional[str]
    file_size_bytes: Optional[int]
    ocr_status: OcrStatus
    extracted_text: Optional[str]
    verification_status: DocumentVerificationStatus
    mismatched_fields: Optional[list[str]]
    uploaded_at: datetime


# ---------- Schemes / DSS ----------

class SchemeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ministry: str
    description: str
    eligibility_rules: dict


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    scheme: SchemeOut
    score: float
    reasons: list[str]
    generated_at: datetime
