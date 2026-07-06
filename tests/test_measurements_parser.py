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

FIXTURE_DIR = Path(__file__).with_name("fixtures")
LUMES_FIXTURE = FIXTURE_DIR / "lumes_sanitized.csv"


class LumesCsvParsingTest(unittest.TestCase):
    def _parse(self, *rows: str):
        return parse_lumes_csv("\n".join(rows))

    def test_parse_lumes_csv_rejects_inconsistent_header_width(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "Lumes CSV header rows have inconsistent column counts"
        ):
            self._parse(
                "Lumes;v2.10;01.01.2026-00:00:00",
                ";PM10",
                ";HMW;extra",
                ";µg/m³",
            )

    def test_parse_lumes_csv_logs_row_length_mismatch(self) -> None:
        with self.assertLogs(
            "custom_components.wiener_luft.measurements_parser", level="WARNING"
        ) as logs:
            parsed = self._parse(
                "Lumes;v2.10;01.01.2026-00:00:00",
                ";Zeit-PM10;PM10",
                ";;HMW",
                ";MESZ;µg/m³",
                "STA1;24.06.2026, 22:30",
                "STA2;24.06.2026, 22:30;1,2;extra",
            )

        self.assertEqual(2, len(parsed))
        self.assertEqual(
            2,
            sum("has" in message and "expected" in message for message in logs.output),
        )

    def test_parse_lumes_csv_handles_missing_and_shifted_time_blocks(self) -> None:
        missing = self._parse(
            "Lumes;v2.10;01.01.2026-00:00:00",
            ";PM10",
            ";HMW",
            ";µg/m³",
            "STA1;1,2",
        )
        shifted = self._parse(
            "Lumes;v2.10;01.01.2026-00:00:00",
            ";PM10;Zeit-PM10;PM10",
            ";HMW;;HMW",
            ";µg/m³;MESZ;µg/m³",
            "STA1;---;24.06.2026, 22:30;3,4",
        )

        self.assertIsNone(missing[("STA1", "PM10")].measured_at)
        self.assertEqual(
            datetime(2026, 6, 24, 22, 30, tzinfo=timezone(timedelta(hours=2))),
            shifted[("STA1", "PM10")].measured_at,
        )

    def test_parse_lumes_csv_logs_unknown_component_in_header(self) -> None:
        with self.assertLogs(
            "custom_components.wiener_luft.measurements_parser", level="WARNING"
        ) as logs:
            self._parse(
                "Lumes;v2.10;01.01.2026-00:00:00",
                ";FOO",
                ";HMW",
                ";µg/m³",
                "STA1;1,2",
            )

        self.assertIn("unexpected=['FOO']", "\n".join(logs.output))

    def test_parse_lumes_csv_logs_unknown_timezone(self) -> None:
        with self.assertLogs(
            "custom_components.wiener_luft.measurements_parser", level="WARNING"
        ) as logs:
            parsed = self._parse(
                "Lumes;v2.10;01.01.2026-00:00:00",
                ";Zeit-PM10;PM10",
                ";;HMW",
                ";XYZ;µg/m³",
                "STA1;24.06.2026, 22:30;1,2",
            )

        self.assertIsNone(parsed[("STA1", "PM10")].measured_at)
        self.assertIn("Could not parse timezone value 'XYZ'", "\n".join(logs.output))

    def test_parse_lumes_csv_logs_invalid_datetime(self) -> None:
        with self.assertLogs(
            "custom_components.wiener_luft.measurements_parser", level="WARNING"
        ) as logs:
            parsed = self._parse(
                "Lumes;v2.10;01.01.2026-00:00:00",
                ";Zeit-PM10;PM10",
                ";;HMW",
                ";MESZ;µg/m³",
                "STA1;not-a-date;1,2",
            )

        self.assertIsNone(parsed[("STA1", "PM10")].measured_at)
        self.assertIn(
            "Could not parse datetime value 'not-a-date'",
            "\n".join(logs.output),
        )

    def test_parse_lumes_csv_logs_invalid_measurement_value(self) -> None:
        with self.assertLogs(
            "custom_components.wiener_luft.measurements_parser", level="WARNING"
        ) as logs:
            parsed = self._parse(
                "Lumes;v2.10;01.01.2026-00:00:00",
                ";PM10",
                ";HMW",
                ";µg/m³",
                "STA1;not-a-number",
            )

        self.assertIsNone(parsed[("STA1", "PM10")].value)
        self.assertIn(
            "Could not parse measurement value 'not-a-number' for station STA1 "
            "component PM10",
            "\n".join(logs.output),
        )

    def test_parse_lumes_csv_tracks_multiple_time_blocks(self) -> None:
        parsed = self._parse(
            "Lumes;v2.10;01.01.2026-00:00:00",
            ";Zeit-PM10;PM10;Zeit-O3;O3",
            ";;HMW;;1MW",
            ";MEZ;µg/m³;MESZ;µg/m³",
            "STA1;24.06.2026, 21:30;1,2;24.06.2026, 22:30;3,4",
        )

        self.assertEqual(
            datetime(2026, 6, 24, 21, 30, tzinfo=timezone(timedelta(hours=1))),
            parsed[("STA1", "PM10")].measured_at,
        )
        self.assertEqual(
            datetime(2026, 6, 24, 22, 30, tzinfo=timezone(timedelta(hours=2))),
            parsed[("STA1", "O3")].measured_at,
        )

    def test_parse_lumes_csv_sets_measurement_type_none_without_valid_value(
        self,
    ) -> None:
        parsed = self._parse(
            "Lumes;v2.10;01.01.2026-00:00:00",
            ";PM10",
            ";HMW",
            ";µg/m³",
            "STA1;---",
        )

        metric = parsed[("STA1", "PM10")]
        self.assertEqual(
            (None, None, "μg/m³"),
            (metric.value, metric.measurement_type, metric.unit),
        )

    def test_parse_lumes_csv_uses_fixture_priority_rules(self) -> None:
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
