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
    return SelectedMetric("STA1", component, value, unit, measurement_type)


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
                station_codes=(station.code,),
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


def _expected_unique_id(component: str) -> str:
    return f"wiener_luft_sta1_{component.lower()}"


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
        self.assertEqual(
            "sensor.wiener_luft_wind_direction_station_1", sensor.entity_id
        )
        self.assertEqual(_expected_unique_id("WR"), sensor._attr_unique_id)
        self.assertEqual(
            MEASUREMENT_SPECS["WR"].translation_key, sensor._attr_translation_key
        )
        self.assertTrue(sensor.available)
        self.assertEqual(180.0, sensor.native_value)
        self.assertEqual("°", sensor.native_unit_of_measurement)
        self.assertEqual(
            {
                "station_code": "STA1",
                "station_name": "Station 1",
                "district": 1,
                "latitude": 48.2,
                "longitude": 16.3,
                "component": "WR",
                "measurement_type": "HMW",
                "station_url": "https://example.test/stations/sta1",
            },
            sensor.extra_state_attributes,
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
        self.assertEqual("sensor.wiener_luft_pm25_station_1", sensor.entity_id)
        self.assertEqual(
            MEASUREMENT_SPECS["PM25"].translation_key,
            sensor._attr_translation_key,
        )
        self.assertFalse(sensor.available)
        self.assertIsNone(sensor.native_value)
        self.assertEqual("µg/m³", sensor.native_unit_of_measurement)
        self.assertEqual(
            {
                "station_code": "STA1",
                "station_name": "Station 1",
                "district": 1,
                "latitude": 48.2,
                "longitude": 16.3,
                "component": "PM25",
                "measurement_type": None,
            },
            sensor.extra_state_attributes,
        )

    def test_entity_id_uses_english_weather_slugs_only(self) -> None:
        station = _station()
        coordinator = _coordinator({})

        cases = {
            "LTM": "sensor.wiener_luft_temperature_station_1",
            "RF": "sensor.wiener_luft_humidity_station_1",
            "WG": "sensor.wiener_luft_wind_speed_station_1",
            "WR": "sensor.wiener_luft_wind_direction_station_1",
            "PM25": "sensor.wiener_luft_pm25_station_1",
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
                station_codes=("STA1",),
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
