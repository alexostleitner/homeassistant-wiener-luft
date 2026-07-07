"""Data fetch coordinator and refresh logic."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .availability import (
    availability_changes,
    availability_items,
    unknown_station_codes,
)
from .const import (
    MEASUREMENT_UPDATE_INTERVAL,
    NAME,
    SOURCE_SNAPSHOT,
    STALE_AFTER,
    STATION_SNAPSHOT,
    STATION_UPDATE_INTERVAL,
)
from .exceptions import IntegrationError
from .fetch import async_fetch_measurements, async_fetch_stations
from .measurements_parser import MeasurementKey, SelectedMeasurements
from .models import IntegrationData
from .snapshots import (
    build_station_snapshot,
    restore_availability_snapshot,
    restore_station_snapshot,
)
from .station import Station

LOGGER = logging.getLogger(__name__)


class IntegrationCoordinator(DataUpdateCoordinator[IntegrationData]):
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
        self._cached_stations: dict[str, Station] = {}
        self._stations_last_refresh_attempt: datetime | None = None

    async def _async_setup(self) -> None:
        """Load station metadata before the first measurement update."""

        if self.config_entry is not None:
            self._cached_stations = (
                restore_station_snapshot(self.config_entry.data.get(STATION_SNAPSHOT))
                or self._cached_stations
            )
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
            self._cached_stations = await async_fetch_stations(self.hass)
        except IntegrationError as err:
            if not self._cached_stations:
                raise UpdateFailed("Could not load station metadata") from err
            LOGGER.warning("Could not refresh station metadata; keeping cached data")
            return False

        if self.config_entry is not None:
            data = dict(self.config_entry.data)
            snapshot = build_station_snapshot(self._cached_stations)
            if data.get(STATION_SNAPSHOT) != snapshot:
                LOGGER.debug(
                    "Persisting station snapshot for entry %s",
                    self.config_entry.entry_id,
                )
                data[STATION_SNAPSHOT] = snapshot
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
        return True

    async def _async_update_data(self) -> IntegrationData:
        """Fetch current measurements and combine them with cached stations."""

        station_refresh_succeeded = await self.async_refresh_stations()
        measurements = await self._async_fetch_measurements()
        if station_refresh_succeeded:
            self._log_source_changes(measurements)
        return self._build_integration_data(
            measurements,
            now=dt_util.utcnow(),
        )

    async def _async_fetch_measurements(self) -> SelectedMeasurements:
        """Fetch current measurements with the coordinator error boundary."""

        try:
            return await async_fetch_measurements(self.hass)
        except IntegrationError as err:
            raise UpdateFailed(
                "Could not update Wiener Luftmessnetz measurements"
            ) from err

    def _build_integration_data(
        self,
        measurements: SelectedMeasurements,
        *,
        now: datetime,
    ) -> IntegrationData:
        """Build the coordinator payload from current stations and measurements."""

        return IntegrationData(
            stations=self._cached_stations,
            measurements=measurements,
            stale_measurements=_stale_measurement_keys(measurements, now),
        )

    def _log_source_changes(self, measurements: SelectedMeasurements) -> None:
        """Log source differences after a successful station refresh."""

        self._log_unknown_station_codes(measurements)
        self._log_new_source_items(measurements)

    def _log_unknown_station_codes(self, measurements: SelectedMeasurements) -> None:
        """Log stations present in measurements but missing from station metadata."""

        for station_code in unknown_station_codes(self._cached_stations, measurements):
            LOGGER.warning(
                "Wiener Luftmessnetz CSV contains unknown station code %s that is not "
                "present in station metadata",
                station_code,
            )

    def _log_new_source_items(self, measurements: SelectedMeasurements) -> None:
        """Log source items that were not present in the last stored snapshot."""

        if self.config_entry is None:
            return

        merged_entry_data = dict(self.config_entry.data)
        merged_entry_data.update(self.config_entry.options)
        previous_source_items = restore_availability_snapshot(
            merged_entry_data.get(SOURCE_SNAPSHOT)
        )
        if previous_source_items is None:
            return

        new_station_codes, new_measurement_keys = availability_changes(
            previous_source_items,
            availability_items(self._cached_stations, measurements),
        )
        if not new_station_codes and not new_measurement_keys:
            return

        LOGGER.info(
            "Wiener Luftmessnetz exposes %d new station(s) and %d new "
            "station/measurement combination(s) since the last saved configuration. "
            "Open the integration options to review and save the updated snapshot.",
            len(new_station_codes),
            len(new_measurement_keys),
        )


def _stale_measurement_keys(
    measurements: SelectedMeasurements,
    now: datetime,
) -> frozenset[MeasurementKey]:
    """Return the measurement keys that should currently be treated as stale."""

    return frozenset(
        key
        for key, reading in measurements.items()
        if reading.measured_at is not None and now - reading.measured_at > STALE_AFTER
    )
