"""Configuration and environment settings for StreetVerism."""

import os
from functools import lru_cache
from typing import List
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Project identification
    project_name: str = "StreetVerism"
    project_version: str = "1.0.0"

    # Mock mode flag (MOCK=1)
    mock: bool = Field(default_factory=lambda: os.getenv("MOCK", "1").lower() in ("1", "true", "yes"))

    # Security
    authority_key: str = Field(default_factory=lambda: os.getenv("AUTHORITY_KEY", "beacon-authority-secret-key-2026"))

    # CORS configuration
    cors_origins_str: str = Field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*"))

    # Database & external endpoints
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./streetverism.db"))
    vite_api_base: str = Field(default_factory=lambda: os.getenv("VITE_API_BASE", "http://localhost:8000"))

    @property
    def cors_origins(self) -> List[str]:
        raw = [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]
        return raw or ["*"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
