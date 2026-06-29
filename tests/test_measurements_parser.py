"""Regression tests for measurement parsing helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft.measurements_parser import (  # noqa: E402
    parse_lumes_csv,
)
from custom_components.wiener_luft.parsing import decode_payload  # noqa: E402

FIXTURE_DIR = Path(__file__).with_name("fixtures")
LUMES_FIXTURE = FIXTURE_DIR / "lumes_sanitized.csv"


class LumesCsvParsingTest(unittest.TestCase):
    def test_parse_lumes_csv_uses_fixture_priority_rules(self) -> None:
        self.assertEqual("abc\u2013def", decode_payload(b"abc\x96def"))
        parsed = parse_lumes_csv(LUMES_FIXTURE.read_bytes())

        self.assertEqual({"STA1", "STA2", "STA3"}, {key[0] for key in parsed})
        self.assertEqual(33, len(parsed))

        expected = {
            ("STA1", "PM10"): (13.7, "HMW", "μg/m³"),
            ("STA1", "PM25"): (4.4, "HMW", "μg/m³"),
            ("STA1", "O3"): (82.0, "HMW", "μg/m³"),
            ("STA1", "CO"): (0.21, "HMW", "mg/m³"),
            ("STA2", "PM10"): (11.1, "MW24", "μg/m³"),
            ("STA2", "PM25"): (2.7, "MW24", "μg/m³"),
            ("STA2", "O3"): (79.0, "1MW", "μg/m³"),
            ("STA2", "CO"): (0.15, "MW8", "mg/m³"),
            ("STA3", "PM10"): (None, None, "μg/m³"),
            ("STA3", "PM25"): (4.6, "HMW", "μg/m³"),
            ("STA3", "O3"): (79.5, "1MW", "μg/m³"),
            ("STA3", "CO"): (0.17, "HMW", "mg/m³"),
        }
        expected_measured_at = datetime(
            2026,
            6,
            24,
            22,
            30,
            tzinfo=timezone(timedelta(hours=2), name="MESZ"),
        )
        for key, expected_value in expected.items():
            with self.subTest(key=key):
                metric = parsed[key]
                self.assertEqual(
                    expected_value,
                    (metric.value, metric.measurement_type, metric.unit),
                )
                if metric.value is None:
                    self.assertIsNone(metric.measured_at)
                else:
                    self.assertEqual(expected_measured_at, metric.measured_at)
