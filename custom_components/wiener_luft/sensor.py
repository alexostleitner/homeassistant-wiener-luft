"""Sensor entities and setup helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .client import SelectedMetric, Station
from .const import DOMAIN
from .coordinator import IntegrationCoordinator
from .measurements import MEASUREMENT_SPECS, MeasurementSpec

NOX_ICON = "mdi:molecule"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""

    coordinator = entry.runtime_data

    def build_entities(
        known_entity_keys: set[tuple[str, str]] | None = None,
    ) -> list[MeasurementSensor]:
        entities: list[MeasurementSensor] = []
        if coordinator.data is None:
            return entities

        for (station_code, component), reading in (
            coordinator.data.measurements.selected.items()
        ):
            station = coordinator.data.stations.get(station_code)
            entity_key = (station_code, component)
            if station is None or not reading.available:
                continue
            if known_entity_keys is not None and entity_key in known_entity_keys:
                continue

            entities.append(
                MeasurementSensor(
                    coordinator,
                    station,
                    component,
                    MEASUREMENT_SPECS[component],
                )
            )
        return entities

    entities = build_entities()
    known_entity_keys = {(entity.station_code, entity.component) for entity in entities}
    async_add_entities(entities)

    def async_add_new_entities() -> None:
        """Add sensors for newly available station/measurement pairs."""

        new_entities = build_entities(known_entity_keys)
        if not new_entities:
            return

        known_entity_keys.update(
            {(entity.station_code, entity.component) for entity in new_entities}
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
        component_slug = component.lower().replace(".", "")
        station_slug = slugify(station.name or station.code)

        self._attr_name = measurement_spec.name
        self._attr_device_class = (
            SensorDeviceClass[measurement_spec.device_class]
            if measurement_spec.device_class is not None
            else None
        )
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT_ANGLE
            if component == "WR"
            else SensorStateClass.MEASUREMENT
        )
        self._attr_icon = NOX_ICON if component == "NOX" else None
        self._attr_unique_id = f"{DOMAIN}_{station.code.lower()}_{component_slug}"
        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._station_code)},
            "name": station.name,
            "manufacturer": "Wiener Luft",
        }
        if station.station_url:
            device_info["configuration_url"] = station.station_url
        self._attr_device_info = device_info
        self.entity_id = f"sensor.{DOMAIN}_{component_slug}_{station_slug}"

    @property
    def available(self) -> bool:
        """Return whether the selected reading is currently available."""

        reading = self._reading
        return (
            self.coordinator.last_update_success
            and reading is not None
            and reading.value is not None
        )

    @property
    def native_value(self) -> float | None:
        """Return the current selected measurement value."""

        reading = self._reading
        return reading.value if reading is not None else None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit reported by the source CSV."""

        reading = self._reading
        return reading.unit if reading is not None else self._measurement_spec.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return stable sensor attributes."""

        station = self._current_station
        reading = self._reading
        attributes: dict[str, Any] = {
            "station_code": self._station_code,
            "station_name": station.name,
            "district": station.district,
            ATTR_LATITUDE: station.latitude,
            ATTR_LONGITUDE: station.longitude,
            "component": self._component,
            "measurement_type": reading.measurement_type if reading else None,
        }
        if station.station_url:
            attributes["station_url"] = station.station_url
        return attributes

    @property
    def _reading(self) -> SelectedMetric | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.measurements.selected.get(
            (self._station_code, self._component)
        )

    @property
    def _current_station(self) -> Station:
        if self.coordinator.data is None:
            return self._station
        return self.coordinator.data.stations.get(self._station_code, self._station)

    @property
    def station_code(self) -> str:
        """Return the station code for setup-time entity tracking."""

        return self._station_code

    @property
    def component(self) -> str:
        """Return the measurement component for setup-time entity tracking."""

        return self._component
