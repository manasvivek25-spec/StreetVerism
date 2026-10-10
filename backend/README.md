# StreetVerism Backend

The StreetVerism backend is a high-reliability emergency crisis navigation and situational awareness service designed for tourists and local residents during acute disaster events (e.g., urban flooding).

---

## 1. Core Architecture

The backend consists of four primary subsystems:

1. **Bayesian Trust Engine (`backend/app/trust/`)**:
   - Evaluates acute hazard probability $P(\text{hazard})$ for each H3 resolution-8 cell (~460m across).
   - Combines official alerts (CAP 1.2), topographical priors, meteorological signals, and decayed crowd reports.
   - Deterministic, explainable Bayesian classification (`official_hazard`, `likely_hazard`, `unverified`, `contradicted`, `clear`).

2. **Service Layer & Data Context (`backend/app/services/`)**:
   - `DataContext`: Immutable per-request state encapsulating temporal, alert, report, and weather state.
   - Strict isolation between live mode (`MOCK=0`, SQLite persistence, wall-clock time) and replay simulation (`ScenarioClock`, closed-world timeline, `ReplayOverlay`).

3. **Hazard-Aware Safe Routing (`backend/app/routing/`)**:
   - `GET /api/route`: Evaluates acute hazard polygons, selects nearest vetted emergency shelter, applies provider polygon avoidance limits (200 km² area, 20 km extent), and falls back to straight-line direction with clear warnings (`routing_unavailable`) when necessary.
   - Generates universal deep links (`maps_urls`) for Google Maps, Apple Maps, and RFC 5870 Geo URIs.

4. **Incident Command & Tourist Check-in (`backend/app/api/`)**:
   - `POST /api/checkin` and `GET /api/checkins`: Anonymous safety status logging with neighborhood triage clustering (H3 res-7 parent cells) and 48-hour automated wall-clock retention purging.
   - Device IDs and personal data are strictly excluded from all public and authority responses.

---

## 2. Operating Modes

- **Live Mode (`MOCK=0`)**:
  - Full SQLite database persistence.
  - Active Bayesian trust engine and scenario replay playback.
  - Enforces `X-Authority-Key` for administrative endpoints.
- **Deterministic Mock Mode (`MOCK=1`)**:
  - Isolated static dataset handlers for offline frontend prototyping.
  - Injects `X-Mock-Data: 1` response header.

---

## 3. Operational Guarantees & Privacy

- **Single Worker Requirement**: All rate limiters, token buckets, route LRU caches, and simulation clocks are in-process. Deploy with exactly **ONE** Uvicorn worker (`--workers 1`). A startup warning is logged if `WEB_CONCURRENCY > 1`.
- **Zero PII Logging**: Logging is strictly audit-clean. Device identifiers, user coordinates, notes, and personal client IPs are never written to server stdout/stderr logs.
- **Wall-Clock Check-ins**: Tourist check-ins always record real-world wall-clock UTC timestamps, even during historical replay simulation, preventing premature purging and ensuring correct chronological triage ordering.
- **Rate Limiting**:
  - Reports: 1 report per cell per device per 600 seconds (429 with `Retry-After`).
  - Check-ins: 15 check-ins per minute per device/IP (429 with `Retry-After`).
  - Safe Route: 30 requests per minute per device/IP (429 with `Retry-After`).

---

## 4. Running Locally & Testing

```bash
# Run test suite
pytest

# Start live backend with replay paused at golden_moment
MOCK=0 REPLAY_AUTOSTART=golden_moment AUTHORITY_KEY=dev-secret uvicorn backend.app.main:app --port 8000 --workers 1
```
