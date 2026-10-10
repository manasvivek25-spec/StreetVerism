# Disclosures & Attribution

This document tracks all third-party libraries, APIs, external data sources, and AI coding assistants utilized in **StreetVerism** during hackathon development.

---

## 1. AI Tools Used
- **Google Antigravity**: Primary AI pair programming assistant and agent environment used for codebase architecture, backend service implementation, test suites, and deployment orchestration.
- **Manus**: Exploratory agent tool used during initial problem framing and ideation.
- **Claude (Anthropic)**: LLM used for multi-agent synthesis, contract validation, and conceptual reviews.
- **Google Stitch**: UI and design prototyping tool used for visual theme exploration and component scaffolding.

---

## 2. External APIs & Data Sources

- **Open-Meteo Weather API**:
  - Source: `https://api.open-meteo.com/v1/forecast` (query params: `latitude`, `longitude`, `hourly=precipitation`, `past_hours=24`, `forecast_days=1`).
  - Source Nature: Numerical weather forecast model data (not real-time radar or rain gauge measurements).
  - License: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
  - Required Attribution: *"Weather data by Open-Meteo.com"*.
  - Technical safeguards: Spatial grid quantization (0.1° bins), 15-minute in-memory LRU cache, and graceful direct-line / offline fallback on timeouts or HTTP 429.

- **OpenRouteService (HeiGIT)**:
  - Source: Heidelberg Institute for Geoinformation Technology (`https://api.openrouteservice.org`).
  - Terms: Subject to [HeiGIT Terms of Service](https://heigit.org/terms-of-service/).
  - License: Routing results licensed under CC-BY-SA 4.0.
  - Required Attribution: `"© openrouteservice by HeiGIT | Map data © OpenStreetMap contributors"`.
  - Privacy safeguards: Origin and destination coordinates are transmitted strictly for road directions calculation. The server never stores, logs, or tracks user GPS routes or histories.

- **OpenStreetMap & Tile Provider**:
  - Map Data: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, licensed under the Open Database License (ODbL).
  - Tile Server: OpenStreetMap standard tile layer (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`).

- **Common Alerting Protocol (CAP v1.2)**:
  - Standard: OASIS Open Standard XML format used for emergency alert schema normalization.

- **Humanitarian Data Exchange (HDX)**:
  - Source of reference spatial coordinates for disaster shelter locations and administrative boundaries.

---

## 3. Libraries & Dependencies

### Backend (Python 3.11+)
- **FastAPI** (`0.115.0+`): High-performance ASGI web framework for Python API routing.
- **Uvicorn** (`0.30.0+`): ASGI web server implementation.
- **Pydantic** (`2.8.0+`): Data parsing and schema validation using Python type annotations.
- **Shapely** (`2.0.0+`): Manipulation and analysis of geometric polygons and spatial containment queries.
- **H3** (`4.1.0+`): Uber's Hexagonal Hierarchical Spatial Indexing System (resolution 7 and 8).
- **HTTPX** (`0.27.0+`): Asynchronous HTTP client for upstream API requests.
- **Pytest** (`8.0.0+`): Unit and integration test runner.
- **defusedxml** (`0.7.1+`): Safe XML parsing protecting against entity expansion and XML injection.

### Frontend (React 19 & TypeScript)
- **React** (`19.0.0`): User interface declarative component library.
- **React DOM** (`19.0.0`): DOM rendering layer for React.
- **Leaflet** (`1.9.4`): Open-source interactive mobile-friendly spatial mapping library.
- **Vite** (`6.0.0+`): Frontend build tool and development server.
- **TypeScript** (`5.6.0+`): Typed JavaScript programming language.
- **Oxlint**: High-speed Rust-based linter for clean React code.

---

## 4. Replay Scenario & Data Integrity Disclosures

- **Historical Event Context**: The replay scenario is loosely based on Cyclone Michaung (December 2023, Chennai). It represents an **illustrative reconstruction** for demonstration and system evaluation only. It is not real-time or official government data.
- **Demo Shelters**: The 4 relief centers registered in `data/shelters.json` are fictional demo facilities created for hackathon testing.
- **Language Status**:
  - English (`en`), Tamil (`ta`), and Hindi (`hi`) safety instructions are curated from official civil defence phrases.
  - French (`fr`), German (`de`), and Japanese (`ja`) instructions are machine-translated and have not yet undergone native speaker crisis review. The user interface explicitly labels these as machine-translated with the original English text accessible.
- **No Offline PWA Claims**: While the tourist application is mobile-responsive and functions as a zero-install web application, full offline Service Worker caching is not yet deployed.
