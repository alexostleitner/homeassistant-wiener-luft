"""Sensor entities and setup helpers."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CALM_WIND_SPEED_MPS,
    CONF_MEASUREMENTS,
    CONF_STATIONS,
    DOMAIN,
)
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


def _build_unique_id(station_code: str, component: str) -> str:
    """Build the stable unique ID for one station/measurement entity."""

    return (
        f"{DOMAIN}_{MEASUREMENT_SPECS[component].measurement_slug}_"
        f"{slugify(station_code)}"
    )


def _sync_entity_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    selected_stations: set[str] | None,
    selected_measurements: set[str] | None,
) -> None:
    """Enable or disable registry entries to match explicit selections."""

    if selected_stations is None or selected_measurements is None:
        return

    selected_unique_ids = {
        _build_unique_id(station_code, component)
        for station_code in selected_stations
        for component in selected_measurements
    }
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.domain != "sensor"
            or not registry_entry.unique_id.startswith(f"{DOMAIN}_")
        ):
            continue
        if registry_entry.unique_id in selected_unique_ids:
            if registry_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                registry.async_update_entity(
                    registry_entry.entity_id,
                    disabled_by=None,
                )
            continue
        if registry_entry.disabled_by is None:
            registry.async_update_entity(
                registry_entry.entity_id,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            )


def _build_entities(
    coordinator: IntegrationCoordinator,
    selected_stations: set[str] | None,
    selected_measurements: set[str] | None,
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
            or (
                selected_stations is not None and station_code not in selected_stations
            )
            or (
                selected_measurements is not None
                and component not in selected_measurements
            )
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
    preferences = dict(entry.data)
    preferences.update(entry.options)
    if CONF_STATIONS in preferences and CONF_MEASUREMENTS in preferences:
        selected_stations = set(preferences[CONF_STATIONS])
        selected_measurements = set(preferences[CONF_MEASUREMENTS])
    else:
        selected_stations = None
        selected_measurements = None
    _sync_entity_registry(hass, entry, selected_stations, selected_measurements)
    entities = _build_entities(
        coordinator,
        selected_stations,
        selected_measurements,
    )
    known_entity_keys = {
        (entity._station_code, entity._component) for entity in entities
    }
    async_add_entities(entities)

    def async_add_new_entities() -> None:
        new_entities = _build_entities(
            coordinator,
            selected_stations,
            selected_measurements,
            known_entity_keys,
        )
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
        self._attr_unique_id = _build_unique_id(station.code, component)
        self._attr_device_info = station_device_info(station)

    @property
    def available(self) -> bool:
        return self._availability_state == "available"

    @property
    def native_value(self) -> float | None:
        reading = self._reading
        if reading is None:
            return None
        if self._component == "WR" and self._wind_speed_is_calm:
            return None
        return reading.value

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
        if (
            self.coordinator.data is not None
            and (self._station_code, self._component)
            in self.coordinator.data.stale_measurements
        ):
            return "stale"
        return "available"

    @property
    def _wind_speed_is_calm(self) -> bool:
        if self.coordinator.data is None:
            return False

        wind_speed = self.coordinator.data.measurements.get(
            (self._station_code, "WG")
        )
        if wind_speed is None or wind_speed.value is None:
            return False

        if wind_speed.unit == "m/s":
            return wind_speed.value < CALM_WIND_SPEED_MPS
        if wind_speed.unit == "km/h":
            return wind_speed.value / 3.6 < CALM_WIND_SPEED_MPS
        return False

    def _log_unit_change(self) -> None:
        hass = getattr(self, "hass", None)
        entity_id = getattr(self, "entity_id", None)
        if hass is None or entity_id is None:
            return

        old_state = hass.states.get(entity_id)
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
            entity_id,
            previous_unit,
            current_unit,
        )
