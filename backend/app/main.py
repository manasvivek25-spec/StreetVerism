"""Main FastAPI application entry point for StreetVerism."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import get_health, router as api_router
from backend.app.config import get_settings
from backend.app.models.state import HealthResponse

# Configure structured logging with exact logger name
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("streetverism")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events with honest mode logging."""
    settings = get_settings()
    if settings.mock:
        logger.info("StreetVerism backend started in MOCK mode (MOCK=1). Serving deterministic mock datasets.")
        env_name = os.getenv("ENVIRONMENT", os.getenv("ENV", "")).lower()
        if env_name in ("prod", "production"):
            logger.warning(
                "CRITICAL WARNING: MOCK=1 is enabled in a PRODUCTION environment (%s)! "
                "Real weather and alert ingestion feeds are bypassed.",
                env_name,
            )
    else:
        logger.info("StreetVerism backend started in LIVE mode (MOCK=0). Real external integrations enabled.")
    yield


settings = get_settings()

app = FastAPI(
    title="StreetVerism API",
    description="Real-Time Crisis Communication & Verified Action Layer for Foreign Tourists During Extreme Weather Events.",
    version=settings.project_version,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "System", "description": "Liveness and operational status"},
        {"name": "Tourist", "description": "Public crisis status, instructions, and tourist check-ins"},
        {"name": "Authority", "description": "Administrative alert publishing and triage dashboard (Protected)"},
        {"name": "Scenario", "description": "Historical replay scenario controls and clock seeking"},
    ],
)

# Configure CORS middleware
cors_allow_all = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not cors_allow_all,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "X-Authority-Key", "Accept", "Authorization"],
    expose_headers=["X-Mock-Data"],
)


@app.middleware("http")
async def add_mock_header_middleware(request: Request, call_next):
    """Expose X-Mock-Data: 1 response header across all endpoints when MOCK=1."""
    response = await call_next(request)
    current_settings = get_settings()
    if current_settings.mock and (request.url.path.startswith("/api") or request.url.path == "/health"):
        response.headers["X-Mock-Data"] = "1"
    return response


# Root-level health endpoint (requirement: both /health and /api/health work)
@app.get("/health", response_model=HealthResponse, tags=["System"], summary="Root health check")
async def root_health() -> HealthResponse:
    """Root health check returning server status and wall-clock timestamp."""
    return await get_health()


# Mount all application endpoints under /api/*
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
