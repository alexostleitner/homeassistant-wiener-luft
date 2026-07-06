"""Regression tests for payload and numeric parsing helpers."""

from __future__ import annotations

import unittest

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft.parsing import (  # noqa: E402
    decode_payload,
    parse_number,
)


class ParsingHelpersTest(unittest.TestCase):
    def test_decode_payload_uses_utf8_sig(self) -> None:
        self.assertEqual("abc", decode_payload(b"\xef\xbb\xbfabc"))

    def test_decode_payload_uses_cp1252(self) -> None:
        self.assertEqual("abc\u2013def", decode_payload(b"abc\x96def"))

    def test_parse_number_handles_common_inputs(self) -> None:
        cases = (
            (None, None),
            (-999, None),
            ("1,23", 1.23),
            (" 4.5 ", 4.5),
        )

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(expected, parse_number(value))

    def test_parse_number_returns_none_for_invalid_values_without_logging(self) -> None:
        with self.assertNoLogs(
            "custom_components.wiener_luft.parsing", level="WARNING"
        ):
            result = parse_number("not a number")

        self.assertIsNone(result)
