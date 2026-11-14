"""Station selection helpers for config flows."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Protocol, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_STATIONS, RECOMMENDED_STATION_COUNT
from .models import IntegrationData
from .station import Station


class _ConfigWithCoordinates(Protocol):
    """Subset of Home Assistant config used by station ordering."""

    latitude: float | None
    longitude: float | None


@dataclass(frozen=True, slots=True)
class StationChoices:
    """Station selector options and their ordering mode."""

    options: list[tuple[Station, int | None]]
    distance_sorted: bool


def _station_distance_km(
    home_latitude: float,
    home_longitude: float,
    station: Station,
) -> float:
    """Return the distance in km between HA and one station."""

    earth_radius_km = 6371.0
    station_latitude = station.latitude
    station_longitude = station.longitude
    assert station_latitude is not None
    assert station_longitude is not None

    delta_lat = radians(station_latitude - home_latitude)
    delta_lon = radians(station_longitude - home_longitude)
    a = (
        sin(delta_lat / 2) ** 2
        + cos(radians(home_latitude))
        * cos(radians(station_latitude))
        * sin(delta_lon / 2) ** 2
    )
    a = max(0.0, min(1.0, a))
    return 2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a))


def _alphabetical_stations(stations: list[Station]) -> StationChoices:
    """Return stations in the existing alphabetical order."""

    return StationChoices(
        options=[
            (station, None)
            for station in sorted(
                stations, key=lambda station: (station.name.casefold(), station.code)
            )
        ],
        distance_sorted=False,
    )


def sorted_stations_for_flow(
    integration_data: IntegrationData,
    hass: HomeAssistant,
) -> StationChoices:
    """Return station ordering for the selector."""

    stations = list(integration_data.stations.values())
    config = cast(_ConfigWithCoordinates, hass.config)
    home_latitude = config.latitude
    home_longitude = config.longitude
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
    return StationChoices(
        options=[
            (station, round(distance_km)) for distance_km, station in ranked_stations
        ],
        distance_sorted=True,
    )


def recommended_station_count(station_choices: StationChoices) -> int | None:
    """Return the default number of stations for a distance-sorted list."""

    if station_choices.distance_sorted:
        return RECOMMENDED_STATION_COUNT
    return None


def build_station_schema(
    station_choices: StationChoices,
    defaults: list[str],
) -> vol.Schema:
    """Build the station selection schema."""

    options: list[SelectOptionDict] = [
        {
            "value": station.code,
            "label": (
                station.name
                if distance_km is None
                else f"{station.name} ({distance_km} km)"
            ),
        }
        for station, distance_km in station_choices.options
    ]
    return vol.Schema(
        {
            vol.Required(CONF_STATIONS, default=defaults): SelectSelector(
                SelectSelectorConfig(options=options, multiple=True)
            )
        }
    )


def station_defaults(
    available_codes: list[str],
    selected_codes: list[str] | None = None,
    *,
    recommended_count: int | None = None,
) -> list[str]:
    """Return station defaults, using saved selections when available."""

    if not selected_codes:
        if recommended_count is not None:
            return available_codes[:recommended_count]
        return available_codes

    selected_code_set = set(selected_codes)
    return [
        code for code in available_codes if code in selected_code_set
    ] or available_codes
