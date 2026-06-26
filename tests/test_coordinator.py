"""Regression tests for coordinator refresh behavior."""

from __future__ import annotations

import json
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft import (  # noqa: E402
    coordinator as coordinator_module,
)
from custom_components.wiener_luft.client import Station  # noqa: E402
from custom_components.wiener_luft.coordinator import (  # noqa: E402
    IntegrationCoordinator,
    IntegrationData,
)

FIXTURE_DIR = Path(__file__).with_name("fixtures")
LUMES_FIXTURE = FIXTURE_DIR / "lumes_sanitized.csv"
NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _make_coordinator() -> IntegrationCoordinator:
    coordinator = IntegrationCoordinator.__new__(IntegrationCoordinator)

    async def async_add_executor_job(func, *args):
        return func(*args)

    coordinator.hass = types.SimpleNamespace(
        async_add_executor_job=async_add_executor_job
    )
    coordinator.stations = {}
    coordinator._stations_last_refresh_attempt = None
    return coordinator


STATION_PAYLOAD = json.dumps(
    {
        "features": [
            {
                "properties": {
                    "NAME_KURZ": "STA1",
                    "NAME": "Station Alpha",
                    "BEZIRK": 3,
                },
                "geometry": {"coordinates": [16.31, 48.21]},
            },
            {
                "properties": {
                    "NAME_KURZ": "STA2",
                    "NAME": "Station Beta",
                    "BEZIRK": 4,
                },
                "geometry": {"coordinates": [16.32, 48.22]},
            },
        ]
    }
).encode()


class IntegrationCoordinatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_stations_caches_within_one_day(self) -> None:
        coordinator = _make_coordinator()

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                return_value=_Response(STATION_PAYLOAD),
            ) as urlopen_mock,
            patch.object(
                coordinator_module.dt_util,
                "utcnow",
                side_effect=[NOW, NOW + timedelta(hours=1)],
            ),
        ):
            first = await coordinator.async_refresh_stations()
            second = await coordinator.async_refresh_stations()

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(1, urlopen_mock.call_count)
        self.assertEqual({"STA1", "STA2"}, set(coordinator.stations))

    async def test_refresh_stations_raises_without_cached_data(self) -> None:
        coordinator = _make_coordinator()

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                side_effect=RuntimeError("network down"),
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
            self.assertRaises(coordinator_module.UpdateFailed),
        ):
            await coordinator.async_refresh_stations(force=True)

    async def test_refresh_stations_keeps_cached_data_on_failure(self) -> None:
        coordinator = _make_coordinator()
        coordinator.stations = {
            "STA1": Station(
                code="STA1",
                name="Station Alpha",
                district=3,
                latitude=48.21,
                longitude=16.31,
                station_url=None,
            )
        }

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                side_effect=RuntimeError("network down"),
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
        ):
            refreshed = await coordinator.async_refresh_stations(force=True)

        self.assertFalse(refreshed)
        self.assertEqual({"STA1"}, set(coordinator.stations))

    async def test_update_data_logs_unknown_station_codes(self) -> None:
        coordinator = _make_coordinator()

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                side_effect=[
                    _Response(STATION_PAYLOAD),
                    _Response(LUMES_FIXTURE.read_bytes()),
                ],
            ) as urlopen_mock,
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
            self.assertLogs(coordinator_module.LOGGER.name, level="WARNING") as logs,
        ):
            data = await coordinator._async_update_data()

        self.assertIsInstance(data, IntegrationData)
        self.assertIn(
            "Wiener Luftmessnetz CSV contains unknown station code STA3",
            "\n".join(logs.output),
        )
        self.assertIn("STA3", {key[0] for key in data.measurements.selected})
        self.assertEqual(2, urlopen_mock.call_count)

    async def test_update_data_raises_when_measurement_fetch_fails(self) -> None:
        coordinator = _make_coordinator()

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                side_effect=[
                    _Response(STATION_PAYLOAD),
                    RuntimeError("measurement feed down"),
                ],
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
            self.assertRaises(coordinator_module.UpdateFailed),
        ):
            await coordinator._async_update_data()
