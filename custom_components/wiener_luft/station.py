"""Station model and station-derived entity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, NAME


@dataclass(frozen=True, slots=True)
class Station:
    """Station metadata."""

    code: str
    name: str
    district: int | None
    latitude: float | None
    longitude: float | None
    station_url: str | None


def station_device_info(station: Station) -> DeviceInfo:
    """Build Home Assistant device metadata for one station."""

    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, station.code)},
        "name": station.name,
        "manufacturer": NAME,
    }
    if station.station_url:
        device_info["configuration_url"] = station.station_url
    return device_info


def station_state_attributes(station: Station) -> dict[str, Any]:
    """Build Home Assistant state attributes for one station."""

    return {
        "district": station.district,
        ATTR_LATITUDE: station.latitude,
        ATTR_LONGITUDE: station.longitude,
    }
