"""Shelter registration, database seeding, and spatial nearest-shelter ranking."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from backend.app.geo import haversine_distance_m
from backend.app.models import Shelter
from backend.app.repositories import ShelterRepo

logger = logging.getLogger("streetverism.services.shelters")


def seed_shelters_from_file(shelters_path: Path, repo: ShelterRepo) -> int:
    """Idempotently seed shelters from data/shelters.json into the database."""
    if not shelters_path.exists():
        raise FileNotFoundError(f"Shelters catalog file not found: {shelters_path}")

    with open(shelters_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("shelters.json must contain a JSON array of shelter records")

    count = 0
    for item in data:
        shelter = Shelter(
            id=item["id"],
            name=item["name"],
            name_local=item.get("name_local") or item["name"],
            lat=item["lat"],
            lng=item["lng"],
            open=item.get("open", True),
            is_demo=item.get("is_demo", True),
            capacity=item.get("capacity"),
        )
        repo.add(shelter)
        count += 1

    logger.info("Successfully seeded %d shelters into database from %s", count, shelters_path)
    return count


def get_all_shelters(repo: ShelterRepo) -> Tuple[List[Shelter], int]:
    """Retrieve all registered emergency shelters and total count."""
    shelters = repo.list_all()
    return shelters, len(shelters)


def get_nearest_shelters(
    lat: float,
    lng: float,
    repo: ShelterRepo,
    limit: int = 3,
) -> List[Shelter]:
    """Find closest shelters ranked by open status first, then haversine distance.

    Returns up to `limit` shelters with distance_m and is_demo preserved.
    """
    all_shelters = repo.list_all()
    if not all_shelters:
        return []

    shelters_with_dist: List[Shelter] = []
    for s in all_shelters:
        dist_m = haversine_distance_m(lat, lng, s.lat, s.lng)
        s_copy = s.model_copy()
        s_copy.distance_m = round(dist_m, 1)
        shelters_with_dist.append(s_copy)

    # Sort rule: open first (open=True before open=False), then by distance ascending
    shelters_with_dist.sort(key=lambda s: (0 if s.open else 1, s.distance_m or float("inf")))
    return shelters_with_dist[:limit]
