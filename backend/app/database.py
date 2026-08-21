from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def apply_lightweight_migrations():
    """Keep existing local SQLite demo databases compatible with new optional claim fields."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    claim_columns = {column["name"] for column in inspect(engine).get_columns("claims")}
    additions = {
        "survey_number": "VARCHAR(80)",
        "parcel_geometry": "JSON",
        "parcel_source": "VARCHAR(32)",
    }
    with engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in claim_columns:
                connection.execute(text(f"ALTER TABLE claims ADD COLUMN {name} {sql_type}"))
    parcel_columns = {column["name"] for column in inspect(engine).get_columns("cadastral_parcels")}
    parcel_additions = {
        "record_identifier": "VARCHAR(80)",
        "landholder_name": "VARCHAR(120)",
        "land_type": "VARCHAR(120)",
    }
    with engine.begin() as connection:
        for name, sql_type in parcel_additions.items():
            if name not in parcel_columns:
                connection.execute(text(f"ALTER TABLE cadastral_parcels ADD COLUMN {name} {sql_type}"))


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
