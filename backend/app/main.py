"""Main FastAPI application entry point for StreetVerism."""

from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import get_health, router as api_router
from backend.app.config import get_settings
from backend.app.models.state import HealthResponse

settings = get_settings()

app = FastAPI(
    title="StreetVerism API",
    description="Real-Time Crisis Communication & Verified Action Layer for Foreign Tourists During Extreme Weather Events.",
    version=settings.project_version,
    openapi_tags=[
        {"name": "System", "description": "Liveness and operational status"},
        {"name": "Tourist", "description": "Public crisis status, instructions, and tourist check-ins"},
        {"name": "Authority", "description": "Administrative alert publishing and triage dashboard (Protected)"},
        {"name": "Scenario", "description": "Historical replay scenario controls and clock seeking"},
    ],
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
