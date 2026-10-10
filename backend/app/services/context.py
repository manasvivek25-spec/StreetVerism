"""DataContext architecture encapsulating per-request temporal, alert, and weather state.

Ensures strict isolation between live mode (DB-backed, live clocks, NoWeatherProvider)
and replay mode (closed-world scenario timeline, ScenarioClock, in-memory overlay).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Literal, Optional

from backend.app.ingest.lifecycle import get_active_alerts
from backend.app.models import Alert, Report
from backend.app.repositories import AlertRepo, ReportRepo
from backend.app.scenario import ReplayOverlay, Scenario, ScenarioClock, scenario_inputs_at
from backend.app.trust.types import CellFeatures


@dataclass(frozen=True)
class DataContext:
    """Immutable per-request evaluation context passed to domain services."""
    now: datetime
    mode: Literal["live", "replay"]
    is_replay: bool
    alerts: List[Alert]
    reports_by_cell: Dict[str, List[Report]]
    features_provider: Callable[[str], CellFeatures]


class NoWeatherProvider:
    """Live mode placeholder provider until A4 live weather integration.

    In live mode:
    - rain_available is False everywhere.
    - flood_prone is False everywhere. Do NOT use data/flood_prone.geojson (it is illustrative).
    Consequence: crowd reports alone can reach only `unverified`, and `contradicted` only via
    an official all_clear.
    """

    def __call__(self, cell: str) -> CellFeatures:
        # TODO(A4): Replace with live Open-Meteo precipitation ingest and official flood-risk zones.
        return CellFeatures(
            rain_mm_3h=0.0,
            rain_mm_24h=0.0,
            flood_prone=False,
            rain_available=False,
        )


from backend.app.ingest.open_meteo import OpenMeteoRainProvider

_LIVE_WEATHER_PROVIDER = OpenMeteoRainProvider()


def get_live_weather_provider() -> OpenMeteoRainProvider:
    """Return the singleton Open-Meteo rain provider instance."""
    return _LIVE_WEATHER_PROVIDER


def build_data_context(
    mode: Literal["live", "replay"],
    scenario_clock: Optional[ScenarioClock],
    scenario: Optional[Scenario],
    overlay: Optional[ReplayOverlay],
    alert_repo: AlertRepo,
    report_repo: ReportRepo,
    injected_now: Optional[datetime] = None,
    features_provider: Optional[Callable[[str], CellFeatures]] = None,
) -> DataContext:
    """Build an immutable DataContext tailored to the current operating mode."""
    if mode == "replay":
        if scenario_clock is None or scenario is None:
            raise RuntimeError("Replay mode requested but scenario or clock is uninitialized")
        sim_dt = injected_now if injected_now is not None else scenario_clock.sim_time()
        # Derive scenario inputs at simulated timestamp (closed world: DB reports ignored)
        inputs = scenario_inputs_at(scenario, sim_dt, overlay)
        reports_map: Dict[str, List[Report]] = defaultdict(list)
        for r in inputs.reports:
            reports_map[r.cell].append(r)

        return DataContext(
            now=sim_dt,
            mode="replay",
            is_replay=True,
            alerts=inputs.alerts,
            reports_by_cell=dict(reports_map),
            features_provider=features_provider or (lambda c: inputs.features_for_cell(c)),
        )

    # Live Mode
    eval_now = injected_now if injected_now is not None else datetime.now(timezone.utc)
    if eval_now.tzinfo is None:
        eval_now = eval_now.replace(tzinfo=timezone.utc)
    now_iso = eval_now.isoformat()

    # Active official alerts from database
    all_db_alerts = alert_repo.list_all()
    active_alerts = get_active_alerts(all_db_alerts, now_iso)

    # Crowd reports in the last 24 hours
    cutoff_dt = eval_now - timedelta(hours=24)
    cutoff_iso = cutoff_dt.isoformat()
    recent_db_reports = report_repo.list_all_since(cutoff_iso)

    live_reports_map: Dict[str, List[Report]] = defaultdict(list)
    for row in recent_db_reports:
        # Convert DB dict row to Report domain model
        try:
            r_obj = Report(
                id=row["id"],
                device_id=row["device_id"],
                lat=row["lat"],
                lng=row["lng"],
                cell=row["cell"],
                claim=row["claim"],
                text=row.get("text"),
                created_at=row["created_at"],
            )
            live_reports_map[r_obj.cell].append(r_obj)
        except Exception:
            continue

    provider = features_provider or _LIVE_WEATHER_PROVIDER

    return DataContext(
        now=eval_now,
        mode="live",
        is_replay=False,
        alerts=active_alerts,
        reports_by_cell=dict(live_reports_map),
        features_provider=provider,
    )

