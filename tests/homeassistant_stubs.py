"""Minimal Home Assistant stubs for unit tests."""

from __future__ import annotations

import sys
import types


def _coordinator_entity_init(self, coordinator) -> None:
    self.coordinator = coordinator


def install_homeassistant_stubs() -> None:
    names = (
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
    modules = {
        name: sys.modules.setdefault(name, types.ModuleType(name))
        for name in names
    }
    homeassistant = modules["homeassistant"]
    components = modules["homeassistant.components"]
    sensor = modules["homeassistant.components.sensor"]
    config_entries = modules["homeassistant.config_entries"]
    const = modules["homeassistant.const"]
    core = modules["homeassistant.core"]
    helpers = modules["homeassistant.helpers"]
    device_registry = modules["homeassistant.helpers.device_registry"]
    entity_platform = modules["homeassistant.helpers.entity_platform"]
    update_coordinator = modules["homeassistant.helpers.update_coordinator"]
    util = modules["homeassistant.util"]
    util_dt = modules["homeassistant.util.dt"]

    for module, attr, child in (
        (homeassistant, "components", components),
        (homeassistant, "config_entries", config_entries),
        (homeassistant, "const", const),
        (homeassistant, "core", core),
        (homeassistant, "helpers", helpers),
        (homeassistant, "util", util),
        (components, "sensor", sensor),
        (helpers, "device_registry", device_registry),
        (helpers, "entity_platform", entity_platform),
        (helpers, "update_coordinator", update_coordinator),
        (util, "dt", util_dt),
    ):
        setattr(module, attr, child)

    for module in (homeassistant, components, helpers):
        module.__path__ = []  # type: ignore[attr-defined]

    const.ATTR_LATITUDE = "latitude"
    const.ATTR_LONGITUDE = "longitude"
    const.Platform = type("Platform", (), {"SENSOR": "sensor"})
    sensor.SensorEntity = type("SensorEntity", (), {})
    sensor.SensorDeviceClass = type(
        "SensorDeviceClass",
        (),
        {
            "PM25": "pm25",
            "PM10": "pm10",
            "NITROGEN_DIOXIDE": "nitrogen_dioxide",
            "OZONE": "ozone",
            "SULPHUR_DIOXIDE": "sulphur_dioxide",
            "CO": "carbon_monoxide",
            "TEMPERATURE": "temperature",
            "HUMIDITY": "humidity",
            "WIND_SPEED": "wind_speed",
            "WIND_DIRECTION": "wind_direction",
            "__class_getitem__": classmethod(lambda cls, item: cls),
        },
    )
    sensor.SensorStateClass = type(
        "SensorStateClass",
        (),
        {
            "MEASUREMENT": "measurement",
            "MEASUREMENT_ANGLE": "measurement_angle",
            "__class_getitem__": classmethod(lambda cls, item: cls),
        },
    )
    config_entries.ConfigFlow = type("ConfigFlow", (), {})
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    core.HomeAssistant = type("HomeAssistant", (), {})
    device_registry.DeviceInfo = type("DeviceInfo", (dict,), {})
    entity_platform.AddEntitiesCallback = type("AddEntitiesCallback", (), {})
    update_coordinator.CoordinatorEntity = type(
        "CoordinatorEntity",
        (),
        {"__init__": _coordinator_entity_init},
    )
    update_coordinator.DataUpdateCoordinator = type(
        "DataUpdateCoordinator",
        (),
        {"__class_getitem__": classmethod(lambda cls, item: cls)},
    )
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})
    util_dt.utcnow = lambda: None
    util.slugify = lambda value: value.lower().replace(" ", "_")
