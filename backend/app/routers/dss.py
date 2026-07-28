from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Claim, Scheme, SchemeRecommendation, User, UserRole, AuditLog
from app.schemas import SchemeOut, RecommendationOut
from app.ai.scheme_engine import score_claim_against_scheme

router = APIRouter(prefix="/api/dss", tags=["dss"])


@router.get("/schemes", response_model=list[SchemeOut])
def list_schemes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Scheme).all()


@router.post("/claims/{claim_id}/recommend", response_model=list[RecommendationOut])
def generate_recommendations(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if current_user.role == UserRole.CITIZEN and claim.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this claim")

    # Clear stale recommendations before regenerating.
    db.query(SchemeRecommendation).filter(SchemeRecommendation.claim_id == claim.id).delete()

    schemes = db.query(Scheme).all()
    created = []
    for scheme in schemes:
        score, reasons = score_claim_against_scheme(claim, scheme.eligibility_rules)
        if score > 0:
            rec = SchemeRecommendation(
                claim_id=claim.id, scheme_id=scheme.id, score=score, reasons=reasons,
            )
            db.add(rec)
            created.append(rec)

    db.add(AuditLog(user_id=current_user.id, action="dss_recommendations_generated",
                     entity_type="claim", entity_id=claim.id,
                     detail=f"{len(created)} schemes matched"))
    db.commit()
    for r in created:
        db.refresh(r)

    created.sort(key=lambda r: r.score, reverse=True)
    return created


@router.get("/claims/{claim_id}/recommendations", response_model=list[RecommendationOut])
def get_recommendations(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if current_user.role == UserRole.CITIZEN and claim.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this claim")

    recs = (
        db.query(SchemeRecommendation)
        .filter(SchemeRecommendation.claim_id == claim.id)
        .order_by(SchemeRecommendation.score.desc())
        .all()
    )
    return recs
