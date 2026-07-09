from typing import Any

from .core import HomeAssistant

type ConfigFlowResult = dict[str, Any]

class ConfigEntry:
    data: dict[str, Any]
    options: dict[str, Any]
    entry_id: str
    runtime_data: Any

    def async_on_unload(self, callback: Any) -> None: ...

class ConfigFlow:
    hass: HomeAssistant

    def __init_subclass__(cls, *, domain: str = ..., **kwargs: Any) -> None: ...
    async def async_set_unique_id(self, unique_id: str) -> None: ...
    def _abort_if_unique_id_configured(self) -> None: ...
    def async_show_form(self, **kwargs: Any) -> ConfigFlowResult: ...
    def async_create_entry(
        self,
        *,
        title: str | None = ...,
        data: Any = ...,
    ) -> ConfigFlowResult: ...
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Any = ...,
    ) -> ConfigFlowResult: ...

class OptionsFlow(ConfigFlow):
    @property
    def config_entry(self) -> ConfigEntry: ...

class OptionsFlowWithReload(OptionsFlow):
    automatic_reload: bool

class UnknownEntry(Exception): ...
