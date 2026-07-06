"""Regression tests for sensor entity behavior."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import Mock

from homeassistant_stubs import (
    install_homeassistant_stubs,
    make_coordinator,
    make_data,
    make_hass,
    make_metric,
    make_state,
    make_station,
)

NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)

install_homeassistant_stubs()

from custom_components.wiener_luft.measurements import (  # noqa: E402
    MEASUREMENT_SPECS,
)
from custom_components.wiener_luft.sensor import (  # noqa: E402
    MeasurementSensor,
)


class MeasurementSensorTest(unittest.TestCase):
    def test_sensor_uses_measurement_metadata(self) -> None:
        station = make_station(station_url="https://example.test/stations/sta1")
        coordinator = make_coordinator(
            make_data(
                {("STA1", "WR"): make_metric(180.0, "HMW", unit="°")}, station=station
            )
        )
        sensor = MeasurementSensor(coordinator, station, "WR", MEASUREMENT_SPECS["WR"])

        self.assertEqual(
            f"wiener_luft_{MEASUREMENT_SPECS['WR'].measurement_slug}_sta1",
            sensor._attr_unique_id,
        )
        self.assertEqual(
            MEASUREMENT_SPECS["WR"].translation_key,
            sensor._attr_translation_key,
        )
        self.assertEqual(0, sensor._attr_suggested_display_precision)

    def test_sensor_exposes_current_value_and_unit(self) -> None:
        station = make_station()
        sensor = MeasurementSensor(
            make_coordinator(
                make_data(
                    {("STA1", "WR"): make_metric(180.0, "HMW", unit="°")},
                    station=station,
                )
            ),
            station,
            "WR",
            MEASUREMENT_SPECS["WR"],
        )

        self.assertTrue(sensor.available)
        self.assertEqual(180.0, sensor.native_value)
        self.assertEqual("°", sensor.native_unit_of_measurement)

    def test_sensor_exposes_station_attributes(self) -> None:
        station = make_station()
        sensor = MeasurementSensor(
            make_coordinator(
                make_data(
                    {("STA1", "WR"): make_metric(180.0, "HMW", unit="°")},
                    station=station,
                )
            ),
            station,
            "WR",
            MEASUREMENT_SPECS["WR"],
        )

        self.assertEqual(
            {
                "district": 1,
                "latitude": 48.2,
                "longitude": 16.3,
                "interval": "HMW",
            },
            sensor.extra_state_attributes,
        )

    def test_sensor_exposes_device_info_with_configuration_url(self) -> None:
        station = make_station(station_url="https://example.test/stations/sta1")
        sensor = MeasurementSensor(
            make_coordinator(
                make_data(
                    {("STA1", "WR"): make_metric(180.0, "HMW", unit="°")},
                    station=station,
                )
            ),
            station,
            "WR",
            MEASUREMENT_SPECS["WR"],
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

    def test_sensor_is_unavailable_when_coordinator_update_fails(self) -> None:
        station = make_station()
        coordinator = make_coordinator(
            make_data(
                {("STA1", "WR"): make_metric(180.0, "HMW", unit="°")},
                station=station,
            )
        )
        sensor = MeasurementSensor(coordinator, station, "WR", MEASUREMENT_SPECS["WR"])

        coordinator.last_update_success = False
        self.assertFalse(sensor.available)

    def test_sensor_is_unavailable_without_data(self) -> None:
        coordinator = make_coordinator(
            make_data({("STA1", "PM25"): make_metric(12.3, "1MW")})
        )
        sensor = MeasurementSensor(
            coordinator,
            make_station(),
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )

        coordinator.data = None

        self.assertFalse(sensor.available)
        self.assertIsNone(sensor.native_value)

    def test_sensor_keeps_metadata_when_data_disappears(self) -> None:
        coordinator = make_coordinator(
            make_data({("STA1", "PM25"): make_metric(12.3, "1MW")})
        )
        sensor = MeasurementSensor(
            coordinator,
            make_station(),
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )

        coordinator.data = None

        self.assertEqual(
            MEASUREMENT_SPECS["PM25"].translation_key,
            sensor._attr_translation_key,
        )
        self.assertEqual(1, sensor._attr_suggested_display_precision)
        self.assertEqual("μg/m³", sensor.native_unit_of_measurement)
        self.assertEqual(
            {"district": 1, "latitude": 48.2, "longitude": 16.3},
            sensor.extra_state_attributes,
        )

    def test_wind_direction_hides_calm_values(self) -> None:
        for wind_speed, expected_value in ((1.7, None), (1.8, 180.0)):
            with self.subTest(wind_speed=wind_speed):
                station = make_station()
                sensor = MeasurementSensor(
                    make_coordinator(
                        make_data(
                            {
                                ("STA1", "WR"): make_metric(180.0, "HMW", unit="°"),
                                ("STA1", "WG"): make_metric(
                                    wind_speed,
                                    "HMW",
                                    unit="km/h",
                                ),
                            },
                            station=station,
                        )
                    ),
                    station,
                    "WR",
                    MEASUREMENT_SPECS["WR"],
                )

                self.assertEqual(expected_value, sensor.native_value)

    def test_interval_change_logs_when_value_changes(self) -> None:
        sensor = MeasurementSensor(
            make_coordinator(make_data({("STA1", "PM25"): make_metric(12.3, "1MW")})),
            make_station(),
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )
        sensor.entity_id = "sensor.pm25_sta1"
        sensor.hass = make_hass(
            states={
                "sensor.pm25_sta1": make_state(
                    interval="HMW",
                    unit_of_measurement="μg/m³",
                )
            }
        )

        with self.assertLogs(
            "custom_components.wiener_luft.sensor", level="WARNING"
        ) as logs:
            sensor.async_write_ha_state()

        self.assertIn("changed from HMW to 1MW", logs.output[0])

    def test_unit_change_warns_only_for_new_unit(self) -> None:
        station = make_station()
        coordinator = make_coordinator(
            make_data({("STA1", "PM25"): make_metric(12.3, "1MW")}, station=station)
        )
        sensor = MeasurementSensor(
            coordinator,
            station,
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )
        sensor.entity_id = "sensor.test_pm25"
        sensor.hass = make_hass(
            states=Mock(get=Mock(return_value=make_state(unit_of_measurement="µg/m³")))
        )

        with self.assertNoLogs("custom_components.wiener_luft.sensor", level="WARNING"):
            sensor.async_write_ha_state()

        coordinator.data = make_data(
            {("STA1", "PM25"): make_metric(12.3, "1MW", unit="mg/m³")},
            station=station,
        )
        with self.assertLogs(
            "custom_components.wiener_luft.sensor", level="WARNING"
        ) as logs:
            sensor.async_write_ha_state()

        self.assertEqual(1, len(logs.output))
        self.assertIn("changed from μg/m³ to mg/m³", logs.output[0])

        sensor.hass.states.get.return_value = make_state(unit_of_measurement="mg/m³")
        with self.assertNoLogs("custom_components.wiener_luft.sensor", level="WARNING"):
            sensor.async_write_ha_state()

    def test_entity_ids_and_precisions_follow_measurement_specs(self) -> None:
        coordinator = make_coordinator(make_data({}))
        station = make_station()

        for component, expected_precision in {
            "LTM": 1,
            "RF": 0,
            "WG": 1,
            "WR": 0,
            "PM25": 1,
            "CO": 2,
        }.items():
            with self.subTest(component=component):
                sensor = MeasurementSensor(
                    coordinator,
                    station,
                    component,
                    MEASUREMENT_SPECS[component],
                )
                self.assertEqual(
                    f"wiener_luft_{MEASUREMENT_SPECS[component].measurement_slug}_sta1",
                    sensor._attr_unique_id,
                )
                self.assertEqual(
                    MEASUREMENT_SPECS[component].translation_key,
                    sensor._attr_translation_key,
                )
                self.assertEqual(
                    expected_precision,
                    sensor._attr_suggested_display_precision,
                )

    def test_sensor_availability_tracks_stale_measurements(self) -> None:
        station = make_station()
        coordinator = make_coordinator(
            make_data(
                {("STA1", "PM25"): make_metric(12.3, "1MW", measured_at=NOW)},
                station=station,
            )
        )
        sensor = MeasurementSensor(
            coordinator,
            station,
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )
        self.assertTrue(sensor.available)

        coordinator.data = make_data(
            {("STA1", "PM25"): make_metric(12.3, "1MW", measured_at=NOW)},
            station=station,
            stale_measurements=(("STA1", "PM25"),),
        )
        self.assertFalse(sensor.available)

        coordinator.data = make_data(
            {("STA1", "PM25"): make_metric(13.4, "1MW", measured_at=NOW)},
            station=station,
        )
        self.assertTrue(sensor.available)

    def test_wind_direction_uses_latest_wind_speed(self) -> None:
        station = make_station()
        coordinator = make_coordinator(
            make_data(
                {
                    ("STA1", "WR"): make_metric(
                        180.0,
                        "HMW",
                        unit="°",
                        measured_at=NOW,
                    ),
                    ("STA1", "WG"): make_metric(
                        5.0,
                        "HMW",
                        unit="km/h",
                        measured_at=NOW,
                    ),
                },
                station=station,
            )
        )
        sensor = MeasurementSensor(coordinator, station, "WR", MEASUREMENT_SPECS["WR"])

        coordinator.data = make_data(
            {
                ("STA1", "WR"): make_metric(
                    180.0,
                    "HMW",
                    unit="°",
                    measured_at=NOW,
                ),
                ("STA1", "WG"): make_metric(
                    1.7,
                    "HMW",
                    unit="km/h",
                    measured_at=NOW,
                ),
            },
            station=station,
        )

        self.assertIsNone(sensor.native_value)

    def test_wind_speed_is_calm_checks_only_supported_units(self) -> None:
        station = make_station()
        coordinator = make_coordinator(
            make_data(
                {
                    ("STA1", "WR"): make_metric(180.0, "HMW", unit="°"),
                    ("STA1", "WG"): make_metric(0.4, "HMW", unit="m/s"),
                },
                station=station,
            )
        )
        sensor = MeasurementSensor(coordinator, station, "WR", MEASUREMENT_SPECS["WR"])
        self.assertTrue(sensor._wind_speed_is_calm)

        coordinator.data = make_data(
            {
                ("STA1", "WR"): make_metric(180.0, "HMW", unit="°"),
                ("STA1", "WG"): make_metric(1.7, "HMW", unit="mph"),
            },
            station=station,
        )
        self.assertFalse(sensor._wind_speed_is_calm)

    def test_extra_state_attributes_skip_interval_without_measurement_type(
        self,
    ) -> None:
        sensor = MeasurementSensor(
            make_coordinator(make_data({("STA1", "PM25"): make_metric(12.3, None)})),
            make_station(),
            "PM25",
            MEASUREMENT_SPECS["PM25"],
        )
        self.assertNotIn("interval", sensor.extra_state_attributes)

    def test_log_change_skips_missing_context(self) -> None:
        for method_name in ("_log_unit_change", "_log_interval_change"):
            with self.subTest(method_name=method_name):
                sensor = MeasurementSensor(
                    make_coordinator(
                        make_data({("STA1", "PM25"): make_metric(12.3, "1MW")})
                    ),
                    make_station(),
                    "PM25",
                    MEASUREMENT_SPECS["PM25"],
                )
                log_change = getattr(sensor, method_name)

                with self.assertNoLogs(
                    "custom_components.wiener_luft.sensor", level="WARNING"
                ):
                    log_change()

                sensor.hass = make_hass(states=Mock(get=Mock(return_value=None)))
                sensor.entity_id = "sensor.pm25_sta1"
                with self.assertNoLogs(
                    "custom_components.wiener_luft.sensor", level="WARNING"
                ):
                    log_change()
