# Disclosures & Attribution

This document tracks all third-party libraries, APIs, external data sources, and AI coding assistants utilized in **StreetVerism** during hackathon development.

---

## 1. AI Tools Used

- **Google Antigravity**: Primary AI pair programming assistant and agent environment used for codebase architecture, backend service implementation, test suites, and deployment orchestration.
- **Manus**: Exploratory agent tool used during initial problem framing and ideation.
- **Claude (Anthropic)**: LLM used for multi-agent synthesis, contract validation, and conceptual reviews.

---

## 2. External APIs, Data Sources & Attributions

### OpenRouteService / HeiGIT
- **Provider**: Heidelberg Institute for Geoinformation Technology (HeiGIT) (`https://api.openrouteservice.org`).
- **Terms of Service**: Subject to [HeiGIT Terms of Service](https://heigit.org/terms-of-service/).
- **Tier & Limits**: OpenRouteService Free Tier API key used for calculating pedestrian evacuation directions. Gracefully falls back to direct-line bearing if rate limits or network failures occur.
- **Attribution**: `"© openrouteservice by HeiGIT | Map data © OpenStreetMap contributors"` (routing results licensed under CC-BY-SA 4.0).
- **Privacy Safeguards**: Coordinates are sent strictly ephemerally for route calculations. The server never stores, logs, or tracks user GPS routes or location history.

### OpenStreetMap (OSM)
- **License**: Map data is © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, licensed under the Open Database License (ODbL) 1.0.
- **Attribution Wording**: `"© OpenStreetMap contributors"`.
- **Road Network**: Evacuation route calculations leverage OSM pedestrian topology.

### Map Tile Provider (Frontend)
- **Tile URL**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
- **Provider**: OpenStreetMap standard tile servers.
- **Attribution Wording**: `&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors`.

### Typography & Icons
- **Typography**: System font stack prioritizing Inter: `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`.
- **Icons**: Standard native Unicode emojis (🚨, 📍, ⚠️, 🔐, 🛡️, ✓) and inline SVG vectors. No external icon font libraries or CDN font packages are loaded.

---

## 3. Libraries & Dependencies

### Backend Dependencies (`backend/requirements.txt`)

| Package | Version Constraint | License | Purpose |
|---|---|---|---|
| **fastapi** | `>=0.110.0` | MIT | High-performance ASGI web framework for REST endpoints and OpenAPI documentation |
| **uvicorn[standard]** | `>=0.28.0` | BSD-3-Clause | Production ASGI web server runner |
| **pydantic** | `>=2.6.0` | MIT | Data parsing, serialization, and schema validation |
| **h3** | `==4.5.0` | Apache-2.0 | Uber's Hexagonal Hierarchical Spatial Indexing System (resolution 8 cells) |
| **shapely** | `==2.2.0` | BSD-3-Clause | Geometric polygon intersection, containment, and spatial clipping |
| **defusedxml** | `==0.7.1` | PSF | Safe XML parsing protecting against XML entity expansion (Billion Laughs) and injection |
| **httpx** | `>=0.27.0` | BSD-3-Clause | Asynchronous HTTP client for upstream API requests |
| **pytest** | `>=8.0.0` | MIT | Unit, integration, and contract test runner |
| **python-multipart** | `>=0.0.9` | Apache-2.0 | Multipart form-data parser for FastAPI request parsing |

### Frontend Dependencies (`web/package.json`)

| Package | Version | License | Purpose |
|---|---|---|---|
| **react** | `^19.2.8` | MIT | Declarative component UI library |
| **react-dom** | `^19.2.8` | MIT | DOM rendering layer for React |
| **leaflet** | `^1.9.4` | BSD-2-Clause | Mobile-friendly interactive mapping library for Leaflet tiles and markers |
| **@types/leaflet** | `^1.9.22` | MIT | TypeScript definitions for Leaflet |
| **vite** | `^8.3.0` | MIT | Next-generation frontend build tool and dev server |
| **@vitejs/plugin-react** | `^6.1.1` | MIT | React Fast Refresh support for Vite |
| **typescript** | `~6.0.2` | Apache-2.0 | Typed superset of JavaScript |
| **oxlint** | `^1.81.0` | MIT | Rust-based high-performance JavaScript/TypeScript linter |
| **@types/react** | `^19.2.18` | MIT | TypeScript type definitions for React |
| **@types/react-dom** | `^19.2.7` | MIT | TypeScript type definitions for React DOM |
| **@types/node** | `^24.13.3` | MIT | TypeScript type definitions for Node.js runtime |

---

## 4. Replay Scenario & Data Integrity Disclosures

- **Hand-Authored Scenario Data**: The Cyclone Michaung replay scenario in `data/scenario.json` contains hand-authored, approximate spatial keyframes and timestamps created solely for demonstration and system evaluation. It is an illustrative reconstruction, not real or official meteorological observations.
- **Fictional Shelters**: The relief centers registered in `data/shelters.json` are fictional demo facilities created for evaluation.
- **Fabricated CAP Feed Sample**: The Common Alerting Protocol file `data/sample_cap.xml` is a fabricated sample alert created to demonstrate CAP 1.2 XML ingestion. No live government CAP feed is connected.
- **No Live Weather Ingestion**: Live mode operates with `weather_available: false`. Live external weather ingestion (such as Open-Meteo) is not connected in the production deployment.
- **No HDX Feed**: No live or external Humanitarian Data Exchange (HDX) data feeds are used.
