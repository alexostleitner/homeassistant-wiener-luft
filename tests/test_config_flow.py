"""Regression tests for config and options flows."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from types import MappingProxyType, ModuleType
from unittest.mock import AsyncMock, patch
from urllib.error import URLError

from homeassistant_stubs import (
    install_homeassistant_stubs,
    make_entry,
    make_hass,
    make_metric,
    make_station,
)


class RequiredStub:
    def __init__(self, schema: str, default=None) -> None:
        self.schema = schema
        self.default = default

    def __hash__(self) -> int:
        return hash(self.schema)


class SchemaStub:
    def __init__(self, schema) -> None:
        self.schema = schema


install_homeassistant_stubs()
voluptuous = sys.modules.setdefault("voluptuous", ModuleType("voluptuous"))
voluptuous.Required = RequiredStub
voluptuous.Schema = SchemaStub

from custom_components.wiener_luft import (  # noqa: E402
    config_flow as config_flow_module,
)
from custom_components.wiener_luft import (  # noqa: E402
    coordinator as coordinator_module,
)
from custom_components.wiener_luft.const import (  # noqa: E402
    MEASUREMENTS_URL,
    SOURCE_SNAPSHOT,
    STATIONS_URL,
)


def read_selector(schema):
    field, selector = next(iter(schema.schema.items()))
    default = field.default() if callable(field.default) else field.default
    return str(field.schema), default, selector.config


class ConfigFlowTest(unittest.TestCase):
    def test_load_measurement_names_returns_empty_for_missing_translation(self) -> None:
        self.assertEqual(
            {},
            config_flow_module._load_measurement_names("zz-test-missing"),
        )

    def test_user_step_aborts_when_station_fetch_fails(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with patch.object(
            config_flow_module,
            "async_fetch_stations",
            side_effect=config_flow_module.FlowFetchError(
                "cannot_connect", {"url": STATIONS_URL}
            ),
        ):
            result = asyncio.run(flow.async_step_user())

        self.assertEqual("abort", result["type"])
        self.assertEqual("stations_cannot_connect", result["reason"])
        self.assertEqual({"url": STATIONS_URL}, result["description_placeholders"])

    def test_user_step_aborts_when_measurement_fetch_fails(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={"STA1": make_station(name="Alpha")},
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                side_effect=config_flow_module.FlowFetchError(
                    "cannot_connect", {"url": MEASUREMENTS_URL}
                ),
            ),
        ):
            result = asyncio.run(flow.async_step_user())

        self.assertEqual("abort", result["type"])
        self.assertEqual("measurements_cannot_connect", result["reason"])
        self.assertEqual({"url": MEASUREMENTS_URL}, result["description_placeholders"])

    def test_user_step_defaults_to_all_stations(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={
                    "STA2": make_station("STA2", "Beta"),
                    "STA1": make_station("STA1", "Alpha"),
                },
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={},
            ),
        ):
            result = asyncio.run(flow.async_step_user())

        field_name, default, selector_config = read_selector(result["data_schema"])
        self.assertEqual("form", result["type"])
        self.assertEqual("user", result["step_id"])
        self.assertEqual({"station_count": "2"}, result["description_placeholders"])
        self.assertEqual("stations", field_name)
        self.assertEqual(["STA1", "STA2"], default)
        self.assertTrue(selector_config["multiple"])
        self.assertEqual(
            [
                {"value": "STA1", "label": "Alpha"},
                {"value": "STA2", "label": "Beta"},
            ],
            selector_config["options"],
        )

    def test_user_step_orders_stations_by_distance(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass(latitude=48.2, longitude=16.3)

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={
                    "S3": make_station("S3", "Charlie", latitude=48.25),
                    "S6": make_station("S6", "Zulu", latitude=48.2),
                    "S2": make_station("S2", "Bravo", latitude=48.23),
                    "S5": make_station("S5", "Echo", latitude=48.24),
                    "S1": make_station("S1", "Alpha", latitude=48.21),
                    "S4": make_station("S4", "Mike", latitude=48.22),
                },
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={},
            ),
        ):
            result = asyncio.run(flow.async_step_user())

        _, default, selector_config = read_selector(result["data_schema"])
        self.assertEqual(["S6", "S1", "S4", "S2", "S5"], default)
        self.assertEqual(
            [
                {"value": "S6", "label": "Zulu (0 km)"},
                {"value": "S1", "label": "Alpha (1 km)"},
                {"value": "S4", "label": "Mike (2 km)"},
                {"value": "S2", "label": "Bravo (3 km)"},
                {"value": "S5", "label": "Echo (4 km)"},
                {"value": "S3", "label": "Charlie (6 km)"},
            ],
            selector_config["options"],
        )

    def test_user_step_falls_back_when_station_coordinates_are_missing(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass(latitude=48.2, longitude=16.3)

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={
                    "STA2": make_station("STA2", "Beta", latitude=None, longitude=None),
                    "STA1": make_station("STA1", "Alpha"),
                },
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={},
            ),
        ):
            result = asyncio.run(flow.async_step_user())

        _, default, selector_config = read_selector(result["data_schema"])
        self.assertEqual(["STA1", "STA2"], default)
        self.assertEqual(
            [
                {"value": "STA1", "label": "Alpha"},
                {"value": "STA2", "label": "Beta"},
            ],
            selector_config["options"],
        )

    def test_measurement_step_marks_partial_availability(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={
                    "STA1": make_station("STA1", "Alpha"),
                    "STA2": make_station("STA2", "Beta"),
                },
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={
                    ("STA1", "PM25"): make_metric(12.3, "1MW"),
                    ("STA1", "O3"): make_metric(5.0, "HMW"),
                    ("STA2", "PM25"): make_metric(11.8, "1MW"),
                    ("STA2", "O3"): make_metric(None, None),
                },
            ),
        ):
            result = asyncio.run(flow.async_step_user({"stations": ["STA1", "STA2"]}))

        _, default, selector_config = read_selector(result["data_schema"])
        self.assertEqual("measurements", result["step_id"])
        self.assertEqual(["PM25", "O3"], default)
        self.assertEqual(
            [
                {"value": "PM25", "label": "PM2.5 (2/2)"},
                {"value": "O3", "label": "Ozone (1/2)"},
            ],
            selector_config["options"][:2],
        )

    def test_measurement_step_creates_entry(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()
        stations = {"STA1": make_station("STA1", "Alpha")}
        measurements = {("STA1", "PM25"): make_metric(12.3, "1MW")}

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value=stations,
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value=measurements,
            ),
        ):
            asyncio.run(flow.async_step_user({"stations": ["STA1"]}))
            result = asyncio.run(
                flow.async_step_measurements({"measurements": ["PM25"]})
            )

        self.assertEqual("create_entry", result["type"])
        self.assertEqual(
            {
                "stations": ["STA1"],
                "measurements": ["PM25"],
                SOURCE_SNAPSHOT: coordinator_module._source_snapshot(
                    stations,
                    measurements,
                ),
            },
            result["data"],
        )

    def test_user_step_requires_station_selection(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={"STA1": make_station("STA1", "Alpha")},
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={},
            ),
        ):
            result = asyncio.run(flow.async_step_user({"stations": []}))

        self.assertEqual("form", result["type"])
        self.assertEqual({"base": "station_required"}, result["errors"])

    def test_measurement_step_requires_measurement_selection(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={"STA1": make_station("STA1", "Alpha")},
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={("STA1", "PM25"): make_metric(12.3, "1MW")},
            ),
        ):
            asyncio.run(flow.async_step_user({"stations": ["STA1"]}))
            result = asyncio.run(flow.async_step_measurements({"measurements": []}))

        self.assertEqual("form", result["type"])
        self.assertEqual({"base": "measurement_required"}, result["errors"])

    def test_measurement_names_fall_back_to_english_for_missing_translations(
        self,
    ) -> None:
        with patch.object(
            config_flow_module,
            "_load_measurement_names",
            side_effect=[{"pm25": "Feinstaub"}, {"pm25": "PM2.5", "o3": "Ozone"}],
        ):
            names = asyncio.run(
                config_flow_module._async_measurement_names(make_hass(language="de"))
            )

        self.assertEqual("Feinstaub", names["PM25"])
        self.assertEqual("Ozone", names["O3"])

    def test_reload_config_entry_returns_without_reload_support(self) -> None:
        for flow in (
            types.SimpleNamespace(),
            types.SimpleNamespace(
                config_entry=types.SimpleNamespace(entry_id="entry-1"),
                hass=make_hass(config_entries=types.SimpleNamespace()),
            ),
        ):
            with self.subTest(flow=flow):
                asyncio.run(config_flow_module._async_reload_config_entry(flow))


class OptionsFlowTest(unittest.TestCase):
    def test_init_uses_existing_explicit_preferences(self) -> None:
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = make_entry(
            data=MappingProxyType({"stations": ["STA1"], "measurements": ["PM25"]}),
            options=MappingProxyType({}),
        )
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={
                    "STA1": make_station("STA1", "Alpha"),
                    "STA2": make_station("STA2", "Beta"),
                },
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={},
            ),
        ):
            result = asyncio.run(flow.async_step_init())

        _, default, _selector_config = read_selector(result["data_schema"])
        self.assertEqual(["STA1"], default)

    def test_init_falls_back_when_saved_preferences_are_outdated(self) -> None:
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = make_entry(
            data=MappingProxyType({"stations": ["STA9"], "measurements": ["ZZ"]}),
            options=MappingProxyType({}),
        )
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={
                    "STA1": make_station("STA1", "Alpha"),
                    "STA2": make_station("STA2", "Beta"),
                },
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={
                    ("STA1", "PM25"): make_metric(12.3, "1MW"),
                    ("STA2", "O3"): make_metric(5.0, "HMW"),
                },
            ),
        ):
            station_result = asyncio.run(flow.async_step_init())
            measurement_result = asyncio.run(
                flow.async_step_init({"stations": ["STA1", "STA2"]})
            )

        _, station_default, _station_selector = read_selector(
            station_result["data_schema"]
        )
        _, measurement_default, measurement_selector = read_selector(
            measurement_result["data_schema"]
        )
        self.assertEqual(["STA1", "STA2"], station_default)
        self.assertEqual(["PM25", "O3"], measurement_default)
        self.assertEqual(
            [
                {"value": "PM25", "label": "PM2.5 (1/2)"},
                {"value": "O3", "label": "Ozone (1/2)"},
            ],
            measurement_selector["options"],
        )

    def test_measurement_step_persists_snapshot_and_reloads(self) -> None:
        stations = {"STA1": make_station("STA1", "Alpha")}
        measurements = {("STA1", "PM25"): make_metric(12.3, "1MW")}
        config_entries = types.SimpleNamespace(
            async_reload=AsyncMock(return_value=None)
        )
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = make_entry(
            entry_id="entry-1",
            data=MappingProxyType({"stations": ["STA1"], "measurements": ["PM25"]}),
            options=MappingProxyType({}),
        )
        flow.hass = make_hass(config_entries=config_entries)

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value=stations,
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value=measurements,
            ),
        ):
            asyncio.run(flow.async_step_init({"stations": ["STA1"]}))
            result = asyncio.run(
                flow.async_step_measurements({"measurements": ["PM25"]})
            )

        self.assertEqual("create_entry", result["type"])
        self.assertEqual(
            {
                "stations": ["STA1"],
                "measurements": ["PM25"],
                SOURCE_SNAPSHOT: coordinator_module._source_snapshot(
                    stations,
                    measurements,
                ),
            },
            result["data"],
        )
        config_entries.async_reload.assert_awaited_once_with("entry-1")

    def test_measurement_step_ignores_missing_entry_reload(self) -> None:
        config_entries = types.SimpleNamespace(
            async_reload=AsyncMock(
                side_effect=config_flow_module.UnknownEntry("removed")
            )
        )
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = make_entry(
            entry_id="entry-removed",
            data=MappingProxyType({"stations": ["STA1"], "measurements": ["PM25"]}),
            options=MappingProxyType({}),
        )
        flow.hass = make_hass(config_entries=config_entries)

        with (
            patch.object(
                config_flow_module,
                "async_fetch_stations",
                return_value={"STA1": make_station("STA1", "Alpha")},
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value={("STA1", "PM25"): make_metric(12.3, "1MW")},
            ),
        ):
            asyncio.run(flow.async_step_init({"stations": ["STA1"]}))
            result = asyncio.run(
                flow.async_step_measurements({"measurements": ["PM25"]})
            )

        self.assertEqual("create_entry", result["type"])
        config_entries.async_reload.assert_awaited_once_with("entry-removed")

    def test_fetch_payload_raises_connect_error(self) -> None:
        with (
            patch.object(
                coordinator_module,
                "urlopen",
                side_effect=URLError("offline"),
            ),
            self.assertRaises(coordinator_module.FlowFetchError) as err,
        ):
            coordinator_module._fetch_payload("https://example.test")

        self.assertEqual("cannot_connect", err.exception.reason)
        self.assertEqual({"url": "https://example.test"}, err.exception.placeholders)

    def test_fetch_measurements_invalid_response_includes_url(self) -> None:
        with (
            patch.object(
                coordinator_module,
                "_fetch_payload",
                return_value=b"not a valid csv payload",
            ),
            self.assertRaises(coordinator_module.FlowFetchError) as err,
        ):
            asyncio.run(coordinator_module.async_fetch_measurements(make_hass()))

        self.assertEqual("invalid_response", err.exception.reason)
        self.assertEqual({"url": MEASUREMENTS_URL}, err.exception.placeholders)
