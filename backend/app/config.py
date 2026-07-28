"""
Central configuration for the FRA Atlas & DSS backend.

Everything that differs between local dev / staging / production lives
here, pulled from environment variables so secrets never sit in code.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "FRA Atlas & WebGIS DSS API"
    ENV: str = "development"

    # --- Database ---
    # Swap this for a PostgreSQL + PostGIS URL in production, e.g.:
    # postgresql://user:pass@host:5432/fra_atlas
    DATABASE_URL: str = "sqlite:///./fra_atlas.db"

    # --- Auth / JWT ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- File uploads ---
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 15

    class Config:
        env_file = ".env"


settings = Settings()
