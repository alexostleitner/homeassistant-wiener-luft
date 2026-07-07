"""Regression tests for config and options flows."""

from __future__ import annotations

import asyncio
import sys
import unittest
from types import MappingProxyType, ModuleType
from unittest.mock import patch
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
    config_flow_data as config_flow_data_module,
)
from custom_components.wiener_luft import (  # noqa: E402
    coordinator as coordinator_module,
)
from custom_components.wiener_luft import exceptions as exceptions_module  # noqa: E402
from custom_components.wiener_luft import fetch as fetch_module  # noqa: E402
from custom_components.wiener_luft.const import (  # noqa: E402
    MEASUREMENTS_URL,
    SOURCE_SNAPSHOT,
    STATIONS_URL,
)
from custom_components.wiener_luft.models import IntegrationData  # noqa: E402


def read_selector(schema):
    field, selector = next(iter(schema.schema.items()))
    default = field.default() if callable(field.default) else field.default
    return str(field.schema), default, selector.config


def make_flow_data(stations, measurements):
    return IntegrationData(
        stations=stations,
        measurements=measurements,
    )


class ConfigFlowTest(unittest.TestCase):
    def test_load_measurement_names_returns_empty_for_missing_translation(self) -> None:
        self.assertEqual(
            {},
            config_flow_data_module._load_measurement_names_from_file(
                "zz-test-missing"
            ),
        )

    def test_user_step_aborts_when_station_fetch_fails(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = make_hass()

        with patch.object(
            config_flow_module,
            "async_fetch_flow_data",
            return_value=(None, "stations_cannot_connect", {"url": STATIONS_URL}),
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
                "async_fetch_flow_data",
                return_value=(
                    None,
                    "measurements_cannot_connect",
                    {"url": MEASUREMENTS_URL},
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {
                            "STA2": make_station("STA2", "Beta"),
                            "STA1": make_station("STA1", "Alpha"),
                        },
                        {},
                    ),
                    None,
                    None,
                ),
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {
                            "S3": make_station("S3", "Charlie", latitude=48.25),
                            "S6": make_station("S6", "Zulu", latitude=48.2),
                            "S2": make_station("S2", "Bravo", latitude=48.23),
                            "S5": make_station("S5", "Echo", latitude=48.24),
                            "S1": make_station("S1", "Alpha", latitude=48.21),
                            "S4": make_station("S4", "Mike", latitude=48.22),
                        },
                        {},
                    ),
                    None,
                    None,
                ),
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {
                            "STA2": make_station(
                                "STA2", "Beta", latitude=None, longitude=None
                            ),
                            "STA1": make_station("STA1", "Alpha"),
                        },
                        {},
                    ),
                    None,
                    None,
                ),
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {
                            "STA1": make_station("STA1", "Alpha"),
                            "STA2": make_station("STA2", "Beta"),
                        },
                        {
                            ("STA1", "PM25"): make_metric(12.3, "1MW"),
                            ("STA1", "O3"): make_metric(5.0, "HMW"),
                            ("STA2", "PM25"): make_metric(11.8, "1MW"),
                            ("STA2", "O3"): make_metric(None, None),
                        },
                    ),
                    None,
                    None,
                ),
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
                "async_fetch_flow_data",
                return_value=(make_flow_data(stations, measurements), None, None),
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
                SOURCE_SNAPSHOT: coordinator_module.build_source_snapshot(
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data({"STA1": make_station("STA1", "Alpha")}, {}),
                    None,
                    None,
                ),
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {"STA1": make_station("STA1", "Alpha")},
                        {("STA1", "PM25"): make_metric(12.3, "1MW")},
                    ),
                    None,
                    None,
                ),
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
            config_flow_data_module,
            "_load_measurement_names_from_file",
            side_effect=[{"pm25": "Feinstaub"}, {"pm25": "PM2.5", "o3": "Ozone"}],
        ):
            names = asyncio.run(
                config_flow_data_module.async_get_measurement_names(
                    make_hass(language="de")
                )
            )

        self.assertEqual("Feinstaub", names["PM25"])
        self.assertEqual("Ozone", names["O3"])


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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {
                            "STA1": make_station("STA1", "Alpha"),
                            "STA2": make_station("STA2", "Beta"),
                        },
                        {},
                    ),
                    None,
                    None,
                ),
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
                "async_fetch_flow_data",
                return_value=(
                    make_flow_data(
                        {
                            "STA1": make_station("STA1", "Alpha"),
                            "STA2": make_station("STA2", "Beta"),
                        },
                        {
                            ("STA1", "PM25"): make_metric(12.3, "1MW"),
                            ("STA2", "O3"): make_metric(5.0, "HMW"),
                        },
                    ),
                    None,
                    None,
                ),
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

    def test_measurement_step_persists_snapshot(self) -> None:
        stations = {"STA1": make_station("STA1", "Alpha")}
        measurements = {("STA1", "PM25"): make_metric(12.3, "1MW")}
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = make_entry(
            entry_id="entry-1",
            data=MappingProxyType({"stations": ["STA1"], "measurements": ["PM25"]}),
            options=MappingProxyType({}),
        )
        flow.hass = make_hass()

        with (
            patch.object(
                config_flow_module,
                "async_fetch_flow_data",
                return_value=(make_flow_data(stations, measurements), None, None),
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
                SOURCE_SNAPSHOT: coordinator_module.build_source_snapshot(
                    stations,
                    measurements,
                ),
            },
            result["data"],
        )

    def test_options_flow_uses_reload_base_class(self) -> None:
        self.assertTrue(
            issubclass(
                config_flow_module.IntegrationOptionsFlow,
                config_flow_module.OptionsFlowWithReload,
            )
        )

    def test_fetch_payload_raises_connect_error(self) -> None:
        with (
            patch.object(
                fetch_module,
                "urlopen",
                side_effect=URLError("offline"),
            ),
            self.assertRaises(exceptions_module.FlowFetchError) as err,
        ):
            fetch_module._fetch_payload("https://example.test")

        self.assertEqual("cannot_connect", err.exception.reason)
        self.assertEqual({"url": "https://example.test"}, err.exception.placeholders)

    def test_fetch_measurements_invalid_response_includes_url(self) -> None:
        with (
            patch.object(
                fetch_module,
                "_fetch_payload",
                return_value=b"not a valid csv payload",
            ),
            self.assertRaises(exceptions_module.FlowFetchError) as err,
        ):
            asyncio.run(fetch_module.async_fetch_measurements(make_hass()))

        self.assertEqual("invalid_response", err.exception.reason)
        self.assertEqual({"url": MEASUREMENTS_URL}, err.exception.placeholders)
