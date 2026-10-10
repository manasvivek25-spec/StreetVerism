# StreetVerism Hazard-Aware Safe Routing

This document details the architecture, hazard avoidance algorithms, OpenRouteService integration, and fallback behaviors of the StreetVerism evacuation routing engine (`/api/route`).

---

## 1. Overview & Operational Goal

During extreme hydrological disasters, standard GPS navigation applications (Google Maps, Apple Maps) compute the fastest path along roads without awareness of submerged underpasses, breached canals, or officially cordoned flood zones.

StreetVerism computes **hazard-aware evacuation routes** for tourists seeking shelter:
1. Identifies verified open relief centres whose enclosing H3 res-8 cells are not hazardous.
2. Converts active hazard zones into geometric avoidance boundaries (*avoid polygons*).
3. Requests pedestrian turn-by-turn directions from OpenRouteService (HeiGIT) with strict avoidance constraints.
4. Performs server-side spatial post-validation to verify the calculated route does not intersect known hazard boundaries.
5. Emits structured navigation steps, hazard proximity warnings, and deep links to native maps apps.
6. Seamlessly falls back to direct-line compass bearings if external routing is offline, rate-limited, or unconfigured.

---

## 2. Routing Pipeline Architecture

```
User Coordinates (lat, lng) + Optional Target Shelter
                      |
                      v
       [ 1. Safe Destination Selection ]
       - Filter open shelters in data/shelters.json
       - Assess enclosing H3 res-8 cells
       - Exclude shelters in official_hazard or likely_hazard
                      |
                      v
       [ 2. Hazard Avoid Set Geometry ]
       - Extract all cells evaluated as official_hazard or likely_hazard
       - (Unverified rumor cells are NEVER avoided; emit warning instead)
       - Exclude user origin cell and destination shelter cell
       - Filter cells to corridor bounding box + buffer (0.03 deg ~ 3.3 km)
       - Shapely unary_union to merge adjacent hexagons
       - Enforce ORS limits: max 200 km², max 20 km extent, max 200 vertices
                      |
                      v
          ROUTING_API_KEY Available & Quota OK?
                 /                     \
               Yes                      No
                v                        v
   [ 3. OpenRouteService v2 API ]   [ 4. Direct-Line Fallback ]
   - POST /v2/directions/foot-walking - Geodesic straight-line LineString
   - avoid_polygons GeoJSON MultiPoly  - Compass azimuth bearing
   - Token bucket + daily budget check - Warnings: routing_unavailable
                |                        |
                v                        |
   [ 5. Post-Validation ]                |
   - Shapely route.intersects(hazard)    |
   - If intersected: add warning         |
                \                        /
                 v                      v
        [ 6. Structured Evacuation Response ]
        - Geometry (GeoJSON LineString)
        - Turn-by-turn steps & maneuvers
        - Warnings (unverified_reports_nearby, etc.)
        - External deep links (Google / Apple Maps)
```

---

## 3. Safe Destination Selection (`backend/app/routing/destinations.py`)

- **Candidate Filtering**: Only relief centres with `open == True` are evaluated.
- **Cell Safety Check (`is_shelter_safe`)**:
  - Resolves shelter coordinates to H3 resolution-8 cell (`latlng_to_cell(lat, lng, 8)`).
  - Inspects Bayesian trust assessment for that cell.
  - A shelter is marked unsafe if its status is `official_hazard` or `likely_hazard`.
  - Shelters in `unverified`, `contradicted`, or `clear` are eligible.
- **Azimuth Bearing & Compass (`calculate_initial_bearing`, `bearing_to_compass`)**:
  - Calculates initial forward azimuth in degrees $[0.0, 360.0)$:
    $$\theta = \operatorname{atan2}(\sin(\Delta\lambda)\cos(\varphi_2), \cos(\varphi_1)\sin(\varphi_2) - \sin(\varphi_1)\cos(\varphi_2)\cos(\Delta\lambda))$$
  - Maps bearing to 8-point compass sector (`N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`).

---

## 4. Hazard Avoid Set Geometry (`backend/app/routing/avoid.py`)

- **Hazard Inclusions**: Only cells classified as `official_hazard` or `likely_hazard` are included in the avoid set.
- **Rumor Policy**: Cells classified as `unverified` are **never** placed into the avoid polygon, preventing malicious rumor injection from blocking vital evacuation arteries. Instead, proximity to unverified cells triggers an informational warning (`unverified_reports_nearby`).
- **Endpoint Protection**: The user's origin H3 cell and the destination shelter H3 cell are explicitly pruned from the avoid set so routing engines can depart and arrive without false collision errors.
- **Corridor Pruning**: Cells outside the corridor bounding box (expanded by a default buffer of $0.03^\circ \approx 3.3\text{ km}$) are pruned to minimize geometry size.
- **OpenRouteService Constraint Guardrails**:
  - **Max Area**: Clamped to $\le 200.0\text{ km}^2$.
  - **Max Spatial Extent**: Clamped to $\le 20.0\text{ km}$.
  - **Max Vertices**: Clamped to $\le 200$ boundary vertices via convex hull simplification if vertex count exceeds threshold.

---

## 5. Upstream ORS Integration (`backend/app/routing/ors_adapter.py`)

- **Endpoint**: `https://api.openrouteservice.org/v2/directions/foot-walking/geojson`
- **Authentication**: `Authorization` HTTP header with `ROUTING_API_KEY`.
- **Quota Management (`RoutingQuotaManager`)**:
  - Token bucket rate limiter: Default 30 requests/minute (configurable via `ROUTING_PER_MIN`).
  - Daily budget cap: Default 1,500 requests/day (configurable via `ROUTING_DAILY_BUDGET`).
- **Post-Validation**:
  - The returned route `LineString` is tested against the Shapely hazard union.
  - If the computed route intersects a hazard zone, `route_intersects_hazard` warning is appended.
- **Attribution**: `"© openrouteservice by HeiGIT | Map data © OpenStreetMap contributors"` (CC-BY-SA 4.0).

---

## 6. Failure Tolerance & Fallbacks

The routing service guarantees a valid response under all adverse conditions:

| Condition | Response Kind | Warnings Appended |
|---|---|---|
| `ROUTING_API_KEY` missing or unset | `direct_line` | `routing_unavailable` |
| ORS HTTP 429 (Rate Limit Exceeded) | `direct_line` | `routing_unavailable` |
| Upstream network timeout / connection error | `direct_line` | `routing_unavailable` |
| Avoid set completely blocks all pedestrian roads | `direct_line` | `avoid_geometry_fallback`, `routing_unavailable` |
| Unverified rumor clusters within 500m of route | *As evaluated* | `unverified_reports_nearby` |
| Origin is outside service bounding box | `direct_line` | `outside_coverage`, `routing_unavailable` |

---

## 7. Caching & Performance

- **In-Memory LRU Route Cache**:
  - Cache Key: `(origin_cell_res8, dest_shelter_id, profile, active_hazard_cells_hash)`.
  - TTL: 15 minutes (`900` seconds).
  - Max entries: 500.
  - Invalidation: Cache is automatically bypassed when `reroute=true` is requested.
- **Client Rate Limiting**:
  - 30 requests per minute per IP / client identifier. HTTP 429 with `Retry-After: 60` on violation.

---

## 8. External Map Links & Limitations

- `/api/route` emits external navigation deep links (`maps_urls.google` and `maps_urls.apple`) via `generate_maps_urls`.
- **Honesty Disclosure**: External applications (Google Maps, Apple Maps) navigate along standard civilian roads and **do not** incorporate real-time flood polygons. The tourist UI explicitly warns users that external navigation apps lack flood awareness.
