"""UI config flow for setup and options."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from functools import cache
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import UnknownEntry
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_MEASUREMENTS, CONF_STATIONS, DOMAIN, NAME, SOURCE_SNAPSHOT
from .coordinator import (
    FlowFetchError,
    IntegrationData,
    _source_snapshot,
    async_fetch_measurements,
    async_fetch_stations,
)
from .measurements import MEASUREMENT_SPECS
from .station import Station

LOGGER = logging.getLogger(__name__)


async def _async_load_flow_data(
    hass,
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


async def _async_measurement_names(hass) -> dict[str, str]:
    """Return localized measurement names from integration translations."""

    language = getattr(getattr(hass, "config", None), "language", None) or "en"
    names = await hass.async_add_executor_job(_load_measurement_names, language)
    if language != "en":
        fallback = await hass.async_add_executor_job(_load_measurement_names, "en")
        names = fallback | names
    return {
        component: names.get(spec.translation_key, spec.translation_key)
        for component, spec in MEASUREMENT_SPECS.items()
    }


@cache
def _load_measurement_names(language: str) -> dict[str, str]:
    """Load translated sensor names for one language file."""

    path = Path(__file__).with_name("translations") / f"{language}.json"
    if not path.exists():
        return {}

    content = json.loads(path.read_text(encoding="utf-8"))
    return {
        translation_key: values["name"]
        for translation_key, values in content["entity"]["sensor"].items()
    }


def _measurement_counts(
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


def _station_distance_km(
    home_latitude: float,
    home_longitude: float,
    station: Station,
) -> float:
    """Return the distance in km between HA and one station."""

    earth_radius_km = 6371.0
    delta_lat = radians(station.latitude - home_latitude)
    delta_lon = radians(station.longitude - home_longitude)
    a = (
        sin(delta_lat / 2) ** 2
        + cos(radians(home_latitude))
        * cos(radians(station.latitude))
        * sin(delta_lon / 2) ** 2
    )
    a = max(0.0, min(1.0, a))
    return 2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a))


def _alphabetical_stations(
    stations: list[Station],
) -> list[tuple[Station, int | None]]:
    """Return stations in the existing alphabetical order."""

    return [
        (station, None)
        for station in sorted(
            stations, key=lambda station: (station.name.casefold(), station.code)
        )
    ]


def _sorted_stations(
    integration_data: IntegrationData,
    hass,
) -> list[tuple[Station, int | None]]:
    """Return station ordering for the selector."""

    stations = list(integration_data.stations.values())
    home_config = getattr(hass, "config", None)
    home_latitude = getattr(home_config, "latitude", None)
    home_longitude = getattr(home_config, "longitude", None)
    if home_latitude is None or home_longitude is None:
        return _alphabetical_stations(stations)

    ranked_stations: list[tuple[float, Station]] = []
    for station in stations:
        if station.latitude is None or station.longitude is None:
            return _alphabetical_stations(stations)
        ranked_stations.append(
            (
                _station_distance_km(home_latitude, home_longitude, station),
                station,
            )
        )

    ranked_stations.sort(
        key=lambda item: (item[0], item[1].name.casefold(), item[1].code)
    )
    return [(station, round(distance_km)) for distance_km, station in ranked_stations]


def _station_schema(
    stations: list[tuple[Station, int | None]],
    defaults: list[str],
) -> vol.Schema:
    """Build the station selection schema."""

    options = [
        {
            "value": station.code,
            "label": (
                station.name
                if distance_km is None
                else f"{station.name} ({distance_km} km)"
            ),
        }
        for station, distance_km in stations
    ]
    return vol.Schema(
        {
            vol.Required(CONF_STATIONS, default=defaults): SelectSelector(
                SelectSelectorConfig(options=options, multiple=True)
            )
        }
    )


def _station_defaults(
    available_codes: list[str],
    preferences: Mapping[str, object] | None = None,
    *,
    recommended_count: int | None = None,
) -> list[str]:
    """Return defaults for the station selection."""

    if (
        preferences is None
        or CONF_STATIONS not in preferences
        or CONF_MEASUREMENTS not in preferences
    ):
        if recommended_count is not None:
            return available_codes[:recommended_count]
        return available_codes

    selected_codes = set(preferences.get(CONF_STATIONS, ()))
    return [
        code for code in available_codes if code in selected_codes
    ] or available_codes


def _measurement_defaults(
    integration_data: IntegrationData,
    selected_station_codes: list[str],
    preferences: Mapping[str, object] | None = None,
) -> list[str]:
    """Return defaults for the measurement selection."""

    counts = _measurement_counts(integration_data, selected_station_codes)
    selectable_components = {
        component for component, count in counts.items() if count > 0
    }
    selected_components = (
        set(preferences.get(CONF_MEASUREMENTS, ()))
        if (
            preferences is not None
            and CONF_STATIONS in preferences
            and CONF_MEASUREMENTS in preferences
        )
        else set()
    )
    allowed_components = selected_components & selectable_components
    if not allowed_components:
        allowed_components = selectable_components

    return [
        component for component in MEASUREMENT_SPECS if component in allowed_components
    ]


def _measurement_schema(
    integration_data: IntegrationData,
    selected_station_codes: list[str],
    defaults: list[str],
    measurement_names: dict[str, str],
) -> vol.Schema:
    """Build the measurement selection schema."""

    counts = _measurement_counts(integration_data, selected_station_codes)
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


async def _async_station_step(
    flow,
    user_input: dict | None,
    *,
    step_id: str,
    preferences: Mapping[str, object] | None = None,
):
    """Handle the shared station-selection step."""

    if flow._integration_data is None:
        (
            flow._integration_data,
            error_key,
            placeholders,
        ) = await _async_load_flow_data(flow.hass)
        if error_key is not None:
            return flow.async_abort(
                reason=error_key,
                description_placeholders=placeholders,
            )

    errors: dict[str, str] = {}
    if user_input is not None:
        flow._selected_station_codes = list(user_input[CONF_STATIONS])
        if flow._selected_station_codes:
            return None
        errors["base"] = "station_required"

    assert flow._integration_data is not None
    stations = _sorted_stations(flow._integration_data, flow.hass)
    available_codes = [station.code for station, _distance_km in stations]
    description_placeholders = (
        {"station_count": str(len(available_codes))} if step_id == "user" else None
    )
    return flow.async_show_form(
        step_id=step_id,
        data_schema=_station_schema(
            stations,
            _station_defaults(
                available_codes,
                preferences,
                recommended_count=(
                    5 if stations and stations[0][1] is not None else None
                ),
            ),
        ),
        description_placeholders=description_placeholders,
        errors=errors,
    )


async def _async_measurement_step(
    flow,
    user_input: dict | None,
    *,
    preferences: Mapping[str, object] | None = None,
    title: str | None = None,
):
    """Handle the shared measurement-selection step."""

    assert flow._integration_data is not None
    assert flow._selected_station_codes is not None
    measurement_names = await _async_measurement_names(flow.hass)

    errors: dict[str, str] = {}
    if user_input is not None:
        selected_measurements = list(user_input[CONF_MEASUREMENTS])
        if selected_measurements:
            entry_data = {
                CONF_STATIONS: flow._selected_station_codes,
                CONF_MEASUREMENTS: selected_measurements,
                SOURCE_SNAPSHOT: _source_snapshot(
                    flow._integration_data.stations,
                    flow._integration_data.measurements,
                ),
            }
            if title is None:
                return flow.async_create_entry(data=entry_data)
            return flow.async_create_entry(title=title, data=entry_data)
        errors["base"] = "measurement_required"

    return flow.async_show_form(
        step_id="measurements",
        data_schema=_measurement_schema(
            flow._integration_data,
            flow._selected_station_codes,
            _measurement_defaults(
                flow._integration_data,
                flow._selected_station_codes,
                preferences,
            ),
            measurement_names,
        ),
        errors=errors,
    )


async def _async_reload_config_entry(flow) -> None:
    """Reload an options entry if it still exists."""

    config_entry = getattr(flow, "config_entry", None)
    if config_entry is None:
        return

    hass = getattr(flow, "hass", None)
    config_entries = getattr(hass, "config_entries", None) if hass else None
    async_reload = (
        getattr(config_entries, "async_reload", None) if config_entries else None
    )
    if async_reload is None:
        return

    LOGGER.debug("Reloading config entry %s after options save", config_entry.entry_id)
    try:
        await async_reload(config_entry.entry_id)
    except UnknownEntry:
        LOGGER.debug(
            "Skipping reload for missing config entry %s after options save",
            config_entry.entry_id,
        )
        return
    LOGGER.debug(
        "Finished reloading config entry %s after options save",
        config_entry.entry_id,
    )


class IntegrationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup via the UI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""

        self._integration_data: IntegrationData | None = None
        self._selected_station_codes: list[str] | None = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow for this config entry."""

        return IntegrationOptionsFlow()

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the station selection step."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        result = await _async_station_step(self, user_input, step_id="user")
        if result is not None:
            return result
        return await self.async_step_measurements()

    async def async_step_measurements(self, user_input: dict | None = None):
        """Handle the measurement selection step."""

        return await _async_measurement_step(
            self,
            user_input,
            title=NAME,
        )


class IntegrationOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing config entry."""

    def __init__(self) -> None:
        """Initialize options flow state."""

        self._integration_data: IntegrationData | None = None
        self._selected_station_codes: list[str] | None = None

    async def async_step_init(self, user_input: dict | None = None):
        """Handle the station selection step for options."""

        preferences = dict(self.config_entry.data)
        preferences.update(self.config_entry.options)
        result = await _async_station_step(
            self,
            user_input,
            step_id="init",
            preferences=preferences,
        )
        if result is not None:
            return result
        return await self.async_step_measurements()

    async def async_step_measurements(self, user_input: dict | None = None):
        """Handle the measurement selection step for options."""

        preferences = dict(self.config_entry.data)
        preferences.update(self.config_entry.options)
        result = await _async_measurement_step(
            self,
            user_input,
            preferences=preferences,
        )
        if result["type"] == "create_entry":
            LOGGER.debug(
                "Options flow created entry %s; reloading it",
                self.config_entry.entry_id,
            )
            await _async_reload_config_entry(self)
        return result
