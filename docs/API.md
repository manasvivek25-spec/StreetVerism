# StreetVerism API Specification (v1)

Base Path: `/api`  
All operational API routes are prefixed with `/api/*`.  
Standard health check endpoints are accessible at both `/health` and `/api/health`.

---

## Changes since Contract v1 (Team Diff & Additions)

The following table documents all additive fields, envelope wrappers, and behavioral refinements established during backend stabilization, provided for Teams B and C:

| Endpoint / Area | Original Contract v1 | Implemented Addition / Deviation | Rationale & Team Notes |
|---|---|---|---|
| `GET /api/state` | Contained `generated_at` and `reviewed` flag | Added `server_time` (ISO-8601 UTC) and `instructions[].original_en` (`null` when `reviewed=true`; English string when `reviewed=false`) | Enables wall-clock drift auditing during replay; allows tourist UI to show human English fallback alongside machine translation. |
| `POST /api/checkin` | Returned `{"id": "..."}` | Returns `{"id": "...", "recorded_at": "ISO-8601 UTC"}` | Confirms check-in receipt timestamp to tourist client. |
| `GET /api/shelters` | Bare list `[Shelter, ...]` | Enveloped as `{"shelters": [...], "total": int}`; added optional `capacity: int` on shelter items | Consistent envelope convention; lets console/dispatch view max occupancy. |
| `GET /api/alerts?active=true` | Bare list `[Alert, ...]` | Enveloped as `{"alerts": [...], "total": int}` | Consistent envelope convention across all catalog queries. |
| `POST /api/scenario/seek` | Loosely specified `{t}` parameter | Strictly accepts XOR: `{"t": "ISO-8601"}` OR `{"offset_s": int}`. Returns HTTP 422 if both or neither provided. Clamps to bounds. | Disambiguates absolute timestamp seeking vs relative seconds seeking without silent failures. |
| `GET /api/scenario/status` & `POST /api/scenario/start` | Undefined status response schema | Concrete response: `{"name", "mode": "live"\|"replay"\|"mock", "is_running", "paused", "speed", "current_time", "elapsed_s", "scenario_start", "scenario_end", "is_replay"}` | Full clock observability for replay scrubbing UI. |
| `GET /health` & `GET /api/health` | Undefined health response schema | Returns `{"status": "healthy", "mode": "live"\|"replay"\|"mock", "is_replay": bool, "version": str, "server_time": str}` | Standardized health check for Docker, reverse proxies, and team monitoring. |
| Global Headers | No mock header | Response header `X-Mock-Data: 1` present on all `/api/*` and `/health` responses when `MOCK=1`; omitted when `MOCK=0` | Allows frontend to show honest "Mock data" banner without changing JSON payload shapes. |
| Error Responses | Generic HTTP errors | Documented standard error envelopes: 401, 403, 422, 429 schemas | Deterministic error handling across client apps. |

---

## 1. Global Conventions & Standards

- **Coordinates**:
  - Point locations in JSON request and response payloads use decimal degrees: `lat` (latitude) and `lng` (longitude).
  - GeoJSON geometries strictly follow RFC 7946 standard: coordinates are `[lng, lat]` (easting, northing).
- **Bounding Boxes**:
  - Bounding box query parameters follow GIS standard order: `bbox=minLng,minLat,maxLng,maxLat`.
- **Timestamps**:
  - Formatted as ISO-8601 UTC strings: `YYYY-MM-DDTHH:MM:SSZ` (e.g. `2026-10-10T12:00:00Z`).
- **Language Codes**:
  - Standard two-letter ISO 639-1 codes: `en`, `hi`, `ta`, `fr`, `de`, `ja`.
  - Human-reviewed templates: `en`, `hi`, `ta` (`reviewed: true`).
  - Machine-translated languages: `fr`, `de`, `ja` (`reviewed: false`).
- **Replay Mode Consistency**:
  - In REPLAY mode (`is_replay: true`), timestamps (`generated_at`, alert publication times, and evidence `age_s`) are computed against the **scenario clock**, not the real-world server clock, ensuring accurate mathematical decay.
  - The real wall-clock time is exposed in `server_time`.
- **Authentication**:
  - Authority endpoints require header: `X-Authority-Key: $AUTHORITY_KEY`.
  - Missing or invalid key yields `401 Unauthorized` or `403 Forbidden`.
- **Privacy & Retention**:
  - Devices are identified by random client-generated UUIDs (`device_id`).
  - Check-in and report coordinates are rounded to 4 decimal places (~11m precision).
  - Check-in records have a strict 48-hour retention TTL.
- **Mock Mode (`MOCK=1`)**:
  - In mock mode (`MOCK=1`), `/health` and `/api/health` return `"mode": "mock"`. (When a scenario is active, `"mode": "replay"`; in live mode, `"mode": "live"`).
  - Every response across `/api/*` and `/health` includes the response header `X-Mock-Data: 1` when `MOCK=1`, allowing the frontend PWA to display an honest "Mock Data" badge.
  - In live mode (`MOCK=0`), the `X-Mock-Data` header is absent.
  - All mock alerts and shelters are strictly labeled as demonstration data (`sender: "... (demo)"`, `is_demo: true`).

---

## 2. Cell Status Definitions (Vocabulary)

Every H3 resolution-8 cell (~460m edge) is classified into one of five deterministic states:
- `official_hazard`: Cell overlaps an active official hazard alert (area fraction $\ge$ 0.5) with hazard $\ne$ `all_clear`.
- `likely_hazard`: No official alert, but calculated probability $p_{\text{hazard}} \ge 0.80$ and at least 2 independent report clusters.
- `unverified`: Crowd claims exist but fail corroboration thresholds ($p_{\text{hazard}} < 0.80$ or single cluster). Rumors are strictly labeled as unverified.
- `contradicted`: A crowd hazard claim exists, but an official `all_clear` alert covers the cell, or prior probability is very low ($< 0.05$) with no corroborating evidence.
- `clear`: $p_{\text{hazard}} < 0.50$ and no active uncontradicted hazard claims.

---

## 3. Endpoints

### 3.1 System Health
#### `GET /health` and `GET /api/health`
Returns system health and active mode.
- **Response `200 OK`**:
```json
{
  "status": "healthy",
  "mode": "live",
  "is_replay": false,
  "version": "1.0.0",
  "server_time": "2026-10-10T12:00:00Z"
}
```

---

### 3.2 Tourist & Public Endpoints

#### `GET /api/state?lat={lat}&lng={lng}&lang={lang}`
Returns the crisis status, active alerts, verified template instructions, explainable evidence weights, and nearest shelters for a tourist's coordinates.
- **Query Parameters**:
  - `lat` (float, required): -90.0 to 90.0
  - `lng` (float, required): -180.0 to 180.0
  - `lang` (string, optional, default: `en`): `en`, `hi`, `ta`, `fr`, `de`, `ja`
- **Response `200 OK`**:
```json
{
  "cell": "88618925d3fffff",
  "status": "likely_hazard",
  "p_hazard": 0.86,
  "headline_key": "MOVE_TO_HIGHER_GROUND",
  "alerts": [
    {
      "id": "alt_michaung_01",
      "source": "official_manual",
      "sender": "State Disaster Authority (demo)",
      "hazard": "flood",
      "severity": "severe",
      "urgency": "immediate",
      "certainty": "observed",
      "area": {
        "type": "Polygon",
        "coordinates": [[[80.20, 13.00], [80.25, 13.00], [80.25, 13.05], [80.20, 13.05], [80.20, 13.00]]]
      },
      "instruction_keys": ["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS"],
      "params": {},
      "sent_at": "2026-10-10T10:00:00Z",
      "expires_at": "2026-10-10T18:00:00Z",
      "supersedes": null,
      "published_by": "console-operator",
      "is_replay": false
    }
  ],
  "instructions": [
    {
      "key": "MOVE_TO_HIGHER_GROUND",
      "text": "Move to higher ground immediately. Do not wait.",
      "reviewed": true,
      "original_en": "Move to higher ground immediately. Do not wait."
    },
    {
      "key": "AVOID_FLOODED_ROADS",
      "text": "Avoid flooded roads and underpasses.",
      "reviewed": true,
      "original_en": "Avoid flooded roads and underpasses."
    }
  ],
  "evidence": [
    {
      "type": "rain",
      "summary": "Heavy rainfall 3h: 65mm, 24h: 180mm",
      "age_s": 900,
      "weight": 1.45
    },
    {
      "type": "crowd",
      "summary": "3 independent reports of road submersion",
      "age_s": 1200,
      "weight": 1.82
    }
  ],
  "nearest_shelters": [
    {
      "id": "sh_chennai_01",
      "name": "Community Relief Center - Velachery",
      "name_local": "சமூக நிவாரண மையம் - வேளச்சேரி",
      "lat": 12.9815,
      "lng": 80.2180,
      "distance_m": 420.5,
      "open": true,
      "is_demo": true
    }
  ],
  "is_replay": false,
  "generated_at": "2026-10-10T12:00:00Z",
  "server_time": "2026-10-10T12:00:00Z"
}
```

#### `GET /api/cells?bbox={minLng,minLat,maxLng,maxLat}`
Returns a GeoJSON FeatureCollection of evaluated H3 res-8 cells intersecting the bounding box.
- **Query Parameters**:
  - `bbox` (string, required): `minLng,minLat,maxLng,maxLat`
- **Response `200 OK`**:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [80.2154, 12.9810],
            [80.2192, 12.9835],
            [80.2230, 12.9810],
            [80.2230, 12.9760],
            [80.2192, 12.9735],
            [80.2154, 12.9760],
            [80.2154, 12.9810]
          ]
        ]
      },
      "properties": {
        "cell": "88618925d3fffff",
        "status": "likely_hazard",
        "p_hazard": 0.86,
        "updated_at": "2026-10-10T12:00:00Z"
      }
    }
  ]
}
```

#### `GET /api/shelters`
Returns all registered emergency evacuation centers and shelters.
- **Response `200 OK`**:
```json
{
  "shelters": [
    {
      "id": "sh_chennai_01",
      "name": "Community Relief Center - Velachery",
      "name_local": "சமூக நிவாரண மையம் - வேளச்சேரி",
      "lat": 12.9815,
      "lng": 80.2180,
      "open": true,
      "is_demo": true,
      "capacity": 350
    }
  ],
  "total": 1
}
```

#### `GET /api/templates/{lang}`
Returns the verified template set directly for client-side offline caching.
- **Path Parameters**:
  - `lang` (string): `en`, `hi`, `ta`, `fr`, `de`, `ja`
- **Response `200 OK`**:
```json
{
  "lang": "en",
  "reviewed": true,
  "templates": {
    "MOVE_TO_HIGHER_GROUND": "Move to higher ground immediately. Do not wait.",
    "AVOID_FLOODED_ROADS": "Avoid flooded roads and underpasses.",
    "DO_NOT_CROSS_WATER": "Do not attempt to walk or drive through moving water.",
    "SHELTER_AT": "Take shelter immediately at {shelter}.",
    "STAY_INDOORS": "Stay indoors away from windows.",
    "STAY_AWAY_FROM_COAST": "Stay away from coastal waters and beaches.",
    "KEEP_PHONE_CHARGED": "Conserve phone battery and keep devices charged.",
    "ALL_CLEAR": "Conditions are safe. Official all clear.",
    "EMERGENCY_NUMBER": "Emergency Assistance: Dial 112.",
    "FOLLOW_OFFICIAL_ONLY": "Follow official alerts only. Disregard unverified social rumors.",
    "CHECKIN_PROMPT": "Please check in to let emergency teams know your safety status.",
    "UNVERIFIED_WARNING": "Unverified crowd reports in this area. Exercise caution."
  }
}
```

#### `POST /api/reports`
Submits an unverified ground-truth observation (hazard or clear report).
- **Request Body**:
```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "lat": 12.9815,
  "lng": 80.2180,
  "claim": "flooded",
  "text": "Water waist-high near 100ft road"
}
```
*Valid `claim` values: `flooded`, `blocked`, `safe`.*
- **Response `200 OK`**:
```json
{
  "accepted": true,
  "cell": "88618925d3fffff",
  "status": "unverified"
}
```

#### `POST /api/checkin`
Submits a tourist safety status check-in for emergency triage.
- **Request Body**:
```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "lat": 12.9815,
  "lng": 80.2180,
  "state": "need_help",
  "language": "de",
  "group_size": 2,
  "note": "Elderly person in group, need evacuation"
}
```
*Valid `state` values: `safe`, `need_help`.*
- **Response `200 OK`**:
```json
{
  "id": "chk_984f1a02",
  "recorded_at": "2026-10-10T12:00:00Z"
}
```

---

### 3.3 Authority Endpoints (Requires `X-Authority-Key`)

#### `POST /api/alerts`
Publishes a new official hazard alert or all-clear declaration.
- **Headers**:
  - `X-Authority-Key: $AUTHORITY_KEY`
- **Request Body** (Alert payload without `id`):
```json
{
  "source": "official_manual",
  "sender": "State Disaster Authority (demo)",
  "hazard": "flood",
  "severity": "extreme",
  "urgency": "immediate",
  "certainty": "observed",
  "area": {
    "type": "Polygon",
    "coordinates": [[[80.20, 13.00], [80.25, 13.00], [80.25, 13.05], [80.20, 13.05], [80.20, 13.00]]]
  },
  "instruction_keys": ["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS"],
  "params": {},
  "sent_at": "2026-10-10T12:00:00Z",
  "expires_at": "2026-10-10T20:00:00Z",
  "supersedes": null,
  "published_by": "commissioner-duty",
  "is_replay": false
}
```
- **Response `201 Created`**: Returns created `Alert` with server-assigned `id`.

#### `GET /api/alerts?active=true`
Lists active (non-expired, non-superseded) official alerts.
- **Headers**: `X-Authority-Key: $AUTHORITY_KEY`
- **Response `200 OK`**:
```json
{
  "alerts": [
    {
      "id": "alt_michaung_01",
      "source": "official_manual",
      "sender": "State Disaster Authority (demo)",
      "hazard": "flood",
      "severity": "extreme",
      "urgency": "immediate",
      "certainty": "observed",
      "area": {
        "type": "Polygon",
        "coordinates": [[[80.20, 13.00], [80.25, 13.00], [80.25, 13.05], [80.20, 13.05], [80.20, 13.00]]]
      },
      "instruction_keys": ["MOVE_TO_HIGHER_GROUND"],
      "params": {},
      "sent_at": "2026-10-10T12:00:00Z",
      "expires_at": "2026-10-10T20:00:00Z",
      "supersedes": null,
      "published_by": "commissioner-duty",
      "is_replay": false
    }
  ],
  "total": 1
}
```

#### `DELETE /api/alerts/{id}`
Immediately expires an active alert.
- **Headers**: `X-Authority-Key: $AUTHORITY_KEY`
- **Response `200 OK`**:
```json
{
  "ok": true,
  "id": "alt_michaung_01",
  "expired_at": "2026-10-10T12:05:00Z"
}
```

#### `GET /api/checkins`
Fetches individual check-in records alongside aggregated clusters at H3 resolution 7 (~1.2km) for high-level rescue triage.
- **Headers**: `X-Authority-Key: $AUTHORITY_KEY`
- **Response `200 OK`**:
```json
{
  "items": [
    {
      "id": "chk_984f1a02",
      "device_id": "550e8400-e29b-41d4-a716-446655440000",
      "lat": 12.9815,
      "lng": 80.2180,
      "state": "need_help",
      "language": "de",
      "group_size": 2,
      "note": "Elderly person in group, need evacuation",
      "cell7": "87618925dffffff",
      "handled": false,
      "recorded_at": "2026-10-10T12:00:00Z"
    }
  ],
  "clusters": [
    {
      "cell7": "87618925dffffff",
      "count": 5,
      "need_help": 2,
      "languages": {
        "de": 2,
        "en": 2,
        "ja": 1
      }
    }
  ]
}
```

#### `PATCH /api/checkins/{id}`
Marks a check-in as handled by rescue dispatch.
- **Headers**: `X-Authority-Key: $AUTHORITY_KEY`
- **Request Body**:
```json
{
  "handled": true
}
```
- **Response `200 OK`**: Returns updated check-in item.

---

### 3.4 Scenario & Replay Endpoints

#### `POST /api/scenario/start`
Starts a historical scenario playback (e.g., `michaung_replay`).
- **Request Body**:
```json
{
  "name": "michaung_replay",
  "speed": 1.0
}
```
- **Response `200 OK`**: Returns scenario status.

#### `POST /api/scenario/seek`
Jumps to a specific time within the active scenario. Accepts **exactly one** of `t` (ISO-8601 UTC) or `offset_s` (integer seconds from scenario start). Returns `422 Unprocessable Entity` if both or neither are provided.
- **Request Body (Option A - ISO-8601)**:
```json
{
  "t": "2023-12-04T08:00:00Z"
}
```
- **Request Body (Option B - Offset seconds)**:
```json
{
  "offset_s": 7200
}
```
- **Response `200 OK`**: Returns updated scenario status (clamped to scenario start/end bounds).

#### `POST /api/scenario/reset`
Stops scenario replay and returns the backend to `live` mode.
- **Response `200 OK`**:
```json
{
  "ok": true,
  "mode": "live",
  "is_replay": false
}
```

#### `GET /api/scenario/status`
Returns the current replay clock and state. When no scenario is active: `is_running: false`, `mode: "live"`.
- **Response `200 OK`**:
```json
{
  "name": "michaung_replay",
  "mode": "replay",
  "is_running": true,
  "paused": false,
  "speed": 2.0,
  "current_time": "2023-12-04T08:00:00Z",
  "elapsed_s": 7200,
  "scenario_start": "2023-12-04T06:00:00Z",
  "scenario_end": "2023-12-04T22:00:00Z",
  "is_replay": true
}
```

---

### 3.5 Stretch Endpoints

#### `GET /api/route?from_lat={lat}&from_lng={lng}&to_shelter={id}&lang={lang}`
Hazard-aware route avoiding cells marked `official_hazard` or `likely_hazard`.
- **Response `200 OK`**:
```json
{
  "route": {
    "type": "LineString",
    "coordinates": [
      [80.2180, 12.9815],
      [80.2175, 12.9820],
      [80.2170, 12.9825]
    ]
  },
  "steps": [
    "Head north on Trunk Rd",
    "Turn left away from waterlogged section on 5th Ave"
  ],
  "distance_m": 850.0,
  "hazard_cells_avoided": 2
}
```

---

### 3.6 Standard Error Responses

- **401 Unauthorized** (Missing or empty `X-Authority-Key` on protected endpoints):
```json
{
  "detail": "Missing required header: X-Authority-Key"
}
```

- **403 Forbidden** (Invalid `X-Authority-Key` credentials):
```json
{
  "detail": "Invalid X-Authority-Key credentials"
}
```

- **422 Unprocessable Entity** (Validation error, e.g. XOR violation on scenario seek or coordinate bounds):
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Payload must contain exactly one of 't' or 'offset_s'",
      "input": {}
    }
  ]
}
```

- **429 Too Many Requests** (Rate limit exceeded on crowd reports or check-in submissions):
```json
{
  "detail": "Rate limit exceeded. Too many requests submitted from this device. Please retry shortly."
}
```

---

### 3.7 Changes Since Contract v1

The operational service layer and live API retain full backward compatibility with v1 clients while adding explicit metadata and controls:

1. **Additive Metadata Fields**:
   - `StateResponse`: adds `coverage` (`"covered"` | `"outside"`), `mode` (`"live"` | `"replay"` | `"mock"`).
   - `HealthResponse`: adds `mode` (`"live"` | `"replay"` | `"mock"`), `replay` (object with `label`, `disclaimer`, `sim_time` during replay).
   - `ScenarioStatus`: adds `start_time`, `end_time`, `duration_s`, `finished`, `bookmarks`, `label`, `disclaimer`.
   - `ScenarioSeek`: supports seeking by `bookmark` name in addition to `t` and `offset_s` (exact one-of required).
   - `CheckinCluster`: adds `unhandled_need_help` integer counter for incident commander triage.
   - `RenderedInstruction`: carries `original_en` string when `reviewed=false` (e.g. machine-translated de/fr/ja); `original_en=null` when `reviewed=true` (en/hi/ta).

2. **Standard Error Shapes**:
   - `401 Unauthorized`: Missing `X-Authority-Key` header on `/api/alerts` or `/api/checkins`.
   - `403 Forbidden`: Invalid `X-Authority-Key`.
   - `404 Not Found`: Alert or Checkin ID not found, or scenario file not found.
   - `409 Conflict`: Manual alert publication attempted during active scenario replay without override.
   - `422 Unprocessable Entity`: Coordinate out of range, bbox delta > 0.3° or > 3,000 cells, invalid claim, or seek XOR violation.
   - `429 Too Many Requests`: 600s per-device rate limit exceeded on `/api/reports`.

3. **Operational Limits**:
   - Max bbox span for `/api/cells`: 0.3° per side.
   - Max evaluated cells per request: 3,000 H3 resolution-8 cells.
   - GeoJSON geometry vertex coordinate precision: 5 decimal places (~1.1 meter resolution).
   - Check-in retention period: 48 hours (hourly automated background purge).
   - Privacy guarantee: `device_id` is stripped from `/api/checkins` responses in live and replay modes; coordinates rounded to 4 decimals at write time.

