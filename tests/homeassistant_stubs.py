"""Minimal Home Assistant stubs for unit tests."""

from __future__ import annotations

import sys
import types
from types import ModuleType
from typing import Any


def _coordinator_entity_init(self, coordinator) -> None:
    self.coordinator = coordinator
    self.hass = None
    self.entity_id = None


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


class _OptionsFlowWithReload(_OptionsFlow):
    automatic_reload = True


class _DataUpdateCoordinator:
    __class_getitem__ = classmethod(_return_cls)

    def __init__(
        self,
        hass=None,
        logger=None,
        name=None,
        update_interval=None,
        config_entry=None,
        **_kwargs,
    ) -> None:
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

    def async_update_listeners(self) -> None:
        for callback in tuple(self._listeners):
            callback()


async def _async_add_executor_job(func, *args):
    return func(*args)


class _EntityRegistryDisabler:
    INTEGRATION = "integration"


class _SelectSelector:
    def __init__(self, config):
        self.config = config


def install_homeassistant_stubs() -> None:
    module_names = (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.data_entry_flow",
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

    modules["homeassistant.const"].ATTR_LATITUDE = "latitude"
    modules["homeassistant.const"].ATTR_LONGITUDE = "longitude"
    modules["homeassistant.const"].Platform = type("Platform", (), {"SENSOR": "sensor"})

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
    modules[
        "homeassistant.config_entries"
    ].OptionsFlowWithReload = _OptionsFlowWithReload
    modules["homeassistant.config_entries"].ConfigEntry = type("ConfigEntry", (), {})
    modules["homeassistant.config_entries"].ConfigFlowResult = dict
    modules["homeassistant.config_entries"].UnknownEntry = type(
        "UnknownEntry", (Exception,), {}
    )
    modules["homeassistant.core"].HomeAssistant = type("HomeAssistant", (), {})
    modules["homeassistant.core"].callback = lambda func: func
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
    selector.SelectOptionDict = dict
    selector.SelectSelector = _SelectSelector
    selector.SelectSelectorConfig = lambda **kwargs: kwargs
    modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = type(
        "CoordinatorEntity",
        (),
        {
            "__class_getitem__": classmethod(_return_cls),
            "__init__": _coordinator_entity_init,
        },
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


def make_hass(
    *,
    language: str = "en",
    latitude: float | None = None,
    longitude: float | None = None,
    config_entries=None,
    entity_registry=None,
    states=None,
):
    hass = types.SimpleNamespace(
        async_add_executor_job=_async_add_executor_job,
        config=types.SimpleNamespace(
            language=language,
            latitude=latitude,
            longitude=longitude,
        ),
    )
    if config_entries is not None:
        hass.config_entries = config_entries
    if entity_registry is not None:
        hass.entity_registry = entity_registry
    if states is not None:
        hass.states = states
    return hass


def make_entry(
    *,
    data=None,
    options=None,
    entry_id: str = "entry-1",
    runtime_data=None,
):
    return types.SimpleNamespace(
        runtime_data=runtime_data,
        data={} if data is None else data,
        options={} if options is None else options,
        entry_id=entry_id,
        async_on_unload=lambda func: func,
    )


def make_station(
    code: str = "STA1",
    name: str = "Station 1",
    *,
    district: int | None = 1,
    latitude: float | None = 48.2,
    longitude: float | None = 16.3,
    station_url: str | None = None,
):
    from custom_components.wiener_luft.station import Station

    return Station(code, name, district, latitude, longitude, station_url)


def make_metric(
    value: float | None,
    measurement_type: str | None,
    *,
    unit: str = "μg/m³",
    measured_at=None,
):
    from custom_components.wiener_luft.measurements_parser import SelectedMetric

    return SelectedMetric(value, unit, measurement_type, measured_at)


def make_data(
    measurements,
    *,
    station=None,
    stale_measurements: tuple[tuple[str, str], ...] = (),
):
    from custom_components.wiener_luft.models import IntegrationData

    station = station or make_station()
    return IntegrationData(
        stations={station.code: station},
        measurements=measurements,
        stale_measurements=frozenset(stale_measurements),
    )


class FakeRegistry:
    def __init__(self, entries) -> None:
        self.entries = list(entries)
        self.updates: list[tuple[str, dict[str, object]]] = []

    def async_update_entity(self, entity_id, **changes):
        self.updates.append((entity_id, changes))
        for entry in self.entries:
            if entry.entity_id != entity_id:
                continue
            for key, value in changes.items():
                setattr(entry, key, value)
            return


def make_coordinator(data):
    coordinator = _DataUpdateCoordinator()
    coordinator.data = data
    return coordinator


def make_registry_entry(
    *,
    unique_id: str,
    disabled_by,
    entity_id: str,
    config_entry_id: str = "entry-1",
    domain: str = "sensor",
):
    return types.SimpleNamespace(
        domain=domain,
        unique_id=unique_id,
        disabled_by=disabled_by,
        entity_id=entity_id,
        config_entry_id=config_entry_id,
    )


def make_state(**attributes):
    return types.SimpleNamespace(attributes=attributes)
