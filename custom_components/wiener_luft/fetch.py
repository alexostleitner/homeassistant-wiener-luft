"""Source fetching helpers for stations and measurements."""

from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from homeassistant.core import HomeAssistant

from .const import (
    HTTP_TIMEOUT_SECONDS,
    MEASUREMENTS_URL,
    STATIONS_URL,
)
from .exceptions import FlowFetchError
from .measurements_parser import SelectedMeasurements, parse_lumes_csv
from .station import Station
from .stations_parser import parse_station_geojson


def _fetch_payload(url: str) -> bytes:
    """Fetch one payload from the configured source URL."""

    try:
        with urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as err:
        raise FlowFetchError("cannot_connect", {"url": url}) from err


async def async_fetch_stations(hass: HomeAssistant) -> dict[str, Station]:
    """Fetch and parse station metadata."""

    try:
        stations = parse_station_geojson(
            await hass.async_add_executor_job(_fetch_payload, STATIONS_URL)
        )
    except FlowFetchError:
        raise
    except Exception as err:
        raise FlowFetchError("invalid_response", {"url": STATIONS_URL}) from err

    if not stations:
        raise FlowFetchError("invalid_response", {"url": STATIONS_URL})
    return stations


async def async_fetch_measurements(
    hass: HomeAssistant,
) -> SelectedMeasurements:
    """Fetch and parse current measurements."""

    try:
        return parse_lumes_csv(
            await hass.async_add_executor_job(_fetch_payload, MEASUREMENTS_URL)
        )
    except FlowFetchError:
        raise
    except Exception as err:
        raise FlowFetchError("invalid_response", {"url": MEASUREMENTS_URL}) from err
