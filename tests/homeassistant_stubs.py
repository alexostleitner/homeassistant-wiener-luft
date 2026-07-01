"""Minimal Home Assistant stubs for unit tests."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any


def _coordinator_entity_init(self, coordinator) -> None:
    self.coordinator = coordinator


def _return_cls(cls, _item):
    return cls


def _constants(name: str, **attrs):
    attrs["__class_getitem__"] = classmethod(_return_cls)
    return type(name, (), attrs)


class _ConfigFlow:
    def __init_subclass__(cls, **_kwargs) -> None:
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        return None

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, *, title: str | None = None, data: Any = None):
        return {"type": "create_entry", "title": title, "data": data}

    def async_abort(self, *, reason: str, description_placeholders: Any = None):
        return {
            "type": "abort",
            "reason": reason,
            "description_placeholders": description_placeholders,
        }


class _OptionsFlow(_ConfigFlow):
    def __init__(self) -> None:
        self._config_entry = None

    @property
    def config_entry(self):
        return self._config_entry


class _DataUpdateCoordinator:
    __class_getitem__ = classmethod(_return_cls)

    def __init__(
        self,
        hass=None,
        logger=None,
        name=None,
        update_interval=None,
        config_entry=None,
    ):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.config_entry = config_entry
        self.last_update_success = True
        self.data = None
        self._listeners = []

    def async_add_listener(self, callback):
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)


class _SelectSelector:
    def __init__(self, config):
        self.config = config


class _EntityRegistryDisabler:
    INTEGRATION = "integration"


def install_homeassistant_stubs() -> None:
    module_names = (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.helpers",
        "homeassistant.helpers.device_registry",
        "homeassistant.helpers.entity_registry",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.selector",
        "homeassistant.helpers.update_coordinator",
        "homeassistant.util",
        "homeassistant.util.dt",
    )
    modules = {}
    for name in module_names:
        modules[name] = sys.modules.setdefault(name, ModuleType(name))
        if "." in name:
            parent, attr = name.rsplit(".", 1)
            setattr(modules[parent], attr, modules[name])

    for name in ("homeassistant", "homeassistant.components", "homeassistant.helpers"):
        modules[name].__path__ = []  # type: ignore[attr-defined]

    const = modules["homeassistant.const"]
    const.ATTR_LATITUDE = "latitude"
    const.ATTR_LONGITUDE = "longitude"
    const.Platform = type("Platform", (), {"SENSOR": "sensor"})

    def _sensor_entity_async_write_ha_state(self) -> None:
        return None

    sensor = modules["homeassistant.components.sensor"]
    sensor.SensorEntity = type(
        "SensorEntity",
        (),
        {"async_write_ha_state": _sensor_entity_async_write_ha_state},
    )
    sensor.SensorDeviceClass = _constants(
        "SensorDeviceClass",
        PM25="pm25",
        PM10="pm10",
        NITROGEN_DIOXIDE="nitrogen_dioxide",
        OZONE="ozone",
        SULPHUR_DIOXIDE="sulphur_dioxide",
        CO="carbon_monoxide",
        TEMPERATURE="temperature",
        HUMIDITY="humidity",
        WIND_SPEED="wind_speed",
        WIND_DIRECTION="wind_direction",
    )
    sensor.SensorStateClass = _constants(
        "SensorStateClass",
        MEASUREMENT="measurement",
        MEASUREMENT_ANGLE="measurement_angle",
    )

    modules["homeassistant.config_entries"].ConfigFlow = _ConfigFlow
    modules["homeassistant.config_entries"].OptionsFlow = _OptionsFlow
    modules["homeassistant.config_entries"].OptionsFlowWithReload = _OptionsFlow
    modules["homeassistant.config_entries"].ConfigEntry = type("ConfigEntry", (), {})
    modules["homeassistant.config_entries"].UnknownEntry = type(
        "UnknownEntry", (Exception,), {}
    )
    modules["homeassistant.core"].HomeAssistant = type("HomeAssistant", (), {})
    modules["homeassistant.helpers.device_registry"].DeviceInfo = type(
        "DeviceInfo", (dict,), {}
    )
    entity_registry = modules["homeassistant.helpers.entity_registry"]
    entity_registry.RegistryEntryDisabler = _EntityRegistryDisabler
    entity_registry.async_get = lambda hass: hass.entity_registry
    entity_registry.async_entries_for_config_entry = lambda registry, config_entry_id: [
        entry for entry in registry.entries if entry.config_entry_id == config_entry_id
    ]
    modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = type(
        "AddEntitiesCallback", (), {}
    )
    selector = modules["homeassistant.helpers.selector"]
    selector.SelectSelector = _SelectSelector
    selector.SelectSelectorConfig = lambda **kwargs: kwargs
    modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = type(
        "CoordinatorEntity",
        (),
        {"__init__": _coordinator_entity_init},
    )
    modules[
        "homeassistant.helpers.update_coordinator"
    ].DataUpdateCoordinator = _DataUpdateCoordinator
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = type(
        "UpdateFailed", (Exception,), {}
    )
    modules["homeassistant.util.dt"].utcnow = lambda: None
    modules["homeassistant.util"].slugify = lambda value: value.lower().replace(
        " ", "_"
    )
