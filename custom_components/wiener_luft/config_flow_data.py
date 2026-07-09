"""Flow data loading helpers for config flows."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Protocol, cast

from homeassistant.core import HomeAssistant

from .exceptions import FlowFetchError
from .fetch import async_fetch_measurements, async_fetch_stations
from .measurements import MEASUREMENT_SPECS
from .models import IntegrationData


class _ConfigWithLanguage(Protocol):
    """Subset of Home Assistant config used by this module."""

    language: str | None


def _translation_mapping(value: object) -> dict[str, object] | None:
    """Return a translation JSON object when the value has the expected shape."""

    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return None


def _translation_names(section: dict[str, object]) -> dict[str, str]:
    """Return sensor translation names from one validated translation section."""

    names: dict[str, str] = {}
    for translation_key, values in section.items():
        translation = _translation_mapping(values)
        if translation is None:
            continue
        name = translation.get("name")
        if isinstance(name, str):
            names[translation_key] = name
    return names


def _required_translation_section(
    parent: dict[str, object],
    key: str,
) -> dict[str, object]:
    """Return one required translation section or fail for invalid bundled data."""

    section = _translation_mapping(parent.get(key))
    if section is None:
        raise ValueError(f"Invalid translation file structure: missing {key!r}")
    return section


async def async_fetch_flow_data(
    hass: HomeAssistant,
) -> tuple[IntegrationData | None, str | None, dict[str, str] | None]:
    """Fetch stations and measurements for the current flow."""

    try:
        stations = await async_fetch_stations(hass)
    except FlowFetchError as err:
        return None, f"stations_{err.reason}", err.placeholders

    try:
        measurements = await async_fetch_measurements(hass)
    except FlowFetchError as err:
        return None, f"measurements_{err.reason}", err.placeholders

    return IntegrationData(stations=stations, measurements=measurements), None, None


async def async_get_measurement_names(hass: HomeAssistant) -> dict[str, str]:
    """Return localized measurement names from integration translations."""

    config = cast(_ConfigWithLanguage, hass.config)
    language = config.language or "en"
    names = cast(
        dict[str, str],
        await hass.async_add_executor_job(_load_measurement_names_from_file, language),
    )
    if language != "en":
        fallback = cast(
            dict[str, str],
            await hass.async_add_executor_job(_load_measurement_names_from_file, "en"),
        )
        names = fallback | names
    return {
        component: names.get(spec.translation_key, spec.translation_key)
        for component, spec in MEASUREMENT_SPECS.items()
    }


@cache
def _load_measurement_names_from_file(language: str) -> dict[str, str]:
    """Load translated sensor names for one language file."""

    path = Path(__file__).with_name("translations") / f"{language}.json"
    if not path.exists():
        return {}

    content = _translation_mapping(
        cast(object, json.loads(path.read_text(encoding="utf-8")))
    )
    if content is None:
        return {}

    entity_section = _required_translation_section(content, "entity")
    sensor_section = _required_translation_section(entity_section, "sensor")
    return _translation_names(sensor_section)
