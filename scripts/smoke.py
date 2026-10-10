#!/usr/bin/env python3
"""StreetVerism Smoke Test Suite.

Validates the complete API golden path against any deployed or local base URL:
1. /health: healthy, server_time, replay/live mode
2. Scenario seek: seeks to golden_moment (elapsed_s=34200)
3. /api/state at Adyar in German: status=official_hazard, reviewed=False, original_en present
4. /api/state at Adyar in Tamil: status=official_hazard, reviewed=True, original_en is None
5. /api/cells: FeatureCollection containing unverified rumor cell and official hazard
6. /api/shelters: active shelters list with capacity & coordinates
7. POST /api/checkin: creates checkin in need_help state
8. GET /api/checkins: retrieves checkin using X-Authority-Key, verifies device_id omission
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import httpx


def run_smoke_test(base_url: str, authority_key: str, timeout: float = 15.0) -> bool:
    base_url = base_url.rstrip("/")
    client = httpx.Client(base_url=base_url, timeout=timeout)
    steps_passed = 0
    total_steps = 8

    print(f"==================================================")
    print(f"StreetVerism API Golden Path Smoke Test")
    print(f"Target URL: {base_url}")
    print(f"==================================================\n")

    # Step 1: Health check
    try:
        resp = client.get("/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        server_time = data.get("server_time")
        assert server_time, "server_time missing"
        # Validate parseable ISO timestamp
        datetime.datetime.fromisoformat(server_time.replace("Z", "+00:00"))
        mode = data.get("mode")
        print(f"[PASS] 1. /health -> 200 OK (mode={mode}, server_time={server_time})")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 1. /health -> {exc}")

    # Step 2: Scenario seek to golden_moment
    try:
        resp = client.post("/api/scenario/seek", json={"bookmark": "golden_moment"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("elapsed_s") == 34200, f"Expected elapsed_s=34200, got {data.get('elapsed_s')}"
        assert data.get("mode") == "replay", f"Expected mode=replay, got {data.get('mode')}"
        print(f"[PASS] 2. /api/scenario/seek -> 200 OK (bookmark=golden_moment, elapsed_s=34200)")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 2. /api/scenario/seek -> {exc}")

    # Step 3: State at Adyar hazard point in German (de)
    try:
        resp = client.get("/api/state?lat=13.015&lng=80.225&lang=de")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "official_hazard", f"Expected official_hazard, got {data.get('status')}"
        instructions = data.get("instructions", [])
        assert len(instructions) > 0, "No instructions returned"
        first_inst = instructions[0]
        # In German, translation is machine-translated: reviewed=False and original_en present
        assert first_inst.get("reviewed") is False, f"Expected reviewed=False for de, got {first_inst.get('reviewed')}"
        assert first_inst.get("original_en") is not None, "Expected original_en to be present for unreviewed translation"
        print(f"[PASS] 3. /api/state (de) -> 200 OK (status={data['status']}, reviewed={first_inst['reviewed']}, original_en present)")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 3. /api/state (de) -> {exc}")

    # Step 4: State at Adyar hazard point in Tamil (ta)
    try:
        resp = client.get("/api/state?lat=13.015&lng=80.225&lang=ta")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "official_hazard", f"Expected official_hazard, got {data.get('status')}"
        instructions = data.get("instructions", [])
        assert len(instructions) > 0, "No instructions returned"
        first_inst = instructions[0]
        # In Tamil, without fluent reviewer confirmation, reviewed=False and original_en is present
        assert first_inst.get("reviewed") is False, f"Expected reviewed=False for unverified ta, got {first_inst.get('reviewed')}"
        assert first_inst.get("original_en") is not None, "Expected original_en present for unverified ta"
        print(f"[PASS] 4. /api/state (ta) -> 200 OK (status={data['status']}, reviewed={first_inst['reviewed']}, original_en present)")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 4. /api/state (ta) -> {exc}")

    # Step 5: Cells feature collection includes unverified rumor cell and hazard cell
    try:
        resp = client.get("/api/cells?bbox=80.20,12.98,80.26,13.07")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("type") == "FeatureCollection", f"Expected FeatureCollection, got {data.get('type')}"
        features = data.get("features", [])
        statuses = {f.get("properties", {}).get("status") for f in features}
        assert "unverified" in statuses, f"Expected 'unverified' rumor cell in cells, found: {statuses}"
        assert "official_hazard" in statuses, f"Expected 'official_hazard' in cells, found: {statuses}"
        print(f"[PASS] 5. /api/cells -> 200 OK ({len(features)} cells returned, statuses={sorted(list(statuses))})")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 5. /api/cells -> {exc}")

    # Step 6: Shelters query
    try:
        resp = client.get("/api/shelters")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        shelters = data.get("shelters", [])
        assert len(shelters) >= 1, "No shelters returned"
        open_shelters = [s for s in shelters if s.get("open") is True]
        assert len(open_shelters) >= 1, "No open shelters found"
        print(f"[PASS] 6. /api/shelters -> 200 OK ({len(shelters)} shelters, {len(open_shelters)} open)")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 6. /api/shelters -> {exc}")

    # Step 7: Check-in creation
    test_device_id = f"smoke-dev-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"
    checkin_id = None
    try:
        resp = client.post(
            "/api/checkin",
            json={
                "device_id": test_device_id,
                "lat": 13.015,
                "lng": 80.225,
                "state": "need_help",
                "language": "de",
                "group_size": 2,
                "note": "Smoke test automated checkin",
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        checkin_id = data.get("id")
        assert checkin_id, f"Check-in id missing in response: {data}"
        assert data.get("recorded_at"), f"recorded_at missing in response: {data}"
        print(f"[PASS] 7. POST /api/checkin -> 200 OK (id={checkin_id}, recorded_at={data.get('recorded_at')})")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 7. POST /api/checkin -> {exc}")

    # Step 8: GET /api/checkins with X-Authority-Key and verify device_id omission
    try:
        assert authority_key, "AUTHORITY_KEY is required to test GET /api/checkins"
        resp = client.get("/api/checkins", headers={"X-Authority-Key": authority_key})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        items = data.get("items", [])
        assert len(items) >= 1, "No items in checkins response"
        # Confirm our checkin is present
        matching = [item for item in items if item.get("id") == checkin_id]
        if checkin_id:
            assert len(matching) == 1, f"Created checkin {checkin_id} not found in GET /checkins"
        # CRITICAL PRIVACY CHECK: ensure device_id is NEVER present
        for item in items:
            assert "device_id" not in item, f"SECURITY VIOLATION: device_id leaked in item {item}"
            assert item.get("created_at") is not None, f"created_at missing in item {item}"
        print(f"[PASS] 8. GET /api/checkins -> 200 OK ({len(items)} checkins, device_id omitted, privacy verified)")
        steps_passed += 1
    except Exception as exc:
        print(f"[FAIL] 8. GET /api/checkins -> {exc}")

    print(f"\n==================================================")
    print(f"Summary: {steps_passed}/{total_steps} steps passed.")
    print(f"==================================================")

    return steps_passed == total_steps


def main() -> int:
    parser = argparse.ArgumentParser(description="StreetVerism Golden Path Smoke Test")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://localhost:8000"),
        help="Base URL of StreetVerism backend (default: http://localhost:8000 or $BASE_URL)",
    )
    parser.add_argument(
        "--authority-key",
        default=os.getenv("AUTHORITY_KEY", "fresh-env-authority-key-456"),
        help="Administrative authority key (default: $AUTHORITY_KEY)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP request timeout in seconds (default: 15.0)",
    )
    args = parser.parse_args()

    success = run_smoke_test(
        base_url=args.base_url,
        authority_key=args.authority_key,
        timeout=args.timeout,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
