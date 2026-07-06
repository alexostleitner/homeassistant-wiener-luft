"""Source fetching helpers for stations and measurements."""

from __future__ import annotations

from collections.abc import Callable
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

type PayloadParser[T] = Callable[[bytes], T]


def _fetch_payload(url: str) -> bytes:
    """Fetch one payload from the configured source URL."""

    try:
        with urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as err:
        raise FlowFetchError("cannot_connect", {"url": url}) from err


async def async_fetch_parsed_payload[T](
    hass: HomeAssistant,
    *,
    url: str,
    fetch_payload: Callable[[str], bytes],
    parser: PayloadParser[T],
) -> T:
    """Fetch one payload and parse it, wrapping parser errors consistently."""

    try:
        return parser(await hass.async_add_executor_job(fetch_payload, url))
    except FlowFetchError:
        raise
    except Exception as err:
        raise FlowFetchError("invalid_response", {"url": url}) from err


async def async_fetch_stations(hass: HomeAssistant) -> dict[str, Station]:
    """Fetch and parse station metadata."""

    stations = await async_fetch_parsed_payload(
        hass,
        url=STATIONS_URL,
        fetch_payload=_fetch_payload,
        parser=parse_station_geojson,
    )
    if not stations:
        raise FlowFetchError("invalid_response", {"url": STATIONS_URL})
    return stations


async def async_fetch_measurements(
    hass: HomeAssistant,
) -> SelectedMeasurements:
    """Fetch and parse current measurements."""

    return await async_fetch_parsed_payload(
        hass,
        url=MEASUREMENTS_URL,
        fetch_payload=_fetch_payload,
        parser=parse_lumes_csv,
    )
