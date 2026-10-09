"""Repository layer abstracting data access from database engines.

Ensures routes never import sqlite3 directly and provides in-memory fakes for tests.
Coordinates are strictly rounded to 4 decimals for location privacy.
Timestamps are normalized to fixed UTC ISO-8601 strings.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.app.db import get_db_connection, to_utc_iso
from backend.app.models import (
    Alert,
    CheckinCreate,
    CheckinItem,
    ReportCreate,
    Shelter,
)


class AlertRepo(ABC):
    @abstractmethod
    def add(self, alert: Alert) -> Alert: ...

    @abstractmethod
    def get(self, alert_id: str) -> Optional[Alert]: ...

    @abstractmethod
    def list_all(self) -> List[Alert]: ...

    @abstractmethod
    def expire(self, alert_id: str, now_iso: str) -> bool: ...


class ReportRepo(ABC):
    @abstractmethod
    def add(self, report: ReportCreate, cell: str, created_at: Optional[str] = None) -> Dict[str, Any]: ...

    @abstractmethod
    def list_by_cell(self, cell: str) -> List[Dict[str, Any]]: ...


class CheckinRepo(ABC):
    @abstractmethod
    def add(self, checkin: CheckinCreate, cell7: str, recorded_at: Optional[str] = None) -> CheckinItem: ...

    @abstractmethod
    def get(self, checkin_id: str) -> Optional[CheckinItem]: ...

    @abstractmethod
    def list_all(self) -> List[CheckinItem]: ...

    @abstractmethod
    def set_handled(self, checkin_id: str, handled: bool) -> Optional[CheckinItem]: ...


class ShelterRepo(ABC):
    @abstractmethod
    def add(self, shelter: Shelter) -> Shelter: ...

    @abstractmethod
    def get(self, shelter_id: str) -> Optional[Shelter]: ...

    @abstractmethod
    def list_all(self) -> List[Shelter]: ...


# --- SQLite Implementations ---

class SqliteAlertRepo(AlertRepo):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add(self, alert: Alert) -> Alert:
        # Normalize timestamps on write
        sent_iso = to_utc_iso(alert.sent_at)
        exp_iso = to_utc_iso(alert.expires_at)
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alerts (
                    id, source, sender, hazard, severity, urgency, certainty,
                    area_json, instruction_keys_json, params_json,
                    sent_at, expires_at, supersedes, published_by, is_replay
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.id,
                    alert.source,
                    alert.sender,
                    alert.hazard,
                    alert.severity,
                    alert.urgency,
                    alert.certainty,
                    json.dumps(alert.area.model_dump()),
                    json.dumps(alert.instruction_keys),
                    json.dumps(alert.params),
                    sent_iso,
                    exp_iso,
                    alert.supersedes,
                    alert.published_by,
                    1 if alert.is_replay else 0,
                ),
            )
        alert_copy = alert.model_copy()
        alert_copy.sent_at = sent_iso
        alert_copy.expires_at = exp_iso
        return alert_copy

    def get(self, alert_id: str) -> Optional[Alert]:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if not row:
                return None
            return Alert(
                id=row["id"],
                source=row["source"],
                sender=row["sender"],
                hazard=row["hazard"],
                severity=row["severity"],
                urgency=row["urgency"],
                certainty=row["certainty"],
                area=json.loads(row["area_json"]),
                instruction_keys=json.loads(row["instruction_keys_json"]),
                params=json.loads(row["params_json"]),
                sent_at=row["sent_at"],
                expires_at=row["expires_at"],
                supersedes=row["supersedes"],
                published_by=row["published_by"],
                is_replay=bool(row["is_replay"]),
            )

    def list_all(self) -> List[Alert]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM alerts ORDER BY sent_at DESC").fetchall()
            alerts = []
            for row in rows:
                alerts.append(
                    Alert(
                        id=row["id"],
                        source=row["source"],
                        sender=row["sender"],
                        hazard=row["hazard"],
                        severity=row["severity"],
                        urgency=row["urgency"],
                        certainty=row["certainty"],
                        area=json.loads(row["area_json"]),
                        instruction_keys=json.loads(row["instruction_keys_json"]),
                        params=json.loads(row["params_json"]),
                        sent_at=row["sent_at"],
                        expires_at=row["expires_at"],
                        supersedes=row["supersedes"],
                        published_by=row["published_by"],
                        is_replay=bool(row["is_replay"]),
                    )
                )
            return alerts

    def expire(self, alert_id: str, now_iso: str) -> bool:
        normalized_now = to_utc_iso(now_iso)
        with get_db_connection(self.db_path) as conn:
            res = conn.execute(
                "UPDATE alerts SET expires_at = ? WHERE id = ?",
                (normalized_now, alert_id),
            )
            return res.rowcount > 0


class SqliteReportRepo(ReportRepo):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add(self, report: ReportCreate, cell: str, created_at: Optional[str] = None) -> Dict[str, Any]:
        rep_id = f"rep_{uuid4().hex[:8]}"
        created_iso = to_utc_iso(created_at or datetime.now(timezone.utc))
        lat_rounded = round(report.lat, 4)
        lng_rounded = round(report.lng, 4)
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reports (id, device_id, lat, lng, cell, claim, text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rep_id, report.device_id, lat_rounded, lng_rounded, cell, report.claim, report.text, created_iso),
            )
        return {
            "id": rep_id,
            "device_id": report.device_id,
            "lat": lat_rounded,
            "lng": lng_rounded,
            "cell": cell,
            "claim": report.claim,
            "text": report.text,
            "created_at": created_iso,
        }

    def list_by_cell(self, cell: str) -> List[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM reports WHERE cell = ? ORDER BY created_at DESC", (cell,)
            ).fetchall()
            return [dict(r) for r in rows]


class SqliteCheckinRepo(CheckinRepo):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add(self, checkin: CheckinCreate, cell7: str, recorded_at: Optional[str] = None) -> CheckinItem:
        chk_id = f"chk_{uuid4().hex[:8]}"
        recorded_iso = to_utc_iso(recorded_at or datetime.now(timezone.utc))
        lat_rounded = round(checkin.lat, 4)
        lng_rounded = round(checkin.lng, 4)
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO checkins (id, device_id, lat, lng, state, language, group_size, note, cell7, handled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chk_id,
                    checkin.device_id,
                    lat_rounded,
                    lng_rounded,
                    checkin.state,
                    checkin.language,
                    checkin.group_size,
                    checkin.note,
                    cell7,
                    0,
                    recorded_iso,
                ),
            )
        return CheckinItem(
            id=chk_id,
            device_id=checkin.device_id,
            lat=lat_rounded,
            lng=lng_rounded,
            state=checkin.state,
            language=checkin.language,
            group_size=checkin.group_size,
            note=checkin.note,
            cell7=cell7,
            handled=False,
            recorded_at=recorded_iso,
        )

    def get(self, checkin_id: str) -> Optional[CheckinItem]:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM checkins WHERE id = ?", (checkin_id,)).fetchone()
            if not row:
                return None
            return CheckinItem(
                id=row["id"],
                device_id=row["device_id"],
                lat=row["lat"],
                lng=row["lng"],
                state=row["state"],
                language=row["language"],
                group_size=row["group_size"],
                note=row["note"],
                cell7=row["cell7"],
                handled=bool(row["handled"]),
                recorded_at=row["created_at"],
            )

    def list_all(self) -> List[CheckinItem]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM checkins ORDER BY created_at DESC").fetchall()
            return [
                CheckinItem(
                    id=r["id"],
                    device_id=r["device_id"],
                    lat=r["lat"],
                    lng=r["lng"],
                    state=r["state"],
                    language=r["language"],
                    group_size=r["group_size"],
                    note=r["note"],
                    cell7=r["cell7"],
                    handled=bool(r["handled"]),
                    recorded_at=r["created_at"],
                )
                for r in rows
            ]

    def set_handled(self, checkin_id: str, handled: bool) -> Optional[CheckinItem]:
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE checkins SET handled = ? WHERE id = ?",
                (1 if handled else 0, checkin_id),
            )
        return self.get(checkin_id)


class SqliteShelterRepo(ShelterRepo):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add(self, shelter: Shelter) -> Shelter:
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO shelters (id, name, name_local, lat, lng, open, is_demo, capacity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shelter.id,
                    shelter.name,
                    shelter.name_local,
                    shelter.lat,
                    shelter.lng,
                    1 if shelter.open else 0,
                    1 if shelter.is_demo else 0,
                    shelter.capacity,
                ),
            )
        return shelter

    def get(self, shelter_id: str) -> Optional[Shelter]:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
            if not row:
                return None
            return Shelter(
                id=row["id"],
                name=row["name"],
                name_local=row["name_local"],
                lat=row["lat"],
                lng=row["lng"],
                open=bool(row["open"]),
                is_demo=bool(row["is_demo"]),
                capacity=row["capacity"],
            )

    def list_all(self) -> List[Shelter]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM shelters ORDER BY id ASC").fetchall()
            return [
                Shelter(
                    id=r["id"],
                    name=r["name"],
                    name_local=r["name_local"],
                    lat=r["lat"],
                    lng=r["lng"],
                    open=bool(r["open"]),
                    is_demo=bool(r["is_demo"]),
                    capacity=r["capacity"],
                )
                for r in rows
            ]


# --- In-Memory Fakes (For Unit Tests & Mock Mode) ---

class InMemoryAlertRepo(AlertRepo):
    def __init__(self, initial_alerts: Optional[List[Alert]] = None):
        self._alerts: Dict[str, Alert] = {a.id: a for a in (initial_alerts or [])}

    def add(self, alert: Alert) -> Alert:
        alert_copy = alert.model_copy()
        alert_copy.sent_at = to_utc_iso(alert.sent_at)
        alert_copy.expires_at = to_utc_iso(alert.expires_at)
        self._alerts[alert_copy.id] = alert_copy
        return alert_copy

    def get(self, alert_id: str) -> Optional[Alert]:
        return self._alerts.get(alert_id)

    def list_all(self) -> List[Alert]:
        return sorted(self._alerts.values(), key=lambda a: a.sent_at, reverse=True)

    def expire(self, alert_id: str, now_iso: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id].expires_at = to_utc_iso(now_iso)
            return True
        return False


class InMemoryReportRepo(ReportRepo):
    def __init__(self):
        self._reports: List[Dict[str, Any]] = []

    def add(self, report: ReportCreate, cell: str, created_at: Optional[str] = None) -> Dict[str, Any]:
        item = {
            "id": f"rep_{uuid4().hex[:8]}",
            "device_id": report.device_id,
            "lat": round(report.lat, 4),
            "lng": round(report.lng, 4),
            "cell": cell,
            "claim": report.claim,
            "text": report.text,
            "created_at": to_utc_iso(created_at or datetime.now(timezone.utc)),
        }
        self._reports.append(item)
        return item

    def list_by_cell(self, cell: str) -> List[Dict[str, Any]]:
        return [r for r in self._reports if r["cell"] == cell]


class InMemoryCheckinRepo(CheckinRepo):
    def __init__(self, initial_items: Optional[List[CheckinItem]] = None):
        self._items: Dict[str, CheckinItem] = {item.id: item for item in (initial_items or [])}

    def add(self, checkin: CheckinCreate, cell7: str, recorded_at: Optional[str] = None) -> CheckinItem:
        chk_id = f"chk_{uuid4().hex[:8]}"
        rec_iso = to_utc_iso(recorded_at or datetime.now(timezone.utc))
        item = CheckinItem(
            id=chk_id,
            device_id=checkin.device_id,
            lat=round(checkin.lat, 4),
            lng=round(checkin.lng, 4),
            state=checkin.state,
            language=checkin.language,
            group_size=checkin.group_size,
            note=checkin.note,
            cell7=cell7,
            handled=False,
            recorded_at=rec_iso,
        )
        self._items[chk_id] = item
        return item

    def get(self, checkin_id: str) -> Optional[CheckinItem]:
        return self._items.get(checkin_id)

    def list_all(self) -> List[CheckinItem]:
        return list(self._items.values())

    def set_handled(self, checkin_id: str, handled: bool) -> Optional[CheckinItem]:
        if checkin_id in self._items:
            item = self._items[checkin_id].model_copy()
            item.handled = handled
            self._items[checkin_id] = item
            return item
        return None


class InMemoryShelterRepo(ShelterRepo):
    def __init__(self, initial_shelters: Optional[List[Shelter]] = None):
        self._shelters: Dict[str, Shelter] = {s.id: s for s in (initial_shelters or [])}

    def add(self, shelter: Shelter) -> Shelter:
        self._shelters[shelter.id] = shelter
        return shelter

    def get(self, shelter_id: str) -> Optional[Shelter]:
        return self._shelters.get(shelter_id)

    def list_all(self) -> List[Shelter]:
        return list(self._shelters.values())
