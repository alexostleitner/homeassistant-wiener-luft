"""Flow data loading helpers for config flows."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from homeassistant.core import HomeAssistant

from .coordinator import (
    FlowFetchError,
    IntegrationData,
    async_fetch_measurements,
    async_fetch_stations,
)
from .measurements import MEASUREMENT_SPECS


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

    language = hass.config.language or "en"
    names = await hass.async_add_executor_job(
        _load_measurement_names_from_file, language
    )
    if language != "en":
        fallback = await hass.async_add_executor_job(
            _load_measurement_names_from_file, "en"
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

    content = json.loads(path.read_text(encoding="utf-8"))
    return {
        translation_key: values["name"]
        for translation_key, values in content["entity"]["sensor"].items()
    }
