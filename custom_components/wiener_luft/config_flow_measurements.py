"""Measurement selection helpers for config flows."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_MEASUREMENTS
from .coordinator import IntegrationData
from .measurements import MEASUREMENT_SPECS


def _count_available_measurements(
    integration_data: IntegrationData,
    selected_station_codes: list[str],
) -> dict[str, int]:
    """Count current measurement availability for the selected stations."""

    counts = {component: 0 for component in MEASUREMENT_SPECS}
    for station_code in selected_station_codes:
        for component in MEASUREMENT_SPECS:
            reading = integration_data.measurements.get((station_code, component))
            if reading is None or reading.measurement_type is None:
                continue
            counts[component] += 1
    return counts


def measurement_defaults(
    integration_data: IntegrationData,
    selected_station_codes: list[str],
    selected_measurement_codes: list[str] | None = None,
) -> list[str]:
    """Return measurement defaults, using saved selections when available."""

    counts = _count_available_measurements(integration_data, selected_station_codes)
    selectable_components = {
        component for component, count in counts.items() if count > 0
    }
    selected_components = set(selected_measurement_codes or ())
    allowed_components = selected_components & selectable_components
    if not allowed_components:
        allowed_components = selectable_components

    return [
        component for component in MEASUREMENT_SPECS if component in allowed_components
    ]


def build_measurement_schema(
    integration_data: IntegrationData,
    selected_station_codes: list[str],
    defaults: list[str],
    measurement_names: dict[str, str],
) -> vol.Schema:
    """Build the measurement selection schema."""

    counts = _count_available_measurements(integration_data, selected_station_codes)
    station_count = len(selected_station_codes)
    options = []
    for component in MEASUREMENT_SPECS:
        available_count = counts[component]
        if available_count == 0:
            continue

        label = f"{measurement_names[component]} ({available_count}/{station_count})"
        options.append({"value": component, "label": label})

    return vol.Schema(
        {
            vol.Required(CONF_MEASUREMENTS, default=defaults): SelectSelector(
                SelectSelectorConfig(options=options, multiple=True)
            )
        }
    )
