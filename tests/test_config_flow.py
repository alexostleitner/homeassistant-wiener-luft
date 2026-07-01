"""Regression tests for config and options flows."""

from __future__ import annotations

import asyncio
import types
import unittest
from datetime import UTC, datetime
from types import MappingProxyType
from unittest.mock import patch
from urllib.error import URLError

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

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
from custom_components.wiener_luft.measurements_parser import (  # noqa: E402
    SelectedMetric,
)
from custom_components.wiener_luft.station import Station  # noqa: E402

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def _hass(language: str = "en"):
    return types.SimpleNamespace(
        config=types.SimpleNamespace(language=language),
        async_add_executor_job=asyncio.to_thread,
    )


def _station(code: str, name: str) -> Station:
    return Station(code, name, 1, 48.2, 16.3, None)


def _metric(
    value: float | None, measurement_type: str | None, unit: str = "μg/m³"
) -> SelectedMetric:
    return SelectedMetric(value, unit, measurement_type, NOW)


def _selector_details(schema):
    field, selector = next(iter(schema.schema.items()))
    default = field.default() if callable(field.default) else field.default
    return str(field.schema), default, selector.config


class ConfigFlowTest(unittest.TestCase):
    def test_user_step_aborts_when_station_fetch_fails(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = _hass()

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

    def test_user_step_defaults_to_all_stations(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = _hass()
        stations = {
            "STA2": _station("STA2", "Beta"),
            "STA1": _station("STA1", "Alpha"),
        }

        with (
            patch.object(
                config_flow_module, "async_fetch_stations", return_value=stations
            ),
            patch.object(
                config_flow_module, "async_fetch_measurements", return_value={}
            ),
        ):
            result = asyncio.run(flow.async_step_user())

        self.assertEqual("form", result["type"])
        self.assertEqual("user", result["step_id"])
        field_name, default, selector_config = _selector_details(result["data_schema"])
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

    def test_measurement_step_marks_partial_availability(self) -> None:
        flow = config_flow_module.IntegrationConfigFlow()
        flow.hass = _hass()
        stations = {
            "STA1": _station("STA1", "Alpha"),
            "STA2": _station("STA2", "Beta"),
        }
        measurements = {
            ("STA1", "PM25"): _metric(12.3, "1MW"),
            ("STA1", "O3"): _metric(5.0, "HMW"),
            ("STA2", "PM25"): _metric(11.8, "1MW"),
            ("STA2", "O3"): _metric(None, None),
        }

        with (
            patch.object(
                config_flow_module, "async_fetch_stations", return_value=stations
            ),
            patch.object(
                config_flow_module,
                "async_fetch_measurements",
                return_value=measurements,
            ),
        ):
            result = asyncio.run(
                flow.async_step_user({"stations": ["STA1", "STA2"]})
            )

        self.assertEqual("measurements", result["step_id"])
        _, default, selector_config = _selector_details(result["data_schema"])
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
        flow.hass = _hass()
        stations = {"STA1": _station("STA1", "Alpha")}
        measurements = {("STA1", "PM25"): _metric(12.3, "1MW")}

        with (
            patch.object(
                config_flow_module, "async_fetch_stations", return_value=stations
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
                    stations, measurements
                ),
            },
            result["data"],
        )


class OptionsFlowTest(unittest.TestCase):
    def test_init_uses_existing_explicit_preferences(self) -> None:
        config_entry = types.SimpleNamespace(
            data=MappingProxyType({"stations": ["STA1"], "measurements": ["PM25"]}),
            options=MappingProxyType({}),
        )
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = config_entry
        flow.hass = _hass()
        stations = {
            "STA1": _station("STA1", "Alpha"),
            "STA2": _station("STA2", "Beta"),
        }

        with (
            patch.object(
                config_flow_module, "async_fetch_stations", return_value=stations
            ),
            patch.object(
                config_flow_module, "async_fetch_measurements", return_value={}
            ),
        ):
            result = asyncio.run(flow.async_step_init())

        _, default, _selector_config = _selector_details(result["data_schema"])
        self.assertEqual(["STA1"], default)

    def test_measurement_step_persists_snapshot_in_options(self) -> None:
        config_entry = types.SimpleNamespace(
            data=MappingProxyType({"stations": ["STA1"], "measurements": ["PM25"]}),
            options=MappingProxyType({}),
        )
        flow = config_flow_module.IntegrationOptionsFlow()
        flow._config_entry = config_entry
        flow.hass = _hass()
        stations = {"STA1": _station("STA1", "Alpha")}
        measurements = {("STA1", "PM25"): _metric(12.3, "1MW")}

        with (
            patch.object(
                config_flow_module, "async_fetch_stations", return_value=stations
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
                    stations, measurements
                ),
            },
            result["data"],
        )

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
        self.assertEqual(
            {"url": "https://example.test"},
            err.exception.placeholders,
        )

    def test_fetch_measurements_invalid_response_includes_url(self) -> None:
        hass = types.SimpleNamespace(async_add_executor_job=asyncio.to_thread)

        with (
            patch.object(
                coordinator_module,
                "_fetch_payload",
                return_value=b"not a valid csv payload",
            ),
            self.assertRaises(coordinator_module.FlowFetchError) as err,
        ):
            asyncio.run(coordinator_module.async_fetch_measurements(hass))

        self.assertEqual("invalid_response", err.exception.reason)
        self.assertEqual({"url": MEASUREMENTS_URL}, err.exception.placeholders)
