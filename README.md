# StreetVerism

> **Real-Time Crisis Communication & Verified Action Layer for Foreign Tourists During Extreme Weather**
> Built for the 24-hour Hackathon (Track: TravelTech) at IIITDM Kancheepuram.

---

## 1. Problem Statement
During localized extreme weather events (e.g., flash floods, severe cyclones), foreign tourists face severe vulnerabilities: unfamiliar local geography, language barriers, fragmented emergency alerts, and misleading social media rumors. This causes panic, dangerous wandering into high-risk zones, and overburdens search-and-rescue teams.

## 2. Our Solution
**StreetVerism** is a two-sided crisis intelligence and triage platform:
1. **Probabilistic Trust Engine**: Ingests weather data (Open-Meteo), official hazard polygons, and crowd observations, fusing them via Bayesian log-odds per H3 resolution-8 cell into five verified states (`official_hazard`, `likely_hazard`, `unverified`, `contradicted`, `clear`).
2. **Tourist Zero-Install PWA**: Accessible via QR code at transit hubs/hotels with offline caching, vetted multilingual template instructions (`en`, `hi`, `ta`, `fr`, `de`, `ja`), nearest emergency shelters, and single-tap safety/help check-ins.
3. **Authority Console**: Allows disaster management authorities to publish verified alerts once (fanning out across all languages) and triage tourist check-in clusters.

---

## 3. Repository Structure
```
StreetVerism/
├── backend/                  # FastAPI backend, SQLite, Trust Engine, Scenario Replay
│   ├── app/
│   │   ├── api/              # API router endpoints
│   │   ├── geo/              # H3 spatial indexing & geometry utils
│   │   ├── models/           # Pydantic v2 schemas & domain models
│   │   ├── mock_data/        # Deterministic mock datasets (MOCK=1)
│   │   ├── scenario/         # Scenario clock & replay controllers
│   │   └── trust/            # Bayesian log-odds trust engine
│   └── tests/                # Pytest test suite
├── data/                     # Offline templates, shelters, scenarios
│   ├── shelters.json
│   ├── templates/            # Vetted language templates ({lang}.json)
│   └── scenarios/            # Michaung replay dataset
├── docs/                     # API.md, openapi.json, DEMO.md
├── web/                      # React + TypeScript Vite PWA (Tourist + Authority)
├── CONTEXT.md                # System specification & contract source of truth
└── DISCLOSURES.md            # Open-source libraries, APIs, and AI disclosure
```

---

## 4. Backend Quickstart

### Prerequisites
- Python 3.11+
- Virtual environment (`venv`)

### Setup & Run
```bash
# 1. Create and activate virtual environment
py -3.11 -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Start development server in MOCK mode
# Windows PowerShell:
$env:MOCK="1"; uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
# Bash:
MOCK=1 uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 5. API Documentation
- Interactive Swagger UI: `http://localhost:8000/docs`
- Redoc UI: `http://localhost:8000/redoc`
- OpenAPI Specification: [`docs/openapi.json`](file:///c:/Users/len/StreetVerism/docs/openapi.json)
- Contract Reference: [`docs/API.md`](file:///c:/Users/len/StreetVerism/docs/API.md)
