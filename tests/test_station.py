"""Regression tests for station model helpers."""

from __future__ import annotations

import unittest

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft.const import NAME  # noqa: E402
from custom_components.wiener_luft.station import (  # noqa: E402
    Station,
    station_device_info,
)


class StationHelperTest(unittest.TestCase):
    def test_station_device_info_includes_optional_url(self) -> None:
        station = Station(
            code="STA1",
            name="Station 1",
            district=1,
            latitude=48.2,
            longitude=16.3,
            station_url="https://example.test/stations/sta1",
        )

        self.assertEqual(
            {
                "identifiers": {("wiener_luft", "STA1")},
                "name": "Station 1",
                "manufacturer": NAME,
                "configuration_url": "https://example.test/stations/sta1",
            },
            station_device_info(station),
        )
