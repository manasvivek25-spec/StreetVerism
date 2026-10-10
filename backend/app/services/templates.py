"""Multilingual template loading, startup validation, and parameter rendering.

Guarantees:
- en.json is loaded and validated for all mandatory emergency keys at startup.
- reviewed status comes ONLY from the template file (true for en/hi/ta, false for de/fr/ja).
- When reviewed is False, original_en carries the exact English fallback string.
- When reviewed is True, original_en is None.
- SHELTER_AT never emits a raw "{shelter}" placeholder: if no shelter resolves,
  the instruction is completely omitted.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.models.state import RenderedInstruction

logger = logging.getLogger("streetverism.services.templates")

SUPPORTED_LANGUAGES = ["en", "hi", "ta", "fr", "de", "ja"]

MANDATORY_KEYS = [
    "MOVE_TO_HIGHER_GROUND",
    "AVOID_FLOODED_ROADS",
    "DO_NOT_CROSS_WATER",
    "SHELTER_AT",
    "STAY_INDOORS",
    "STAY_AWAY_FROM_COAST",
    "KEEP_PHONE_CHARGED",
    "ALL_CLEAR",
    "EMERGENCY_NUMBER",
    "FOLLOW_OFFICIAL_ONLY",
    "CHECKIN_PROMPT",
    "UNVERIFIED_WARNING",
]

_TEMPLATES_CACHE: Dict[str, Dict[str, Any]] = {}


def load_and_validate_templates(template_dir: Path) -> None:
    """Load and validate all template JSON files, failing fast on missing files or keys."""
    global _TEMPLATES_CACHE
    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    en_path = template_dir / "en.json"
    if not en_path.exists():
        raise FileNotFoundError(f"Mandatory English template file missing: {en_path}")

    loaded: Dict[str, Dict[str, Any]] = {}
    for lang in SUPPORTED_LANGUAGES:
        lang_file = template_dir / f"{lang}.json"
        if not lang_file.exists():
            continue
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "templates" not in data:
                raise ValueError(f"Malformed template file {lang_file}: missing 'templates' object")
            loaded[lang] = data
        except Exception as e:
            raise RuntimeError(f"Failed to load template file {lang_file}: {e}") from e

    # Validate English file contains all mandatory emergency keys
    en_templates = loaded.get("en", {}).get("templates", {})
    missing_keys = [k for k in MANDATORY_KEYS if k not in en_templates]
    if missing_keys:
        raise ValueError(f"English template missing mandatory emergency keys: {missing_keys}")

    _TEMPLATES_CACHE = loaded
    logger.info("Loaded and validated templates for %d languages: %s", len(loaded), list(loaded.keys()))


def get_template_catalog(lang: str, template_dir: Optional[Path] = None) -> Tuple[Dict[str, Any], str]:
    """Retrieve raw template catalog for a language, falling back to English if missing.

    Returns (catalog_dict, served_lang).
    """
    global _TEMPLATES_CACHE
    if not _TEMPLATES_CACHE and template_dir is not None:
        load_and_validate_templates(template_dir)

    target_lang = lang if lang in _TEMPLATES_CACHE else "en"
    catalog = dict(_TEMPLATES_CACHE.get(target_lang, _TEMPLATES_CACHE.get("en", {})))
    # Ensure the served response declares what was actually served
    catalog["lang"] = target_lang
    return catalog, target_lang


def render_instruction(
    key: str,
    lang: str,
    params: Optional[Dict[str, Any]] = None,
    fallback_shelter_name: Optional[str] = None,
    shelter_map: Optional[Dict[str, str]] = None,
    template_dir: Optional[Path] = None,
) -> Optional[RenderedInstruction]:
    """Render a localized instruction with parameter interpolation.

    Returns None if the instruction cannot be rendered (e.g. SHELTER_AT without shelter).
    """
    global _TEMPLATES_CACHE
    if not _TEMPLATES_CACHE and template_dir is not None:
        load_and_validate_templates(template_dir)

    target_lang = lang if lang in _TEMPLATES_CACHE else "en"
    lang_data = _TEMPLATES_CACHE.get(target_lang, _TEMPLATES_CACHE.get("en", {}))
    en_data = _TEMPLATES_CACHE.get("en", {})

    tmpl_text = lang_data.get("templates", {}).get(key) or en_data.get("templates", {}).get(key)
    en_text = en_data.get("templates", {}).get(key, key)

    if not tmpl_text:
        return None

    # Handle SHELTER_AT parameter interpolation
    if key == "SHELTER_AT":
        resolved_shelter: Optional[str] = None
        param_shelter = (params or {}).get("shelter")
        if param_shelter:
            if shelter_map and param_shelter in shelter_map:
                resolved_shelter = shelter_map[param_shelter]
            else:
                resolved_shelter = str(param_shelter)
        elif fallback_shelter_name:
            resolved_shelter = fallback_shelter_name

        if not resolved_shelter:
            # Omit instruction entirely if no shelter could be resolved
            return None

        tmpl_text = tmpl_text.replace("{shelter}", resolved_shelter)
        en_text = en_text.replace("{shelter}", resolved_shelter)

    # Double check to NEVER emit a raw {shelter} placeholder
    if "{shelter}" in tmpl_text or "{shelter}" in en_text:
        return None

    is_reviewed = bool(lang_data.get("reviewed", False))
    original_en = en_text if not is_reviewed else None

    return RenderedInstruction(
        key=key,
        text=tmpl_text,
        reviewed=is_reviewed,
        original_en=original_en,
    )
