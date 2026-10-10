"""Service layer providing domain logic, data contexts, and storage abstractions."""

from backend.app.services.alert_service import (
    create_official_alert,
    expire_official_alert,
    list_official_alerts,
)
from backend.app.services.cells_service import (
    MAX_BBOX_CELLS,
    MAX_BBOX_DELTA,
    clear_cells_cache,
    get_cells_for_bbox,
    parse_bbox_string,
)
from backend.app.services.checkin_service import (
    handle_checkin,
    list_checkins,
    purge_expired,
    submit_checkin,
)
from backend.app.services.context import DataContext, NoWeatherProvider, build_data_context
from backend.app.services.report_service import submit_crowd_report
from backend.app.services.shelters import (
    get_all_shelters,
    get_nearest_shelters,
    seed_shelters_from_file,
)
from backend.app.services.state_service import get_state
from backend.app.services.templates import (
    SUPPORTED_LANGUAGES,
    get_template_catalog,
    load_and_validate_templates,
    render_instruction,
)

__all__ = [
    "DataContext",
    "NoWeatherProvider",
    "build_data_context",
    "seed_shelters_from_file",
    "get_all_shelters",
    "get_nearest_shelters",
    "load_and_validate_templates",
    "get_template_catalog",
    "render_instruction",
    "SUPPORTED_LANGUAGES",
    "get_state",
    "MAX_BBOX_DELTA",
    "MAX_BBOX_CELLS",
    "clear_cells_cache",
    "get_cells_for_bbox",
    "parse_bbox_string",
    "submit_crowd_report",
    "submit_checkin",
    "list_checkins",
    "handle_checkin",
    "purge_expired",
    "create_official_alert",
    "list_official_alerts",
    "expire_official_alert",
]
