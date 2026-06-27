"""Data fetch coordinator and refresh logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from functools import partial
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
    STATION_UPDATE_INTERVAL,
    STATIONS_URL,
)
from .measurements_parser import SelectedMetric, parse_lumes_csv
from .station import Station
from .stations_parser import parse_station_geojson

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IntegrationData:
    """Normalized data exposed to entities."""

    stations: dict[str, Station]
    measurements: dict[tuple[str, str], SelectedMetric]


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
            with await self.hass.async_add_executor_job(
                partial(urlopen, STATIONS_URL, timeout=HTTP_TIMEOUT_SECONDS)
            ) as response:
                payload = await self.hass.async_add_executor_job(response.read)
            self.stations = parse_station_geojson(payload)
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
            with await self.hass.async_add_executor_job(
                partial(urlopen, MEASUREMENTS_URL, timeout=HTTP_TIMEOUT_SECONDS)
            ) as response:
                payload = await self.hass.async_add_executor_job(response.read)
            measurements = parse_lumes_csv(payload)
        except Exception as err:
            raise UpdateFailed(
                "Could not update Wiener Luftmessnetz measurements"
            ) from err

        if station_refresh_succeeded:
            self._log_unknown_station_codes(measurements)

        return IntegrationData(
            stations=self.stations,
            measurements=measurements,
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
