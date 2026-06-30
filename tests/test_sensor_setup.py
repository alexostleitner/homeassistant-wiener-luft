"""Regression tests for sensor entity setup."""

from __future__ import annotations

import asyncio
import types
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft import sensor as sensor_module  # noqa: E402
from custom_components.wiener_luft.coordinator import (  # noqa: E402
    IntegrationData,
)
from custom_components.wiener_luft.measurements import (  # noqa: E402
    MEASUREMENT_SPECS,
)
from custom_components.wiener_luft.measurements_parser import (  # noqa: E402
    SelectedMetric,
)
from custom_components.wiener_luft.sensor import (  # noqa: E402
    MeasurementSensor,
    async_setup_entry,
)
from custom_components.wiener_luft.station import Station  # noqa: E402

NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


def _station(*, station_url: str | None = None) -> Station:
    return Station("STA1", "Station 1", 1, 48.2, 16.3, station_url)


def _metric(
    component: str,
    value: float | None,
    measurement_type: str | None,
    *,
    unit: str = "μg/m³",
    measured_at: datetime | None = None,
) -> SelectedMetric:
    return SelectedMetric(value, unit, measurement_type, measured_at)


def _coordinator(
    selected: dict[tuple[str, str], SelectedMetric],
    *,
    station: Station | None = None,
):
    station = station or _station()
    coordinator = types.SimpleNamespace(
        data=IntegrationData(
            stations={station.code: station},
            measurements=selected,
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
        self.assertEqual(_expected_entity_base("WR"), sensor._attr_unique_id)
        self.assertEqual(
            MEASUREMENT_SPECS["WR"].translation_key, sensor._attr_translation_key
        )
        self.assertEqual(0, sensor._attr_suggested_display_precision)
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
        self.assertEqual(
            MEASUREMENT_SPECS["PM25"].translation_key,
            sensor._attr_translation_key,
        )
        self.assertEqual(1, sensor._attr_suggested_display_precision)
        self.assertFalse(sensor.available)
        self.assertIsNone(sensor.native_value)
        self.assertEqual("μg/m³", sensor.native_unit_of_measurement)
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

    def test_wind_direction_calm_threshold(self) -> None:
        station = _station()
        cases = (
            (1.7, None),
            (1.8, 180.0),
        )

        for wind_speed, expected_value in cases:
            with self.subTest(wind_speed=wind_speed):
                sensor = MeasurementSensor(
                    _coordinator(
                        {
                            ("STA1", "WR"): _metric("WR", 180.0, "HMW", unit="°"),
                            ("STA1", "WG"): _metric(
                                "WG", wind_speed, "HMW", unit="km/h"
                            ),
                        },
                        station=station,
                    ),
                    station,
                    "WR",
                    MEASUREMENT_SPECS["WR"],
                )

                self.assertTrue(sensor.available)
                self.assertEqual(expected_value, sensor.native_value)

    def test_unit_change_warns_once_per_new_state(self) -> None:
        station = _station()
        coordinator = _coordinator(
            {("STA1", "PM25"): _metric("PM25", 12.3, "1MW", unit="μg/m³")},
            station=station,
        )
        sensor = MeasurementSensor(
            coordinator,
            station,
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )
        sensor.entity_id = "sensor.test_pm25"
        sensor.hass = types.SimpleNamespace(
            states=Mock(
                get=Mock(
                    return_value=types.SimpleNamespace(
                        attributes={"unit_of_measurement": "µg/m³"}
                    )
                )
            )
        )
        with self.assertNoLogs(
            "custom_components.wiener_luft.sensor", level="WARNING"
        ):
            sensor.async_write_ha_state()

        sensor.coordinator.data = IntegrationData(
            stations={"STA1": station},
            measurements={
                ("STA1", "PM25"): _metric("PM25", 12.3, "1MW", unit="mg/m³"),
            },
        )
        with self.assertLogs(
            "custom_components.wiener_luft.sensor", level="WARNING"
        ) as logs:
            sensor.async_write_ha_state()
        self.assertEqual(1, len(logs.output))
        self.assertIn("changed from μg/m³ to mg/m³", logs.output[0])

        sensor.hass.states.get.return_value = types.SimpleNamespace(
            attributes={"unit_of_measurement": "mg/m³"}
        )
        with self.assertNoLogs(
            "custom_components.wiener_luft.sensor", level="WARNING"
        ):
            sensor.async_write_ha_state()

    def test_entity_identifiers_share_slug_logic(self) -> None:
        station = _station()
        coordinator = _coordinator({})

        cases = {
            "LTM": 1,
            "RF": 0,
            "WG": 1,
            "WR": 0,
            "PM25": 1,
            "CO": 2,
        }

        for component, expected_precision in cases.items():
            with self.subTest(component=component):
                sensor = MeasurementSensor(
                    coordinator,
                    station,
                    component,
                    MEASUREMENT_SPECS[component],
                )
                self.assertEqual(
                    _expected_entity_base(component), sensor._attr_unique_id
                )
                self.assertEqual(
                    MEASUREMENT_SPECS[component].translation_key,
                    sensor._attr_translation_key,
                )
                self.assertEqual(
                    expected_precision,
                    sensor._attr_suggested_display_precision,
                )

    def test_handle_coordinator_update_skips_unchanged_fresh_measurement(self) -> None:
        cases = (
            {
                "name": "fresh measurement is skipped",
                "initial_measured_at": NOW - timedelta(minutes=30),
                "update_now": NOW,
                "next_metric": None,
                "expected_writes": 0,
                "expected_available": True,
                "final_now": NOW,
            },
            {
                "name": "stale measurement writes once",
                "initial_measured_at": NOW - timedelta(minutes=30),
                "update_now": NOW + timedelta(hours=3),
                "next_metric": None,
                "repeat_update": True,
                "expected_writes": 1,
                "expected_available": False,
                "final_now": NOW + timedelta(hours=3),
            },
            {
                "name": "new measurement recovers availability",
                "initial_measured_at": NOW - timedelta(hours=3),
                "update_now": NOW,
                "next_metric": _metric(
                    "PM25",
                    13.4,
                    "1MW",
                    measured_at=NOW - timedelta(minutes=10),
                ),
                "next_now": NOW,
                "expected_writes": 1,
                "expected_available": True,
                "final_now": NOW,
            },
        )

        for case in cases:
            with self.subTest(case=case["name"]):
                station = _station()
                coordinator = _coordinator(
                    {
                        ("STA1", "PM25"): _metric(
                            "PM25",
                            12.3,
                            "1MW",
                            measured_at=case["initial_measured_at"],
                        )
                    },
                    station=station,
                )
                with patch.object(sensor_module.dt_util, "utcnow", return_value=NOW):
                    sensor = MeasurementSensor(
                        coordinator,
                        station,
                        "PM25",
                        MEASUREMENT_SPECS["PM25"],
                    )
                sensor.async_write_ha_state = Mock()

                with patch.object(
                    sensor_module.dt_util,
                    "utcnow",
                    return_value=case["update_now"],
                ):
                    sensor._handle_coordinator_update()
                    if case.get("repeat_update"):
                        sensor._handle_coordinator_update()

                next_metric = case["next_metric"]
                if next_metric is not None:
                    coordinator.data = IntegrationData(
                        stations={"STA1": station},
                        measurements={("STA1", "PM25"): next_metric},
                    )
                    with patch.object(
                        sensor_module.dt_util,
                        "utcnow",
                        return_value=case["next_now"],
                    ):
                        sensor._handle_coordinator_update()

                self.assertEqual(
                    case["expected_writes"],
                    sensor.async_write_ha_state.call_count,
                )
                with patch.object(
                    sensor_module.dt_util,
                    "utcnow",
                    return_value=case["final_now"],
                ):
                    self.assertEqual(case["expected_available"], sensor.available)

    def test_wind_direction_update_writes_when_wind_becomes_calm(self) -> None:
        station = _station()
        measured_at = NOW - timedelta(minutes=10)
        coordinator = _coordinator(
            {
                ("STA1", "WR"): _metric(
                    "WR", 180.0, "HMW", unit="°", measured_at=measured_at
                ),
                ("STA1", "WG"): _metric(
                    "WG", 5.0, "HMW", unit="km/h", measured_at=measured_at
                ),
            },
            station=station,
        )
        with patch.object(sensor_module.dt_util, "utcnow", return_value=NOW):
            sensor = MeasurementSensor(
                coordinator,
                station,
                "WR",
                MEASUREMENT_SPECS["WR"],
            )

        sensor.async_write_ha_state = Mock()
        coordinator.data = IntegrationData(
            stations={"STA1": station},
            measurements={
                ("STA1", "WR"): _metric(
                    "WR", 180.0, "HMW", unit="°", measured_at=measured_at
                ),
                ("STA1", "WG"): _metric(
                    "WG", 1.7, "HMW", unit="km/h", measured_at=measured_at
                ),
            },
        )

        with patch.object(sensor_module.dt_util, "utcnow", return_value=NOW):
            sensor._handle_coordinator_update()

        self.assertEqual(1, sensor.async_write_ha_state.call_count)
        self.assertIsNone(sensor.native_value)


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
            [entity._component for entity in batches[0]],
        )

        coordinator.data = IntegrationData(
            stations={"STA1": _station()},
            measurements={
                ("STA1", "PM25"): _metric("PM25", 12.3, "1MW"),
                ("STA1", "NO2"): _metric("NO2", 8.0, "HMW"),
            },
        )
        coordinator.async_update_listeners()
        coordinator.async_update_listeners()

        self.assertEqual(2, len(batches))
        self.assertEqual(["NO2"], [entity._component for entity in batches[1]])

    def test_setup_skips_unknown_measurements(self) -> None:
        coordinator = _coordinator(
            {
                ("STA1", "PM25"): _metric("PM25", 12.3, "1MW"),
                ("STA1", "ZZ"): _metric("ZZ", 5.0, "1MW"),
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
        self.assertEqual(1, len(batches))
        self.assertEqual(["PM25"], [entity._component for entity in batches[0]])
