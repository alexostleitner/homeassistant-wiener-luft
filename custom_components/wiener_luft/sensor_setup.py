"""Sensor setup helpers."""

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
from .sensor_entity import MeasurementSensor, build_sensor_unique_id

LOGGER = logging.getLogger(__name__)


async def async_setup_sensors(
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
    LOGGER.debug(
        "Starting sensor setup for entry %s (stations=%s, measurements=%s)",
        entry.entry_id,
        selected_stations,
        selected_measurements,
    )
    _sync_entity_registry(hass, entry, selected_stations, selected_measurements)
    entities_by_measurement_key = _build_entities_by_measurement_key(
        coordinator,
        selected_stations,
        selected_measurements,
    )
    known_measurement_keys = set(entities_by_measurement_key)
    async_add_entities(entities_by_measurement_key.values())

    def async_add_new_entities() -> None:
        available_entities_by_measurement_key = _build_entities_by_measurement_key(
            coordinator,
            selected_stations,
            selected_measurements,
        )
        new_measurement_keys = (
            set(available_entities_by_measurement_key) - known_measurement_keys
        )
        new_entities = [
            available_entities_by_measurement_key[measurement_key]
            for measurement_key in new_measurement_keys
        ]
        if not new_entities:
            return

        known_measurement_keys.update(new_measurement_keys)
        async_add_entities(new_entities)

    LOGGER.debug(
        "Registering coordinator listener for entry %s",
        entry.entry_id,
    )
    remove_listener = coordinator.async_add_listener(async_add_new_entities)
    LOGGER.debug(
        "Registered coordinator listener for entry %s",
        entry.entry_id,
    )
    entry.async_on_unload(remove_listener)


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
        build_sensor_unique_id(station_code, measurement_code)
        for station_code in selected_stations
        for measurement_code in selected_measurements
    }
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.domain != "sensor" or not registry_entry.unique_id.startswith(
            f"{DOMAIN}_"
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


def _build_entities_by_measurement_key(
    coordinator: IntegrationCoordinator,
    selected_stations: set[str] | None,
    selected_measurements: set[str] | None,
) -> dict[MeasurementKey, MeasurementSensor]:
    """Build the currently available measurement entities."""

    if coordinator.data is None:
        return {}

    entities: dict[MeasurementKey, MeasurementSensor] = {}
    for station_code, station in coordinator.data.stations.items():
        if selected_stations is not None and station_code not in selected_stations:
            continue

        measurement_codes = (
            (
                measurement_code
                for measurement_code in MEASUREMENT_SPECS
                if measurement_code in selected_measurements
            )
            if selected_measurements is not None
            else MEASUREMENT_SPECS.keys()
        )
        for measurement_code in measurement_codes:
            spec = MEASUREMENT_SPECS.get(measurement_code)
            measurement_key = (station_code, measurement_code)
            reading = coordinator.data.measurements.get(measurement_key)
            if (
                spec is None
                or reading is None
                or reading.value is None
                or reading.measurement_type is None
            ):
                continue

            entities[measurement_key] = MeasurementSensor(
                coordinator, station, measurement_code, spec
            )
    return entities
