"""
Populates the database with demo users, the scheme catalogue, and a
handful of sample FRA claims across the four focus states so the UI
has something real to show on first run.

Run with:  python -m app.seed_data
"""
from app.database import Base, engine, SessionLocal
from app.models import User, UserRole, Claim, ClaimType, ClaimStatus, Scheme
from app.security import hash_password
from app.ai.schemes_data import SCHEMES

DEMO_USERS = [
    dict(username="citizen1", full_name="Ramesh Baiga", password="password123",
         role=UserRole.CITIZEN, state="Madhya Pradesh", district="Balaghat", village="Baihar"),
    dict(username="village_official", full_name="Sunita Meena", password="password123",
         role=UserRole.VILLAGE_OFFICIAL, state="Madhya Pradesh", district="Balaghat", village="Baihar"),
    dict(username="district_officer", full_name="Arjun Rao", password="password123",
         role=UserRole.DISTRICT_OFFICER, state="Madhya Pradesh", district="Balaghat"),
    dict(username="state_officer", full_name="Priya Nair", password="password123",
         role=UserRole.STATE_OFFICER, state="Odisha"),
    dict(username="admin", full_name="System Administrator", password="admin123",
         role=UserRole.ADMIN),
]

SAMPLE_CLAIMS = [
    dict(patta_number="MP-BLG-0001", claimant_name="Ramesh Baiga", claim_type=ClaimType.IFR,
         state="Madhya Pradesh", district="Balaghat", village="Baihar",
         latitude=22.0996, longitude=80.3350, area_acres=1.8, land_type="cultivable",
         status=ClaimStatus.VERIFIED),
    dict(patta_number="MP-BLG-0002", claimant_name="Kamla Bai", claim_type=ClaimType.IFR,
         state="Madhya Pradesh", district="Balaghat", village="Baihar",
         latitude=22.1050, longitude=80.3420, area_acres=0.9, land_type="homestead",
         status=ClaimStatus.SUBMITTED),
    dict(patta_number="OD-MYB-0001", claimant_name="Sabar Community", claim_type=ClaimType.CFR,
         state="Odisha", district="Mayurbhanj", village="Jashipur",
         latitude=21.9497, longitude=86.3450, area_acres=42.0, land_type="forest",
         status=ClaimStatus.APPROVED),
    dict(patta_number="TS-ADB-0001", claimant_name="Lambada Community", claim_type=ClaimType.CR,
         state="Telangana", district="Adilabad", village="Utnoor",
         latitude=19.3450, longitude=78.6100, area_acres=15.5, land_type="forest",
         status=ClaimStatus.UNDER_REVIEW),
    dict(patta_number="TR-DHK-0001", claimant_name="Bishnu Reang", claim_type=ClaimType.IFR,
         state="Tripura", district="Dhalai", village="Ambassa",
         latitude=23.9350, longitude=91.8400, area_acres=2.4, land_type="waterlogged",
         status=ClaimStatus.SUBMITTED),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).first():
            users_by_username = {}
            for u in DEMO_USERS:
                user = User(
                    username=u["username"], full_name=u["full_name"],
                    hashed_password=hash_password(u["password"]), role=u["role"],
                    state=u.get("state"), district=u.get("district"), village=u.get("village"),
                )
                db.add(user)
                users_by_username[u["username"]] = user
            db.commit()
            print(f"Seeded {len(DEMO_USERS)} demo users.")
        else:
            users_by_username = {u.username: u for u in db.query(User).all()}

        if not db.query(Scheme).first():
            for s in SCHEMES:
                db.add(Scheme(**s))
            db.commit()
            print(f"Seeded {len(SCHEMES)} schemes.")

        if not db.query(Claim).first():
            citizen = users_by_username.get("citizen1")
            for c in SAMPLE_CLAIMS:
                owner_id = citizen.id if citizen and c["patta_number"].startswith("MP-BLG-0001") else None
                db.add(Claim(**c, owner_id=owner_id))
            db.commit()
            print(f"Seeded {len(SAMPLE_CLAIMS)} sample claims.")

        print("\nDemo credentials (username / password):")
        for u in DEMO_USERS:
            print(f"  {u['username']:18s} / {u['password']}   [{u['role'].value}]")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
