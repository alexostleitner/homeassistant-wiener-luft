"""Regression tests for sensor entity setup."""

from __future__ import annotations

import asyncio
import unittest

from homeassistant_stubs import (
    FakeRegistry,
    install_homeassistant_stubs,
    make_coordinator,
    make_data,
    make_entry,
    make_hass,
    make_metric,
    make_registry_entry,
    make_station,
)

install_homeassistant_stubs()

from custom_components.wiener_luft.models import IntegrationData  # noqa: E402
from custom_components.wiener_luft.sensor import async_setup_entry  # noqa: E402
from custom_components.wiener_luft.sensor_entity import (  # noqa: E402
    MeasurementSensor,
    build_sensor_unique_id,
)
from custom_components.wiener_luft.sensor_setup import (  # noqa: E402
    _build_entities_by_measurement_key,
)


class SensorSetupTest(unittest.TestCase):
    def test_build_entities_returns_empty_without_data(self) -> None:
        self.assertEqual(
            {},
            _build_entities_by_measurement_key(make_coordinator(None), None, None),
        )

    def test_build_entities_filters_selection(self) -> None:
        coordinator = make_coordinator(
            IntegrationData(
                stations={
                    "STA1": make_station(),
                    "STA2": make_station(
                        "STA2",
                        "Station 2",
                        district=2,
                        latitude=48.3,
                        longitude=16.4,
                    ),
                },
                measurements={
                    ("STA1", "PM25"): make_metric(12.3, "1MW"),
                    ("STA2", "PM25"): make_metric(13.4, "1MW"),
                    ("STA2", "O3"): make_metric(9.1, "HMW"),
                },
            )
        )

        entities_by_measurement_key = _build_entities_by_measurement_key(
            coordinator,
            {"STA2"},
            {"PM25", "ZZ"},
        )
        self.assertEqual(
            {("STA2", "PM25")},
            set(entities_by_measurement_key),
        )

    def test_setup_adds_new_entities_once(self) -> None:
        coordinator = make_coordinator(
            make_data(
                {
                    ("STA1", "PM25"): make_metric(12.3, "1MW"),
                    ("STA1", "NO2"): make_metric(None, None),
                    ("STA1", "O3"): make_metric(1.0, "HMW"),
                    ("STA1", "NOX"): make_metric(2.0, "HMW"),
                    ("STA1", "WR"): make_metric(180.0, "HMW", unit="°"),
                }
            )
        )
        registry = FakeRegistry(())
        batches: list[list[MeasurementSensor]] = []

        asyncio.run(
            async_setup_entry(
                make_hass(entity_registry=registry),
                make_entry(runtime_data=coordinator),
                lambda entities: batches.append(list(entities)),
            )
        )

        self.assertEqual(
            ["PM25", "O3", "NOX", "WR"],
            [entity._measurement_code for entity in batches[0]],
        )

        coordinator.data = make_data(
            {
                ("STA1", "PM25"): make_metric(12.3, "1MW"),
                ("STA1", "NO2"): make_metric(8.0, "HMW"),
            }
        )
        coordinator.async_update_listeners()
        coordinator.async_update_listeners()

        self.assertEqual(2, len(batches))
        self.assertEqual(["NO2"], [entity._measurement_code for entity in batches[1]])

    def test_setup_skips_unknown_measurements(self) -> None:
        coordinator = make_coordinator(
            make_data(
                {
                    ("STA1", "PM25"): make_metric(12.3, "1MW"),
                    ("STA1", "ZZ"): make_metric(5.0, "1MW"),
                }
            )
        )
        batches: list[list[MeasurementSensor]] = []

        asyncio.run(
            async_setup_entry(
                make_hass(entity_registry=FakeRegistry(())),
                make_entry(runtime_data=coordinator),
                lambda entities: batches.append(list(entities)),
            )
        )

        self.assertEqual(["PM25"], [entity._measurement_code for entity in batches[0]])

    def test_setup_filters_entities_by_explicit_selection(self) -> None:
        coordinator = make_coordinator(
            make_data(
                {
                    ("STA1", "PM25"): make_metric(12.3, "1MW"),
                    ("STA1", "O3"): make_metric(1.0, "HMW"),
                    ("STA1", "WR"): make_metric(180.0, "HMW", unit="°"),
                }
            )
        )
        batches: list[list[MeasurementSensor]] = []

        asyncio.run(
            async_setup_entry(
                make_hass(entity_registry=FakeRegistry(())),
                make_entry(
                    runtime_data=coordinator,
                    data={"stations": ["STA1"], "measurements": ["PM25", "WR"]},
                ),
                lambda entities: batches.append(list(entities)),
            )
        )

        self.assertEqual(
            ["PM25", "WR"],
            [entity._measurement_code for entity in batches[0]],
        )

    def test_setup_skips_missing_selected_measurements(self) -> None:
        for measurements in (
            {
                ("STA1", "PM25"): make_metric(12.3, "1MW"),
                ("STA1", "O3"): make_metric(None, None),
            },
            {("STA1", "PM25"): make_metric(12.3, "1MW")},
        ):
            with self.subTest(measurements=measurements):
                coordinator = make_coordinator(make_data(measurements))
                batches: list[list[MeasurementSensor]] = []
                add_entities = batches.append

                asyncio.run(
                    async_setup_entry(
                        make_hass(entity_registry=FakeRegistry(())),
                        make_entry(
                            runtime_data=coordinator,
                            data={
                                "stations": ["STA1"],
                                "measurements": ["PM25", "O3"],
                            },
                        ),
                        lambda entities, add_entities=add_entities: add_entities(
                            list(entities)
                        ),
                    )
                )

                self.assertEqual(
                    ["PM25"],
                    [entity._measurement_code for entity in batches[0]],
                )

    def test_setup_syncs_registry_entries(self) -> None:
        coordinator = make_coordinator(
            make_data({("STA1", "PM25"): make_metric(12.3, "1MW")})
        )
        registry = FakeRegistry(
            [
                make_registry_entry(
                    unique_id=build_sensor_unique_id("STA1", "PM25"),
                    disabled_by="integration",
                    entity_id="sensor.pm25_sta1",
                ),
                make_registry_entry(
                    unique_id=build_sensor_unique_id("STA1", "O3"),
                    disabled_by=None,
                    entity_id="sensor.o3_sta1",
                ),
                make_registry_entry(
                    unique_id="other_integration_sensor",
                    disabled_by=None,
                    entity_id="sensor.ignore_me",
                ),
            ]
        )

        asyncio.run(
            async_setup_entry(
                make_hass(entity_registry=registry),
                make_entry(
                    runtime_data=coordinator,
                    data={"stations": ["STA1"], "measurements": ["PM25"]},
                ),
                lambda entities: None,
            )
        )

        self.assertEqual(
            [
                ("sensor.pm25_sta1", {"disabled_by": None}),
                ("sensor.o3_sta1", {"disabled_by": "integration"}),
            ],
            registry.updates,
        )
