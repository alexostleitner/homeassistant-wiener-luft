"""Data fetch coordinator and refresh logic."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
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
    STATION_SNAPSHOT,
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

        config_entry = getattr(self, "config_entry", None)
        entry_data = getattr(config_entry, "data", None) if config_entry else None
        if isinstance(entry_data, dict):
            self.stations = _parse_station_snapshot(
                entry_data.get(STATION_SNAPSHOT)
            ) or self.stations
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
        config_entry = getattr(self, "config_entry", None)
        hass = getattr(self, "hass", None)
        config_entries = getattr(hass, "config_entries", None) if hass else None
        if (
            config_entry is not None
            and config_entries is not None
            and hasattr(config_entries, "async_update_entry")
        ):
            entry_data = getattr(config_entry, "data", None)
            data = dict(entry_data) if entry_data is not None else {}
            snapshot = _station_snapshot(self.stations)
            if data.get(STATION_SNAPSHOT) != snapshot:
                data[STATION_SNAPSHOT] = snapshot
                config_entries.async_update_entry(config_entry, data=data)
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


def _station_snapshot(stations: dict[str, Station]) -> dict[str, dict[str, object]]:
    """Serialize station metadata for persistence."""

    return {
        code: asdict(station)
        for code, station in sorted(stations.items())
    }


def _parse_station_snapshot(value: object) -> dict[str, Station] | None:
    """Parse a persisted station snapshot."""

    if not isinstance(value, dict):
        return None

    stations: dict[str, Station] = {}
    for code, station_data in value.items():
        station = _parse_station_snapshot_item(code, station_data)
        if station is None:
            return None
        stations[code] = station
    return stations


def _parse_station_snapshot_item(code: object, value: object) -> Station | None:
    """Parse one persisted station entry."""

    if not isinstance(code, str) or not isinstance(value, dict):
        return None

    stored_code = value.get("code", code)
    name = value.get("name")
    district = value.get("district")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    station_url = value.get("station_url")
    if stored_code != code or not isinstance(name, str):
        return None
    if district is not None and not isinstance(district, int):
        return None
    if latitude is not None and not isinstance(latitude, (int, float)):
        return None
    if longitude is not None and not isinstance(longitude, (int, float)):
        return None
    if station_url is not None and not isinstance(station_url, str):
        return None

    return Station(
        code=code,
        name=name,
        district=district,
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        station_url=station_url,
    )


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
