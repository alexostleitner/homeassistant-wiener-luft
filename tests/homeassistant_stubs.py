"""Minimal Home Assistant stubs for unit tests."""

from __future__ import annotations

import sys
from types import ModuleType


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
        "homeassistant.helpers.entity_platform",
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
    modules["homeassistant.config_entries"].ConfigEntry = type("ConfigEntry", (), {})
    modules["homeassistant.core"].HomeAssistant = type("HomeAssistant", (), {})
    modules["homeassistant.helpers.device_registry"].DeviceInfo = type(
        "DeviceInfo", (dict,), {}
    )
    modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = type(
        "AddEntitiesCallback", (), {}
    )
    modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = type(
        "CoordinatorEntity",
        (),
        {"__init__": _coordinator_entity_init},
    )
    modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = (
        _constants("DataUpdateCoordinator")
    )
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = type(
        "UpdateFailed", (Exception,), {}
    )
    modules["homeassistant.util.dt"].utcnow = lambda: None
    modules["homeassistant.util"].slugify = (
        lambda value: value.lower().replace(" ", "_")
    )
