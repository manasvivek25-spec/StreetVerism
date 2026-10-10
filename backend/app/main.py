"""Main FastAPI application entry point for StreetVerism."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.app.api.routes import (
    autostart_replay,
    get_checkin_repo,
    get_health,
    get_shelter_repo,
    init_scenario,
    router as api_router,
)
from backend.app.config import get_settings
from backend.app.db import init_db
from backend.app.models.state import HealthResponse
from backend.app.services import load_and_validate_templates, seed_shelters_from_file

# Configure structured logging with exact logger name
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("streetverism")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events with honest mode logging."""
    settings = get_settings()
    retention_task = None
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

        # Check single-worker concurrency guarantee
        web_concurrency = int(os.getenv("WEB_CONCURRENCY", "1"))
        if web_concurrency > 1:
            logger.warning(
                "CRITICAL WARNING: WEB_CONCURRENCY is %d. "
                "StreetVerism relies on in-memory state (scenario clock, rate limiters, route cache). "
                "Deploy with exactly ONE worker (--workers 1).",
                web_concurrency,
            )

        # 1. Initialize SQLite schema idempotently
        init_db(settings.database_url)

        # 2. Seed shelters from data/shelters.json
        project_root = Path(__file__).resolve().parent.parent.parent
        shelters_file = project_root / "data" / "shelters.json"
        if shelters_file.exists():
            seed_shelters_from_file(shelters_file, get_shelter_repo())

        # 3. Load & validate multilingual emergency templates
        templates_dir = project_root / "data" / "templates"
        if templates_dir.exists():
            load_and_validate_templates(templates_dir)

        # 4. Scenario pre-initialization & REPLAY_AUTOSTART check
        scenario_path = project_root / "data" / "scenarios" / "michaung_replay.json"
        if scenario_path.exists() and shelters_file.exists():
            init_scenario(scenario_path, shelters_file)

        if settings.replay_autostart:
            autostart_replay(settings.replay_autostart)
            logger.info("Replay scenario auto-started at bookmark '%s'", settings.replay_autostart)

        # 5. Background retention task for checkins (purge records older than 48h hourly)
        async def retention_worker():
            while True:
                try:
                    await asyncio.sleep(3600)
                    now_utc = datetime.now(timezone.utc)
                    cutoff_iso = (now_utc - timedelta(hours=48)).isoformat()
                    get_checkin_repo().delete_older_than(cutoff_iso)
                    logger.debug("Hourly check-in retention purge completed.")
                except asyncio.CancelledError:
                    break
                except Exception as ex:
                    logger.error("Error during check-in retention purge: %s", ex)

        retention_task = asyncio.create_task(retention_worker())

    yield

    if retention_task is not None:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass


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

# Configure CORS and GZip middleware
cors_allow_all = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not cors_allow_all,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "X-Authority-Key", "Accept", "Authorization"],
    expose_headers=["X-Mock-Data"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


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
