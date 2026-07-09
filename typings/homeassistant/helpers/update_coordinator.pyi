from collections.abc import Callable
from typing import Any

class UpdateFailed(Exception): ...

class DataUpdateCoordinator[T]:
    hass: Any
    logger: Any
    name: Any
    update_interval: Any
    config_entry: Any
    last_update_success: bool
    data: T | None

    def __init__(
        self,
        hass: Any = ...,
        logger: Any = ...,
        name: Any = ...,
        update_interval: Any = ...,
        config_entry: Any = ...,
        **kwargs: Any,
    ) -> None: ...
    def async_add_listener(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]: ...
    def async_update_listeners(self) -> None: ...
    async def async_config_entry_first_refresh(self) -> None: ...

class CoordinatorEntity[T]:
    coordinator: T
    hass: Any
    entity_id: str | None

    def __init__(self, coordinator: T) -> None: ...
