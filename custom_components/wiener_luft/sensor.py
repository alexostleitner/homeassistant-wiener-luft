"""Sensor platform setup and entrypoint."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MEASUREMENTS, CONF_STATIONS, DOMAIN
from .coordinator import IntegrationCoordinator
from .measurements import MEASUREMENT_SPECS
from .measurements_parser import MeasurementKey
from .sensor_entity import MeasurementSensor

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""

    _SensorPlatformSetup(hass, entry, async_add_entities).setup()


class _SensorPlatformSetup:
    """Set up and extend sensor entities for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator: IntegrationCoordinator = entry.runtime_data
        self.async_add_entities = async_add_entities
        self.station_filter, self.measurement_filter = self._selected_filters()
        self.known_measurement_keys: set[MeasurementKey] = set()

    def setup(self) -> None:
        """Set up the initial sensor entities and register future updates."""

        LOGGER.debug(
            "Starting sensor setup for entry %s (stations=%s, measurements=%s)",
            self.entry.entry_id,
            self.station_filter,
            self.measurement_filter,
        )
        self._sync_registry()
        self._add_initial_entities()
        self._register_listener()

    def _sync_registry(self) -> None:
        """Enable or disable registry entries to match explicit selections."""

        if self.station_filter is None or self.measurement_filter is None:
            return

        selected_unique_ids = {
            MeasurementSensor.build_unique_id(station_code, measurement_code)
            for station_code in self.station_filter
            for measurement_code in self.measurement_filter
            if measurement_code in MEASUREMENT_SPECS
        }
        registry = er.async_get(self.hass)
        for registry_entry in er.async_entries_for_config_entry(
            registry, self.entry.entry_id
        ):
            self._sync_registry_entry(
                registry,
                registry_entry,
                selected_unique_ids,
            )

    def _sync_registry_entry(
        self,
        registry: er.EntityRegistry,
        registry_entry: er.RegistryEntry,
        selected_unique_ids: set[str],
    ) -> None:
        """Enable or disable one registry entry to match explicit selections."""

        if registry_entry.domain != "sensor" or not registry_entry.unique_id.startswith(
            f"{DOMAIN}_"
        ):
            return
        if registry_entry.unique_id in selected_unique_ids:
            if registry_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                registry.async_update_entity(
                    registry_entry.entity_id,
                    disabled_by=None,
                )
            return
        if registry_entry.disabled_by is None:
            registry.async_update_entity(
                registry_entry.entity_id,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            )

    def _add_initial_entities(self) -> None:
        """Add the measurement entities available during initial setup."""

        available_entities = self._available_entities()
        self.known_measurement_keys = set(available_entities)
        self.async_add_entities(available_entities.values())

    def _register_listener(self) -> None:
        """Register the coordinator listener that adds newly available entities."""

        LOGGER.debug(
            "Registering coordinator listener for entry %s",
            self.entry.entry_id,
        )
        remove_listener = self.coordinator.async_add_listener(
            self._handle_coordinator_update
        )
        LOGGER.debug(
            "Registered coordinator listener for entry %s",
            self.entry.entry_id,
        )
        self.entry.async_on_unload(remove_listener)

    def _handle_coordinator_update(self) -> None:
        """Add entities that became available after a coordinator update."""

        available_entities = self._available_entities()
        new_entities = {
            measurement_key: entity
            for measurement_key, entity in available_entities.items()
            if measurement_key not in self.known_measurement_keys
        }
        if not new_entities:
            return

        self.known_measurement_keys.update(new_entities)
        self.async_add_entities(new_entities.values())

    def _available_entities(self) -> dict[MeasurementKey, MeasurementSensor]:
        """Return the measurement entities that can currently be created."""

        data = self.coordinator.data
        if data is None:
            return {}

        measurements = data.measurements
        measurement_codes = self._selected_measurement_codes()
        entities: dict[MeasurementKey, MeasurementSensor] = {}
        for station_code, station in data.stations.items():
            if (
                self.station_filter is not None
                and station_code not in self.station_filter
            ):
                continue

            for measurement_code in measurement_codes:
                measurement_key = (station_code, measurement_code)
                reading = measurements.get(measurement_key)
                if (
                    reading is None
                    or reading.value is None
                    or reading.measurement_type is None
                ):
                    continue

                entities[measurement_key] = MeasurementSensor(
                    self.coordinator,
                    station,
                    measurement_code,
                    MEASUREMENT_SPECS[measurement_code],
                )
        return entities

    def _selected_filters(self) -> tuple[set[str] | None, set[str] | None]:
        """Return the explicitly configured station and measurement filters."""

        merged_entry_data = dict(self.entry.data)
        merged_entry_data.update(self.entry.options)
        if (
            CONF_STATIONS not in merged_entry_data
            or CONF_MEASUREMENTS not in merged_entry_data
        ):
            return None, None

        return (
            set(merged_entry_data[CONF_STATIONS]),
            set(merged_entry_data[CONF_MEASUREMENTS]),
        )

    def _selected_measurement_codes(self) -> tuple[str, ...]:
        """Return the measurement codes that should currently create entities."""

        if self.measurement_filter is None:
            return tuple(MEASUREMENT_SPECS)

        return tuple(
            measurement_code
            for measurement_code in MEASUREMENT_SPECS
            if measurement_code in self.measurement_filter
        )
