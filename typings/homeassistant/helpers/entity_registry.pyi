from typing import Any

class RegistryEntryDisabler:
    INTEGRATION: str

class RegistryEntry:
    domain: str
    unique_id: str
    entity_id: str
    config_entry_id: str
    disabled_by: str | None

class EntityRegistry:
    entries: list[RegistryEntry]

    def async_update_entity(self, entity_id: str, **changes: Any) -> None: ...

def async_get(hass: Any) -> EntityRegistry: ...
def async_entries_for_config_entry(
    registry: EntityRegistry, config_entry_id: str
) -> list[RegistryEntry]: ...
