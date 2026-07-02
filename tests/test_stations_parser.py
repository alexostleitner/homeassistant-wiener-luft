"""Regression tests for station metadata parsing helpers."""

from __future__ import annotations

import unittest

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft.stations_parser import (  # noqa: E402
    parse_station_geojson,
)


class StationGeoJsonParsingTest(unittest.TestCase):
    def test_parse_station_geojson_requires_features_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "features list"):
            parse_station_geojson({})

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
            "custom_components.wiener_luft.stations_parser", level="WARNING"
        ) as logs:
            stations = parse_station_geojson(payload)

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

    def test_parse_station_geojson_ignores_non_dict_features(self) -> None:
        stations = parse_station_geojson(
            {
                "features": [
                    "skip",
                    {
                        "properties": {
                            "NAME_KURZ": "STA1",
                            "NAME": "Station Alpha",
                        },
                        "geometry": {"coordinates": [16.31, 48.21]},
                    },
                ]
            }
        )

        self.assertEqual({"STA1"}, set(stations))

    def test_parse_station_geojson_handles_short_coordinates(self) -> None:
        stations = parse_station_geojson(
            {
                "features": [
                    {
                        "properties": {
                            "NAME_KURZ": "STA1",
                            "NAME": "Station Alpha",
                        },
                        "geometry": {"coordinates": [16.31]},
                    }
                ]
            }
        )

        self.assertIsNone(stations["STA1"].longitude)
        self.assertIsNone(stations["STA1"].latitude)
