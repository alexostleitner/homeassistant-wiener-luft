"""Data fetch coordinator and refresh logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    HTTP_TIMEOUT_SECONDS,
    MEASUREMENT_UPDATE_INTERVAL,
    MEASUREMENTS_URL,
    NAME,
    SOURCE_SNAPSHOT,
    STALE_AFTER,
    STATION_UPDATE_INTERVAL,
    STATIONS_URL,
)
from .measurements import MEASUREMENT_SPECS
from .measurements_parser import SelectedMetric, parse_lumes_csv
from .station import Station
from .stations_parser import parse_station_geojson

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FlowFetchError(Exception):
    """Structured fetch error that can be surfaced in config flow UI."""

    reason: str
    placeholders: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class IntegrationData:
    """Normalized data exposed to entities."""

    stations: dict[str, Station]
    measurements: dict[tuple[str, str], SelectedMetric]
    stale_measurements: frozenset[tuple[str, str]] = field(default_factory=frozenset)


class IntegrationCoordinator(
    DataUpdateCoordinator[IntegrationData]
):
    """Coordinate data refreshes."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry | None = None
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=NAME,
            update_interval=MEASUREMENT_UPDATE_INTERVAL,
            config_entry=config_entry,
            always_update=False,
        )
        self.stations: dict[str, Station] = {}
        self._stations_last_refresh_attempt: datetime | None = None

    async def _async_setup(self) -> None:
        """Load station metadata before the first measurement update."""

        await self.async_refresh_stations(force=True)

    async def async_refresh_stations(self, force: bool = False) -> bool:
        """Refresh station metadata at most once per day."""

        now = dt_util.utcnow()
        if (
            not force
            and self._stations_last_refresh_attempt is not None
            and now - self._stations_last_refresh_attempt < STATION_UPDATE_INTERVAL
        ):
            return False

        self._stations_last_refresh_attempt = now
        try:
            self.stations = await async_fetch_stations(self.hass)
        except Exception as err:
            if not self.stations:
                raise UpdateFailed("Could not load station metadata") from err
            LOGGER.warning("Could not refresh station metadata; keeping cached data")
            return False
        return True

    async def _async_update_data(self) -> IntegrationData:
        """Fetch current measurements and combine them with cached stations."""

        station_refresh_succeeded = await self.async_refresh_stations()

        try:
            measurements = await async_fetch_measurements(self.hass)
        except Exception as err:
            raise UpdateFailed(
                "Could not update Wiener Luftmessnetz measurements"
            ) from err

        if station_refresh_succeeded:
            self._log_unknown_station_codes(measurements)
            self._log_new_source_items(measurements)

        now = dt_util.utcnow()
        return IntegrationData(
            stations=self.stations,
            measurements=measurements,
            stale_measurements=_stale_measurements(measurements, now),
        )

    def _log_unknown_station_codes(
        self, measurements: dict[tuple[str, str], SelectedMetric]
    ) -> None:
        """Log stations present in measurements but missing from station metadata."""

        for station_code in dict.fromkeys(
            station_code for station_code, _component in measurements
        ):
            if station_code in self.stations:
                continue
            LOGGER.warning(
                "Wiener Luftmessnetz CSV contains unknown station code %s that is not "
                "present in station metadata",
                station_code,
            )

    def _log_new_source_items(
        self, measurements: dict[tuple[str, str], SelectedMetric]
    ) -> None:
        """Log source items that were not present in the last stored snapshot."""

        preferences = getattr(self, "config_entry", None)
        if preferences is None:
            return

        current_preferences = dict(preferences.data)
        current_preferences.update(preferences.options)
        previous_source_items = _parse_source_snapshot(
            current_preferences.get(SOURCE_SNAPSHOT)
        )
        if previous_source_items is None:
            return

        previous_station_codes, previous_measurement_keys = previous_source_items
        current_station_codes, current_measurement_keys = _source_items(
            self.stations, measurements
        )
        new_station_codes = current_station_codes - previous_station_codes
        new_measurement_keys = current_measurement_keys - previous_measurement_keys
        if not new_station_codes and not new_measurement_keys:
            return

        LOGGER.info(
            "Wiener Luftmessnetz exposes %d new station(s) and %d new "
            "station/measurement combination(s) since the last saved configuration. "
            "Open the integration options to review and save the updated snapshot.",
            len(new_station_codes),
            len(new_measurement_keys),
        )


def _parse_source_snapshot(
    value: object,
) -> tuple[set[str], set[tuple[str, str]]] | None:
    """Parse the stored source snapshot from config entry data or options."""

    if not isinstance(value, dict):
        return None

    station_codes = value.get("station_codes")
    measurement_keys = value.get("measurement_keys")
    if not isinstance(station_codes, list) or not isinstance(measurement_keys, list):
        return None

    if any(not isinstance(item, (list, tuple)) for item in measurement_keys):
        return None

    previous_station_codes = set(station_codes)
    previous_measurement_keys = {tuple(item) for item in measurement_keys}
    if any(
        not isinstance(station_code, str)
        for station_code in previous_station_codes
    ):
        return None
    if any(
        len(item) != 2
        or not isinstance(item[0], str)
        or not isinstance(item[1], str)
        for item in previous_measurement_keys
    ):
        return None

    return previous_station_codes, previous_measurement_keys


def _source_items(
    stations: dict[str, Station],
    measurements: dict[tuple[str, str], SelectedMetric],
) -> tuple[set[str], set[tuple[str, str]]]:
    """Return the currently available station and measurement keys."""

    current_station_codes = set(stations)
    current_measurement_keys = {
        (station_code, component)
        for (station_code, component), reading in measurements.items()
        if station_code in stations
        and component in MEASUREMENT_SPECS
        and reading.value is not None
        and reading.measurement_type is not None
    }
    return current_station_codes, current_measurement_keys


def _source_snapshot(
    stations: dict[str, Station],
    measurements: dict[tuple[str, str], SelectedMetric],
) -> dict[str, list]:
    """Serialize the currently available station and measurement keys."""

    station_codes, measurement_keys = _source_items(stations, measurements)
    return {
        "station_codes": sorted(station_codes),
        "measurement_keys": [list(item) for item in sorted(measurement_keys)],
    }


def _fetch_payload(url: str) -> bytes:
    """Fetch one payload from the configured source URL."""

    try:
        with urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as err:
        raise FlowFetchError("cannot_connect", {"url": url}) from err


def _stale_measurements(
    measurements: dict[tuple[str, str], SelectedMetric],
    now: datetime,
) -> frozenset[tuple[str, str]]:
    """Return the measurement keys that should currently be treated as stale."""

    return frozenset(
        key
        for key, reading in measurements.items()
        if reading.measured_at is not None and now - reading.measured_at > STALE_AFTER
    )


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
) -> dict[tuple[str, str], SelectedMetric]:
    """Fetch and parse current measurements."""

    try:
        return parse_lumes_csv(
            await hass.async_add_executor_job(_fetch_payload, MEASUREMENTS_URL)
        )
    except FlowFetchError:
        raise
    except Exception as err:
        raise FlowFetchError("invalid_response", {"url": MEASUREMENTS_URL}) from err
