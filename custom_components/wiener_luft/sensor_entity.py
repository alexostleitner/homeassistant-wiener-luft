"""Sensor entity implementation and sensor-specific helpers."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CALM_WIND_SPEED_MPS, DOMAIN
from .coordinator import IntegrationCoordinator
from .measurements import (
    DISPLAY_PRECISION_BY_UNIT,
    MEASUREMENT_SPECS,
    MeasurementSpec,
)
from .measurements_parser import SelectedMetric
from .station import (
    Station,
    station_device_info,
    station_state_attributes,
)

LOGGER = logging.getLogger("custom_components.wiener_luft.sensor")


class MeasurementSensor(CoordinatorEntity[IntegrationCoordinator], SensorEntity):
    """Measurement sensor backed by coordinator data."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: IntegrationCoordinator,
        station: Station,
        measurement_code: str,
        measurement_spec: MeasurementSpec,
    ) -> None:
        super().__init__(coordinator)
        self._station_code = station.code
        self._station = station
        self._measurement_code = measurement_code
        self._measurement_spec = measurement_spec

        self._attr_translation_key = measurement_spec.translation_key
        self._attr_device_class = (
            getattr(SensorDeviceClass, measurement_spec.device_class)
            if measurement_spec.device_class is not None
            else None
        )
        self._attr_state_class = getattr(SensorStateClass, measurement_spec.state_class)
        self._attr_icon = measurement_spec.icon
        self._attr_suggested_display_precision = DISPLAY_PRECISION_BY_UNIT.get(
            measurement_spec.unit
        )
        self._attr_unique_id = self.build_unique_id(station.code, measurement_code)
        self._attr_device_info = station_device_info(station)

    @staticmethod
    def build_unique_id(station_code: str, measurement_code: str) -> str:
        """Build the stable unique ID for one station/measurement entity."""

        return (
            f"{DOMAIN}_{MEASUREMENT_SPECS[measurement_code].measurement_slug}_"
            f"{slugify(station_code)}"
        )

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False

        reading = self._reading
        if reading is None or reading.value is None:
            return False

        return not (
            self.coordinator.data is not None
            and (self._station_code, self._measurement_code)
            in self.coordinator.data.stale_measurements
        )

    @property
    def native_value(self) -> float | None:
        reading = self._reading
        if reading is None:
            return None
        if self._measurement_code == "WR" and self._wind_speed_is_calm():
            return None
        return reading.value

    @property
    def native_unit_of_measurement(self) -> str:
        reading = self._reading
        return reading.unit if reading is not None else self._measurement_spec.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = station_state_attributes(self._current_station)
        reading = self._reading
        if reading is not None and reading.measurement_type is not None:
            attributes["interval"] = reading.measurement_type
        return attributes

    def async_write_ha_state(self) -> None:
        self._log_unit_change()
        self._log_interval_change()
        super().async_write_ha_state()

    @property
    def _reading(self) -> SelectedMetric | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.measurements.get(
            (self._station_code, self._measurement_code)
        )

    @property
    def _current_station(self) -> Station:
        if self.coordinator.data is None:
            return self._station
        return self.coordinator.data.stations.get(self._station_code, self._station)

    @property
    def _wind_speed_reading(self) -> SelectedMetric | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.measurements.get((self._station_code, "WG"))

    def _wind_speed_is_calm(self) -> bool:
        wind_speed_reading = self._wind_speed_reading
        if wind_speed_reading is None or wind_speed_reading.value is None:
            return False
        if wind_speed_reading.unit == "m/s":
            return wind_speed_reading.value < CALM_WIND_SPEED_MPS
        if wind_speed_reading.unit == "km/h":
            return wind_speed_reading.value / 3.6 < CALM_WIND_SPEED_MPS
        return False

    def _log_unit_change(self) -> None:
        if self.hass is None or self.entity_id is None:
            return

        old_state = self.hass.states.get(self.entity_id)
        if old_state is None:
            return

        previous_unit = old_state.attributes.get("unit_of_measurement")
        if previous_unit is not None:
            previous_unit = previous_unit.replace(
                "\u00b5", unicodedata.normalize("NFKC", "\u00b5")
            )
        current_unit = self.native_unit_of_measurement
        if previous_unit is None or previous_unit == current_unit:
            return

        LOGGER.warning(
            "Unit of measurement for %s changed from %s to %s",
            self.entity_id,
            previous_unit,
            current_unit,
        )

    def _log_interval_change(self) -> None:
        reading = self._reading
        if self.hass is None or self.entity_id is None or reading is None:
            return

        old_state = self.hass.states.get(self.entity_id)
        if old_state is None:
            return

        previous_interval = old_state.attributes.get("interval")
        current_interval = reading.measurement_type
        if (
            previous_interval is None
            or current_interval is None
            or previous_interval == current_interval
        ):
            return

        LOGGER.warning(
            "Interval for %s changed from %s to %s",
            self.entity_id,
            previous_interval,
            current_interval,
        )
