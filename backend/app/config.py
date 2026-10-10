"""Configuration and environment settings for StreetVerism."""

import os
from functools import lru_cache
from typing import List
from pydantic import BaseModel, Field


def get_required_authority_key() -> str:
    """Retrieve AUTHORITY_KEY from environment or fail fast with a descriptive error."""
    key = os.getenv("AUTHORITY_KEY")
    if not key or not key.strip():
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: AUTHORITY_KEY environment variable is not set. "
            "Authority endpoints require a secure shared secret. Set AUTHORITY_KEY in the environment or .env."
        )
    return key.strip()


class Settings(BaseModel):
    """Application settings loaded strictly from environment variables."""

    # Project identification
    project_name: str = "StreetVerism"
    project_version: str = "1.0.0"

    # Mock mode flag (MOCK=1)
    mock: bool = Field(default_factory=lambda: os.getenv("MOCK", "1").lower() in ("1", "true", "yes"))

    # Security: Strictly required from environment, NO hardcoded default
    authority_key: str = Field(default_factory=get_required_authority_key)

    # CORS configuration
    cors_origins_str: str = Field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*"))

    # Database & external endpoints
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./streetverism.db"))
    vite_api_base: str = Field(default_factory=lambda: os.getenv("VITE_API_BASE", "http://localhost:8000"))

    # Service coverage & Replay Autostart
    service_bbox: str = Field(default_factory=lambda: os.getenv("SERVICE_BBOX", "80.10,12.80,80.40,13.30"))
    replay_autostart: str = Field(default_factory=lambda: os.getenv("REPLAY_AUTOSTART", "").strip())

    @property
    def cors_origins(self) -> List[str]:
        raw = [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]
        return raw or ["*"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
