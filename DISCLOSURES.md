# Disclosures & Attribution

This document tracks all third-party libraries, APIs, external data sources, and AI coding assistants utilized in **StreetVerism** during the hackathon development window.

## AI Coding Tools
- **Google DeepMind Antigravity**: AI pair programming assistant used for architecture, backend scaffolding, mock data modeling, and test suites.

## Backend Libraries (Python 3.11+)
- **FastAPI**: Modern, high-performance web framework for building APIs with Python 3.11+ and standard type hints.
- **Uvicorn**: ASGI web server implementation for Python.
- **Pydantic (v2)**: Data validation and settings management using Python type annotations.
- **Shapely**: Manipulation and analysis of planar geometric objects.
- **H3 (v4)**: Uber's Hexagonal Hierarchical Spatial Indexing System.
- **HTTPX**: Fully featured HTTP client for Python 3 with async support.
- **Pytest**: Python testing framework.
- **defusedxml**: XML package providing safe parsing and protection against XML vulnerabilities (XXE, entity expansion / billion laughs attacks).

## External APIs & Data Sources (Planned & Ingested)
- **Open-Meteo**: Free weather API for precipitation, rainfall rates, and historical data.
- **Common Alerting Protocol (CAP v1.2)**: Public open standard (OASIS) used for alert ingestion parser and schema normalization.
- **OpenRouteService (HeiGIT)**: Open-source routing service provided by Heidelberg Institute for Geoinformation Technology. Subject to [HeiGIT Terms of Service](https://heigit.org/terms-of-service/). Routing results licensed under CC-BY-SA 4.0.
- **OpenStreetMap**: Map data © OpenStreetMap contributors under the Open Database License (ODbL).
- **Humanitarian Data Exchange (HDX)**: Reference shelter and boundary geo-coordinates.

## Routing Privacy & Data Flow
- **Third-Party Data Flow**: Origin and destination coordinates are sent to OpenRouteService (HeiGIT) solely when a road route is requested by a client.
- **Zero GPS Tracking**: The StreetVerism server never stores, logs, or streams user GPS track histories.
- **Device ID Protection**: `device_id` is used solely by an ephemeral in-memory rate limiter and is never persisted alongside routes or exposed in public query responses.

## Replay Scenario & Geographic Reconstruction
- **Cyclone Michaung (Dec 2023, Chennai)**: Qualitative background and timeline only (heavy rain ramping over 24 sim-hours, low-lying southern/southwestern basins worst affected, official alerts issued in phases).
- **Hand-Authored Scenario Data (`data/scenarios/michaung_replay.json`)**: Approximate, illustrative synthetic timeline, rainfall keyframes, and crowd reports constructed strictly for demonstration and testing purposes. All values and device IDs are synthetic and approximate.
- **Hand-Drawn Approximate Flood-Prone Polygons (`data/flood_prone.geojson`)**: Hand-drawn polygon approximations representing historically vulnerable drainage basins in Chennai (Velachery/Pallikaranai and Adyar riparian corridor) for illustrative demonstration only; not an official flood risk map.
