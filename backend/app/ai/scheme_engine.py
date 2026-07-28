"""
Decision Support System - scheme matching engine.

This is intentionally rule-based rather than a black-box model: the
DSS's job is to justify *why* a claimant is eligible for a scheme in
terms an official can audit, so transparent rules beat an opaque
classifier here. (A learned ranking model could be layered on top of
this later to prioritize among ties, but the eligibility logic itself
should stay explainable.)
"""
from app.models import Claim


def score_claim_against_scheme(claim: Claim, scheme_rules: dict) -> tuple[float, list[str]]:
    """
    Returns (score 0-100, list of human-readable reasons).
    A claim must pass all hard eligibility gates to score > 0.
    """
    reasons = []

    claim_types = scheme_rules.get("claim_types", [])
    if claim_types and claim.claim_type.value not in claim_types:
        return 0.0, [f"Claim type {claim.claim_type.value} not eligible (requires {claim_types})"]

    land_types = scheme_rules.get("land_types", [])
    if land_types and claim.land_type and claim.land_type not in land_types:
        return 0.0, [f"Land type '{claim.land_type}' not eligible (requires one of {land_types})"]

    min_area = scheme_rules.get("min_area")
    if min_area is not None and claim.area_acres < min_area:
        return 0.0, [f"Land area {claim.area_acres} acres is below minimum {min_area} acres"]

    max_area = scheme_rules.get("max_area")
    if max_area is not None and claim.area_acres > max_area:
        return 0.0, [f"Land area {claim.area_acres} acres exceeds maximum {max_area} acres"]

    # Passed all hard gates - now build a soft score + explanation.
    score = 60.0
    reasons.append(f"Claim type '{claim.claim_type.value}' matches scheme criteria")

    if claim.land_type in land_types:
        score += 15.0
        reasons.append(f"Land type '{claim.land_type}' matches scheme criteria")

    if claim.status.value in ("approved", "verified"):
        score += 20.0
        reasons.append(f"Claim status '{claim.status.value}' strengthens eligibility")
    else:
        reasons.append(f"Claim is still '{claim.status.value}' — approval will strengthen eligibility")

    if min_area is not None and claim.area_acres >= min_area * 1.5:
        score += 5.0
        reasons.append("Land area comfortably exceeds the minimum threshold")

    return min(score, 100.0), reasons
