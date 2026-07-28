import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, JSON, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    CITIZEN = "citizen"                # FRA claimant
    VILLAGE_OFFICIAL = "village_official"   # Gram Sabha level
    DISTRICT_OFFICER = "district_officer"   # Forest/Revenue dept
    STATE_OFFICER = "state_officer"         # MoTA state nodal
    ADMIN = "admin"


class ClaimType(str, enum.Enum):
    IFR = "IFR"   # Individual Forest Rights
    CFR = "CFR"   # Community Forest Resource
    CR = "CR"     # Community Rights


class ClaimStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    APPROVED = "approved"
    REJECTED = "rejected"


class AssetType(str, enum.Enum):
    AGRICULTURAL_LAND = "agricultural_land"
    FOREST_COVER = "forest_cover"
    WATER_BODY = "water_body"
    HOMESTEAD = "homestead"
    ENCROACHMENT = "encroachment"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=True)
    full_name = Column(String(120), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CITIZEN)

    # Jurisdiction scoping - used to filter what a user can see/approve.
    state = Column(String(64), nullable=True)
    district = Column(String(64), nullable=True)
    village = Column(String(64), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    claims = relationship("Claim", back_populates="owner", foreign_keys="Claim.owner_id")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    patta_number = Column(String(64), unique=True, index=True, nullable=False)
    claimant_name = Column(String(120), nullable=False)
    claim_type = Column(Enum(ClaimType), nullable=False)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.SUBMITTED)

    state = Column(String(64), nullable=False)
    district = Column(String(64), nullable=False)
    village = Column(String(64), nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_acres = Column(Float, nullable=False)
    land_type = Column(String(64), nullable=True)  # e.g. cultivable, homestead

    submitted_date = Column(DateTime, default=datetime.utcnow)
    reviewed_date = Column(DateTime, nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="claims", foreign_keys=[owner_id])

    assets = relationship("Asset", back_populates="claim", cascade="all, delete-orphan")
    recommendations = relationship(
        "SchemeRecommendation", back_populates="claim", cascade="all, delete-orphan"
    )
    documents = relationship(
        "ClaimDocument", back_populates="claim", cascade="all, delete-orphan"
    )


class Asset(Base):
    """
    A physical feature detected on/near a claim's parcel, either by the
    AI satellite-analysis pipeline or entered manually by an official.
    """
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    asset_type = Column(Enum(AssetType), nullable=False)
    area_acres = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0.0 - 1.0
    source = Column(String(32), default="satellite_ai")  # satellite_ai | manual
    geometry = Column(JSON, nullable=True)  # simplified polygon [[lat,lng], ...]
    detected_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="assets")


class Scheme(Base):
    """A government welfare/development scheme the DSS can recommend."""
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    ministry = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    # Eligibility rules stored as JSON, e.g.:
    # {"claim_types": ["IFR"], "land_types": ["cultivable"], "min_area": 0.5}
    eligibility_rules = Column(JSON, nullable=False)


class SchemeRecommendation(Base):
    __tablename__ = "scheme_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    score = Column(Float, nullable=False)  # 0-100 match score
    reasons = Column(JSON, nullable=False)  # list[str] explaining the match
    generated_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="recommendations")
    scheme = relationship("Scheme")


class OcrStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"   # OCR engine not installed on this machine
    FAILED = "failed"


class DocumentVerificationStatus(str, enum.Enum):
    MATCHED = "matched"
    MISMATCH = "mismatch"
    UNPARSEABLE = "unparseable"
    NOT_AVAILABLE = "not_available"


class ClaimDocument(Base):
    """
    An uploaded scan of a legacy paper claim (patta, old FRA form, survey
    sketch, etc). `extracted_text` is filled in by the OCR pipeline in
    app/ai/ocr.py when available — see that module's docstring.
    `verification_status`/`mismatched_fields` come from cross-checking
    OCR-parsed fields against the claim's declared data — see
    app/ai/document_parser.py.
    """
    __tablename__ = "claim_documents"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)  # random name on disk
    content_type = Column(String(100), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    ocr_status = Column(Enum(OcrStatus), default=OcrStatus.PENDING)
    extracted_text = Column(Text, nullable=True)

    verification_status = Column(Enum(DocumentVerificationStatus),
                                  default=DocumentVerificationStatus.NOT_AVAILABLE)
    mismatched_fields = Column(JSON, nullable=True)  # list[str], e.g. ["patta_number"]

    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="documents")


class SatelliteImage(Base):
    """
    An aerial/satellite image uploaded for a claim's parcel, which the
    computer-vision pipeline in app/ai/satellite_cv.py analyzes to
    produce Asset records. See that module's docstring for exactly what
    kind of analysis this is (classical CV, not a trained neural net).
    """
    __tablename__ = "satellite_images"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    coverage_deg = Column(Float, default=0.01)  # assumed ground footprint, in degrees, centered on the claim point
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim")


class AuditLog(Base):
    """Tamper-evident trail of who did what — essential for legal land records."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)   # e.g. "claim_approved"
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
