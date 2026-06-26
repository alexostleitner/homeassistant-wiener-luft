"""Regression tests for client parsing helpers."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft.client import (  # noqa: E402
    decode_payload,
    parse_lumes_csv,
    parse_station_geojson,
)

FIXTURE_DIR = Path(__file__).with_name("fixtures")
LUMES_FIXTURE = FIXTURE_DIR / "lumes_sanitized.csv"


class LumesCsvParsingTest(unittest.TestCase):
    def test_parse_lumes_csv_uses_fixture_priority_rules(self) -> None:
        self.assertEqual("abc\u2013def", decode_payload(b"abc\x96def"))
        parsed = parse_lumes_csv(LUMES_FIXTURE.read_bytes())

        self.assertEqual({"STA1", "STA2", "STA3"}, {key[0] for key in parsed.selected})
        self.assertEqual(33, len(parsed.selected))

        expected = {
            ("STA1", "PM10"): (13.7, "HMW", "µg/m³"),
            ("STA1", "PM25"): (4.4, "HMW", "µg/m³"),
            ("STA1", "O3"): (82.0, "HMW", "µg/m³"),
            ("STA1", "CO"): (0.21, "HMW", "mg/m³"),
            ("STA2", "PM10"): (11.1, "MW24", "µg/m³"),
            ("STA2", "PM25"): (2.7, "MW24", "µg/m³"),
            ("STA2", "O3"): (79.0, "1MW", "µg/m³"),
            ("STA2", "CO"): (0.15, "MW8", "mg/m³"),
            ("STA3", "PM10"): (None, None, "µg/m³"),
            ("STA3", "PM25"): (4.6, "HMW", "µg/m³"),
            ("STA3", "O3"): (79.5, "1MW", "µg/m³"),
            ("STA3", "CO"): (0.17, "HMW", "mg/m³"),
        }
        for key, expected_value in expected.items():
            with self.subTest(key=key):
                metric = parsed.selected[key]
                self.assertEqual(
                    expected_value,
                    (metric.value, metric.measurement_type, metric.unit),
                )


class StationGeoJsonParsingTest(unittest.TestCase):
    def test_parse_station_geojson(self) -> None:
        payload = {
            "features": [
                {
                    "properties": {
                        "NAME_KURZ": "STA1",
                        "NAME": "Station Alpha",
                        "BEZIRK": "3",
                        "URL_INFO": "https://example.test/a",
                    },
                    "geometry": {"coordinates": [16.31, 48.21]},
                },
                {
                    "properties": {
                        "NAME_KURZ": "sta1",
                        "NAME": "Station Alpha Updated",
                        "BEZIRK": 4,
                    },
                    "geometry": {"coordinates": [16.32, 48.22]},
                },
                {
                    "properties": {"NAME": "Ignored"},
                    "geometry": {"coordinates": [16.33, 48.23]},
                },
                {
                    "properties": {
                        "NAME_KURZ": "STA3",
                        "NAME": "Station Gamma",
                        "BEZIRK": None,
                    },
                    "geometry": {"coordinates": [16.5, 48.3]},
                },
            ]
        }

        with self.assertLogs(
            "custom_components.wiener_luft.client", level="WARNING"
        ) as logs:
            stations = parse_station_geojson(json.dumps(payload))

        self.assertEqual({"STA1", "STA3"}, set(stations))
        self.assertEqual("Station Alpha Updated", stations["STA1"].name)
        self.assertEqual(4, stations["STA1"].district)
        self.assertEqual(48.22, stations["STA1"].latitude)
        self.assertEqual(16.32, stations["STA1"].longitude)
        self.assertEqual("Station Gamma", stations["STA3"].name)
        self.assertIsNone(stations["STA3"].district)
        self.assertEqual(48.3, stations["STA3"].latitude)
        self.assertEqual(16.5, stations["STA3"].longitude)
        self.assertIn(
            "Duplicate station metadata for NAME_KURZ=STA1",
            "\n".join(logs.output),
        )
        self.assertIn(
            "Skipping station feature without NAME_KURZ",
            "\n".join(logs.output),
        )
