"""Sensor entities and setup helpers."""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import DOMAIN, STALE_AFTER
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

LOGGER = logging.getLogger(__name__)
StateToken = tuple[str, datetime | None, str, Station]


def _build_entities(
    coordinator: IntegrationCoordinator,
    known_entity_keys: set[tuple[str, str]] | None = None,
) -> list[MeasurementSensor]:
    entities: list[MeasurementSensor] = []
    if coordinator.data is None:
        return entities

    for (station_code, component), reading in (
        coordinator.data.measurements.items()
    ):
        station = coordinator.data.stations.get(station_code)
        entity_key = (station_code, component)
        if (
            station is None
            or reading.value is None
            or reading.measurement_type is None
        ):
            continue
        if known_entity_keys is not None and entity_key in known_entity_keys:
            continue

        spec = MEASUREMENT_SPECS.get(component)
        if spec is None:
            continue

        entities.append(
            MeasurementSensor(
                coordinator,
                station,
                component,
                spec,
            )
        )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""

    coordinator = entry.runtime_data
    entities = _build_entities(coordinator)
    known_entity_keys = {
        (entity._station_code, entity._component) for entity in entities
    }
    async_add_entities(entities)

    def async_add_new_entities() -> None:
        new_entities = _build_entities(coordinator, known_entity_keys)
        if not new_entities:
            return

        known_entity_keys.update(
            {(entity._station_code, entity._component) for entity in new_entities}
        )
        async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class MeasurementSensor(CoordinatorEntity, SensorEntity):
    """Measurement sensor backed by coordinator data."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: IntegrationCoordinator,
        station: Station,
        component: str,
        measurement_spec: MeasurementSpec,
    ) -> None:
        super().__init__(coordinator)
        self._station_code = station.code
        self._station = station
        self._component = component
        self._measurement_spec = measurement_spec

        self._attr_translation_key = measurement_spec.translation_key
        self._attr_device_class = (
            getattr(SensorDeviceClass, measurement_spec.device_class)
            if measurement_spec.device_class is not None
            else None
        )
        self._attr_state_class = getattr(
            SensorStateClass, measurement_spec.state_class
        )
        self._attr_icon = measurement_spec.icon
        self._attr_suggested_display_precision = (
            DISPLAY_PRECISION_BY_UNIT.get(measurement_spec.unit)
        )
        unique_id = (
            f"{DOMAIN}_{measurement_spec.measurement_slug}_{slugify(station.code)}"
        )
        self._attr_unique_id = unique_id
        self._attr_device_info = station_device_info(station)
        self.entity_id = f"sensor.{unique_id}"
        self._last_written_token = self._state_token

    @property
    def available(self) -> bool:
        return self._availability_state == "available"

    @property
    def native_value(self) -> float | None:
        reading = self._reading
        return reading.value if reading is not None else None

    @property
    def native_unit_of_measurement(self) -> str:
        reading = self._reading
        return reading.unit if reading is not None else self._measurement_spec.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return station_state_attributes(self._current_station)

    def async_write_ha_state(self) -> None:
        self._log_unit_change()
        super().async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        state_token = self._state_token
        if state_token == self._last_written_token:
            return

        self._last_written_token = state_token
        self.async_write_ha_state()

    @property
    def _reading(self) -> SelectedMetric | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.measurements.get(
            (self._station_code, self._component)
        )

    @property
    def _current_station(self) -> Station:
        if self.coordinator.data is None:
            return self._station
        return self.coordinator.data.stations.get(self._station_code, self._station)

    @property
    def _availability_state(self) -> str:
        reading = self._reading
        if not self.coordinator.last_update_success:
            return "coordinator_unavailable"
        if reading is None or reading.value is None:
            return "missing"
        if self._is_stale(reading):
            return "stale"
        return "available"

    @property
    def _state_token(self) -> StateToken:
        reading = self._reading
        return (
            self._availability_state,
            None if reading is None else reading.measured_at,
            self.native_unit_of_measurement,
            self._current_station,
        )

    def _is_stale(self, reading: SelectedMetric) -> bool:
        measured_at = reading.measured_at
        if measured_at is None:
            return False
        now = dt_util.utcnow()
        if now is None:
            return False
        return now - measured_at > STALE_AFTER

    def _log_unit_change(self) -> None:
        hass = getattr(self, "hass", None)
        if hass is None or self.entity_id is None:
            return

        old_state = hass.states.get(self.entity_id)
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
