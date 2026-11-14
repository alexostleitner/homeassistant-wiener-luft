from collections.abc import Callable
from typing import Any

class HomeAssistant:
    config: Any
    states: Any
    config_entries: Any

    async def async_add_executor_job(
        self, func: Callable[..., Any], *args: Any
    ) -> Any: ...

def callback[F: Callable[..., Any]](func: F) -> F: ...
