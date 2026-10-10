# StreetVerism Deployment & Operational Guide

This document describes environment configuration, startup commands, health checks, and deployment verification for the StreetVerism backend.

---

## 1. Operating Modes

StreetVerism operates in two distinct execution modes:

| Mode | Flag | Description |
| :--- | :--- | :--- |
| **Live / Operational** | `MOCK=0` | Full Bayesian trust engine, real database persistence (SQLite), multilingual template catalog validation, and scenario replay simulation. |
| **Deterministic Mock** | `MOCK=1` | Isolated deterministic mock datasets for offline UI prototyping and frontend testing. Injects `X-Mock-Data: 1` header. |

---

## 2. Environment Variables

All secrets and operational switches are injected via environment variables (or `.env` file). **Never commit secrets to the repository.**

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `MOCK` | No | `1` | `0` for live/replay operation; `1` for deterministic mock mode. |
| `AUTHORITY_KEY` | **Yes (in MOCK=0)** | *None* | Secure shared secret required for administrative endpoints (`/api/alerts`, `/api/checkins`). Checked via constant-time comparison. |
| `DATABASE_URL` | No | `sqlite:///./streetverism.db` | SQLite database URI or connection path. |
| `SERVICE_BBOX` | No | `80.10,12.80,80.40,13.30` | Spatial bounding box for Chennai coverage (`min_lng,min_lat,max_lng,max_lat`). |
| `REPLAY_AUTOSTART` | No | `""` (empty) | If set (e.g. `golden_moment`), automatically loads the Michaung replay scenario, seeks to that bookmark, and keeps playback **PAUSED** on startup (play/seek via scenario API). |
| `ROUTING_PROVIDER` | No | `"openrouteservice"` | Routing provider adapter name. |
| `ROUTING_BASE_URL` | No | `"https://api.openrouteservice.org"` | Base URL for the directions provider API. |
| `ROUTING_API_KEY` | No | *None* | Production API key for OpenRouteService (sent via Authorization header; never committed). |
| `ROUTING_DAILY_BUDGET` | No | `1500` | Maximum daily provider requests before falling back to direct line. |
| `ROUTING_PER_MIN` | No | `30` | Token bucket provider rate limit per minute. |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed origins (e.g. `http://localhost:5173,https://streetverism.app`). |
| `PORT` | No | `8000` | Port for the Uvicorn web server. |

---

## 3. Server Startup

> [!IMPORTANT]
> **Single Worker Requirement**: StreetVerism relies on in-memory state for rate limiters, token buckets, route LRU caches, and the simulation replay clock. Always run with exactly **ONE** worker (`--workers 1`). A startup warning is emitted if `WEB_CONCURRENCY > 1`.

### Prerequisites
- Python 3.11+
- Virtual environment with pinned dependencies installed:
  ```bash
  pip install -r requirements.txt
  ```

### Production / Live Mode Startup (`MOCK=0`)
```bash
export MOCK=0
export AUTHORITY_KEY="your-strong-production-authority-secret"
export DATABASE_URL="sqlite:///./data/streetverism.db"
export ROUTING_API_KEY="your-openrouteservice-api-key"

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Live Replay Demo Startup (`MOCK=0` + `REPLAY_AUTOSTART`)
To run a live replay demonstration pre-seeded at the peak emergency bookmark (`golden_moment`), with the simulation clock **PAUSED** upon boot:
```bash
export MOCK=0
export AUTHORITY_KEY="demo-authority-secret"
export REPLAY_AUTOSTART="golden_moment"

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Offline Mock Mode Startup (`MOCK=1`)
```bash
export MOCK=1
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. Verification & Health Checks

Verify backend readiness using `curl`:

### 1. Root Liveness & Operating Mode
```bash
curl -i http://localhost:8000/health
```
**Expected Response (MOCK=0 Live):**
```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "healthy",
  "mode": "live",
  "is_replay": false,
  "version": "1.0.0",
  "server_time": "2026-10-10T12:00:00.000000Z",
  "replay": null
}
```

### 2. Tourist Crisis State (Velachery Bounding Box)
```bash
curl "http://localhost:8000/api/state?lat=12.9815&lng=80.2180&lang=en"
```
**Expected Response:**
- Returns `status` (`official_hazard`, `likely_hazard`, `unverified`, `contradicted`, or `clear`).
- Returns `coverage: "covered"`.
- Returns human-reviewed localized safety instructions (without unrendered placeholders).

### 3. Evaluated H3 Res-8 Cells
```bash
curl "http://localhost:8000/api/cells?bbox=80.20,12.98,80.25,13.02"
```
**Expected Response:**
- Standard GeoJSON `FeatureCollection`.
- Coordinate coordinates rounded to 5 decimal places.
- Header includes `Content-Encoding: gzip` when client sends `Accept-Encoding: gzip`.

### 4. Protected Authority Dashboard Triage
```bash
curl -H "X-Authority-Key: your-strong-production-authority-secret" \
     http://localhost:8000/api/checkins
```
**Expected Response:**
- Returns `items` (device IDs stripped for privacy) and aggregated `clusters` (H3 res-7).

---

## 5. Storage & Persistence Notes

- **SQLite Database Path**: By default, SQLite stores data at `./streetverism.db`. In containerized environments (Docker, Kubernetes, fly.io), mount a persistent volume to the database folder (e.g. `/data/streetverism.db`) so check-ins, manual alerts, and reports persist across container restarts.
- **Automated Retention Purge**: An asynchronous worker executes every hour to purge check-ins older than 48 hours according to data privacy requirements.
