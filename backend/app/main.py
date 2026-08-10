from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, SessionLocal, apply_lightweight_migrations
from app.cadastral_loader import load_bundled_demo_parcel
from app.routers import auth, claims, atlas, cadastral, dss, users

Base.metadata.create_all(bind=engine)
apply_lightweight_migrations()
_startup_db = SessionLocal()
try:
    load_bundled_demo_parcel(_startup_db)
finally:
    _startup_db.close()

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered FRA Atlas and WebGIS-based Decision Support System "
        "for integrated monitoring of Forest Rights Act implementation. "
        "(SIH25108 — Ministry of Tribal Affairs)"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(atlas.router)
app.include_router(cadastral.router)
app.include_router(dss.router)
app.include_router(users.router)


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
