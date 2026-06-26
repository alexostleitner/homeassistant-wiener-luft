"""Regression tests for sensor entity setup."""

from __future__ import annotations

import asyncio
import types
import unittest

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft.client import (  # noqa: E402
    LumesMeasurements,
    SelectedMetric,
    Station,
)
from custom_components.wiener_luft.coordinator import (  # noqa: E402
    IntegrationData,
)
from custom_components.wiener_luft.measurements import (  # noqa: E402
    MEASUREMENT_SPECS,
)
from custom_components.wiener_luft.sensor import (  # noqa: E402
    MeasurementSensor,
    async_setup_entry,
)


def _station(*, station_url: str | None = None) -> Station:
    return Station("STA1", "Station 1", 1, 48.2, 16.3, station_url)


def _metric(
    component: str,
    value: float | None,
    measurement_type: str | None,
    *,
    unit: str = "µg/m³",
) -> SelectedMetric:
    return SelectedMetric(value, unit, measurement_type)


def _coordinator(
    selected: dict[tuple[str, str], SelectedMetric],
    *,
    station: Station | None = None,
):
    station = station or _station()
    coordinator = types.SimpleNamespace(
        data=IntegrationData(
            stations={station.code: station},
            measurements=LumesMeasurements(
                selected=selected,
            ),
        ),
        last_update_success=True,
        _listeners=[],
    )

    def async_add_listener(callback):
        coordinator._listeners.append(callback)
        return lambda: coordinator._listeners.remove(callback)

    coordinator.async_add_listener = async_add_listener
    def async_update_listeners() -> None:
        for callback in tuple(coordinator._listeners):
            callback()

    coordinator.async_update_listeners = async_update_listeners
    return coordinator


def _expected_entity_base(component: str, station_code: str = "STA1") -> str:
    measurement_spec = MEASUREMENT_SPECS[component]
    return f"wiener_luft_{measurement_spec.measurement_slug}_{station_code.lower()}"


def _expected_unique_id(component: str) -> str:
    return _expected_entity_base(component)


def _expected_entity_id(component: str) -> str:
    return f"sensor.{_expected_entity_base(component)}"


class MeasurementSensorTest(unittest.TestCase):
    def test_sensor_state(self) -> None:
        station = _station(station_url="https://example.test/stations/sta1")
        coordinator = _coordinator(
            {("STA1", "WR"): _metric("WR", 180.0, "HMW", unit="°")},
            station=station,
        )
        sensor = MeasurementSensor(
            coordinator,
            station,
            "WR",
            MEASUREMENT_SPECS["WR"],
        )
        self.assertEqual(_expected_entity_id("WR"), sensor.entity_id)
        self.assertEqual(_expected_unique_id("WR"), sensor._attr_unique_id)
        self.assertEqual(
            sensor._attr_unique_id, sensor.entity_id.removeprefix("sensor.")
        )
        self.assertEqual(
            MEASUREMENT_SPECS["WR"].translation_key, sensor._attr_translation_key
        )
        self.assertTrue(sensor.available)
        self.assertEqual(180.0, sensor.native_value)
        self.assertEqual("°", sensor.native_unit_of_measurement)
        self.assertEqual(
            {
                "district": 1,
                "latitude": 48.2,
                "longitude": 16.3,
            },
            sensor.extra_state_attributes,
        )
        self.assertEqual(
            {
                "identifiers": {("wiener_luft", "STA1")},
                "name": "Station 1",
                "manufacturer": "Wiener Luft",
                "configuration_url": "https://example.test/stations/sta1",
            },
            sensor._attr_device_info,
        )
        coordinator.last_update_success = False
        self.assertFalse(sensor.available)

        sensor = MeasurementSensor(
            _coordinator({("STA1", "PM25"): _metric("PM25", 12.3, "1MW")}),
            _station(),
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )
        sensor.coordinator.data = None
        self.assertEqual(_expected_entity_id("PM25"), sensor.entity_id)
        self.assertEqual(
            MEASUREMENT_SPECS["PM25"].translation_key,
            sensor._attr_translation_key,
        )
        self.assertFalse(sensor.available)
        self.assertIsNone(sensor.native_value)
        self.assertEqual("µg/m³", sensor.native_unit_of_measurement)
        self.assertEqual(
            {
                "district": 1,
                "latitude": 48.2,
                "longitude": 16.3,
            },
            sensor.extra_state_attributes,
        )
        self.assertEqual(
            {
                "identifiers": {("wiener_luft", "STA1")},
                "name": "Station 1",
                "manufacturer": "Wiener Luft",
            },
            sensor._attr_device_info,
        )

    def test_entity_identifiers_share_slug_logic(self) -> None:
        station = _station()
        coordinator = _coordinator({})

        cases = {
            "LTM": "sensor.wiener_luft_temperature_sta1",
            "RF": "sensor.wiener_luft_humidity_sta1",
            "WG": "sensor.wiener_luft_wind_speed_sta1",
            "WR": "sensor.wiener_luft_wind_direction_sta1",
            "PM25": "sensor.wiener_luft_pm25_sta1",
        }

        for component, expected_entity_id in cases.items():
            with self.subTest(component=component):
                sensor = MeasurementSensor(
                    coordinator,
                    station,
                    component,
                    MEASUREMENT_SPECS[component],
                )
                self.assertEqual(expected_entity_id, sensor.entity_id)
                self.assertEqual(_expected_unique_id(component), sensor._attr_unique_id)
                self.assertEqual(
                    sensor._attr_unique_id, sensor.entity_id.removeprefix("sensor.")
                )
                self.assertEqual(
                    MEASUREMENT_SPECS[component].translation_key,
                    sensor._attr_translation_key,
                )


class SensorSetupTest(unittest.TestCase):
    def test_setup_adds_entities_once(self) -> None:
        coordinator = _coordinator(
            {
                ("STA1", "PM25"): _metric("PM25", 12.3, "1MW"),
                ("STA1", "NO2"): _metric("NO2", None, None),
                ("STA1", "O3"): _metric("O3", 1.0, "HMW"),
                ("STA1", "NOX"): _metric("NOX", 2.0, "HMW"),
                ("STA1", "WR"): _metric("WR", 180.0, "HMW", unit="°"),
            }
        )
        batches: list[list[object]] = []
        asyncio.run(
            async_setup_entry(
                types.SimpleNamespace(),
                types.SimpleNamespace(
                    runtime_data=coordinator,
                    async_on_unload=lambda func: func,
                ),
                lambda entities: batches.append(list(entities)),
            )
        )
        self.assertEqual(
            ["PM25", "O3", "NOX", "WR"],
            [entity.component for entity in batches[0]],
        )

        coordinator.data = IntegrationData(
            stations={"STA1": _station()},
            measurements=LumesMeasurements(
                selected={
                    ("STA1", "PM25"): _metric("PM25", 12.3, "1MW"),
                    ("STA1", "NO2"): _metric("NO2", 8.0, "HMW"),
                },
            ),
        )
        coordinator.async_update_listeners()
        coordinator.async_update_listeners()

        self.assertEqual(2, len(batches))
        self.assertEqual(["NO2"], [entity.component for entity in batches[1]])
