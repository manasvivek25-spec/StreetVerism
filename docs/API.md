# StreetVerism API Specification (v1)

Base Path: `/api`  
All operational API routes are prefixed with `/api/*`.  
Standard health check endpoints are accessible at both `/health` and `/api/health`.

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
  - Authority endpoints require header: `X-Authority-Key: <AUTHORITY_KEY>`.
  - Missing or invalid key yields `401 Unauthorized` or `403 Forbidden`.
- **Privacy & Retention**:
  - Devices are identified by random client-generated UUIDs (`device_id`).
  - Check-in and report coordinates are rounded to 4 decimal places (~11m precision).
  - Check-in records have a strict 48-hour retention TTL.

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
      "sender": "TNSDMA (demo)",
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
  - `X-Authority-Key: <AUTHORITY_KEY>`
- **Request Body** (Alert payload without `id`):
```json
{
  "source": "official_manual",
  "sender": "TNSDMA",
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
- **Headers**: `X-Authority-Key: <AUTHORITY_KEY>`
- **Response `200 OK`**:
```json
{
  "alerts": [
    {
      "id": "alt_michaung_01",
      "source": "official_manual",
      "sender": "TNSDMA",
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
- **Headers**: `X-Authority-Key: <AUTHORITY_KEY>`
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
- **Headers**: `X-Authority-Key: <AUTHORITY_KEY>`
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
- **Headers**: `X-Authority-Key: <AUTHORITY_KEY>`
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
