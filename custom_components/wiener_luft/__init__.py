"""Integration setup and unload hooks."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PLATFORMS
from .coordinator import IntegrationCoordinator
from .entity_ids import sensor_entity_id, sensor_unique_id
from .measurements import MEASUREMENT_SPECS

LOGGER = logging.getLogger(__name__)
_COMPONENT_BY_SLUG = {
    component.lower().replace(".", ""): component for component in MEASUREMENT_SPECS
}

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate stored entity IDs to the shared slug format."""

    if entry.version == 1 and getattr(entry, "minor_version", 1) < 2:
        registry = er.async_get(hass)
        prefix = f"{DOMAIN}_"

        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity_entry.domain != "sensor" or not entity_entry.unique_id:
                continue

            if not entity_entry.unique_id.startswith(prefix):
                continue

            station_slug, separator, component_slug = entity_entry.unique_id[
                len(prefix) :
            ].partition("_")
            component = _COMPONENT_BY_SLUG.get(component_slug)
            if not separator or not station_slug or component is None:
                continue

            measurement_spec = MEASUREMENT_SPECS[component]
            update_kwargs: dict[str, str] = {}
            new_unique_id = sensor_unique_id(measurement_spec, station_slug.upper())
            new_entity_id = sensor_entity_id(measurement_spec, station_slug.upper())
            if entity_entry.unique_id != new_unique_id:
                update_kwargs["new_unique_id"] = new_unique_id
            if entity_entry.entity_id != new_entity_id:
                update_kwargs["new_entity_id"] = new_entity_id
            if update_kwargs:
                LOGGER.warning(
                    "Migrating entity registry entry %s: unique_id %s -> %s, entity_id %s -> %s",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                    update_kwargs.get("new_unique_id", entity_entry.unique_id),
                    entity_entry.entity_id,
                    update_kwargs.get("new_entity_id", entity_entry.entity_id),
                )
                registry.async_update_entity(entity_entry.entity_id, **update_kwargs)

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""

    coordinator = IntegrationCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration for a config entry."""

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data = None
    return unloaded
