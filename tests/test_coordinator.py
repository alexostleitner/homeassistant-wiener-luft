"""Regression tests for coordinator refresh behavior."""

from __future__ import annotations

import json
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.wiener_luft import (  # noqa: E402
    coordinator as coordinator_module,
)
from custom_components.wiener_luft.coordinator import (  # noqa: E402
    IntegrationCoordinator,
    IntegrationData,
)
from custom_components.wiener_luft.measurements_parser import (  # noqa: E402
    SelectedMetric,
)
from custom_components.wiener_luft.station import Station  # noqa: E402

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

    async_update_entry = Mock(side_effect=lambda entry, **changes: setattr(
        entry, "data", changes["data"]
    ))

    coordinator.hass = types.SimpleNamespace(
        async_add_executor_job=async_add_executor_job,
        config_entries=types.SimpleNamespace(async_update_entry=async_update_entry),
    )
    coordinator.stations = {}
    coordinator._stations_last_refresh_attempt = None
    coordinator.config_entry = types.SimpleNamespace(data={}, options={})
    coordinator._async_update_entry = async_update_entry
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

    async def test_refresh_stations_persists_station_snapshot(self) -> None:
        coordinator = _make_coordinator()

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                return_value=_Response(STATION_PAYLOAD),
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
        ):
            refreshed = await coordinator.async_refresh_stations(force=True)

        self.assertTrue(refreshed)
        self.assertEqual(
            coordinator_module._station_snapshot(coordinator.stations),
            coordinator.config_entry.data[coordinator_module.STATION_SNAPSHOT],
        )
        coordinator._async_update_entry.assert_called_once()

    async def test_async_setup_loads_cached_station_snapshot(self) -> None:
        coordinator = _make_coordinator()
        cached_stations = {
            "STA1": Station(
                code="STA1",
                name="Station Alpha",
                district=3,
                latitude=48.21,
                longitude=16.31,
                station_url="https://example.test/stations/sta1",
            )
        }
        coordinator.config_entry.data = {
            coordinator_module.STATION_SNAPSHOT: coordinator_module._station_snapshot(
                cached_stations
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
            await coordinator._async_setup()

        self.assertEqual(cached_stations, coordinator.stations)

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
        self.assertIn("STA3", {key[0] for key in data.measurements})
        self.assertEqual(2, urlopen_mock.call_count)

    def test_log_new_source_items_uses_saved_snapshot(self) -> None:
        coordinator = _make_coordinator()
        station_alpha = Station(
            code="STA1",
            name="Station Alpha",
            district=3,
            latitude=48.21,
            longitude=16.31,
            station_url=None,
        )
        station_beta = Station(
            code="STA2",
            name="Station Beta",
            district=4,
            latitude=48.22,
            longitude=16.32,
            station_url=None,
        )
        base_stations = {"STA1": station_alpha, "STA2": station_beta}
        base_measurements = {
            ("STA1", "PM25"): SelectedMetric(12.3, "μg/m³", "1MW", NOW),
            ("STA2", "O3"): SelectedMetric(4.5, "μg/m³", "HMW", NOW),
        }
        new_station = Station(
            code="STA3",
            name="Station Gamma",
            district=5,
            latitude=48.23,
            longitude=16.33,
            station_url=None,
        )
        expanded_stations = {**base_stations, "STA3": new_station}
        expanded_measurements = {
            **base_measurements,
            ("STA3", "PM25"): SelectedMetric(3.2, "μg/m³", "1MW", NOW),
            ("STA1", "O3"): SelectedMetric(6.7, "μg/m³", "HMW", NOW),
        }
        coordinator.stations = expanded_stations
        coordinator.config_entry.data = {
            coordinator_module.SOURCE_SNAPSHOT: coordinator_module._source_snapshot(
                base_stations, base_measurements
            )
        }
        coordinator.config_entry.options = {}

        with self.assertLogs(coordinator_module.LOGGER.name, level="INFO") as logs:
            coordinator._log_new_source_items(expanded_measurements)
        with self.assertLogs(coordinator_module.LOGGER.name, level="INFO") as logs2:
            coordinator._log_new_source_items(expanded_measurements)

        coordinator.config_entry.options = {
            coordinator_module.SOURCE_SNAPSHOT: coordinator_module._source_snapshot(
                expanded_stations, expanded_measurements
            )
        }
        with self.assertNoLogs(coordinator_module.LOGGER.name, level="INFO"):
            coordinator._log_new_source_items(expanded_measurements)

        self.assertIn("1 new station(s)", logs.output[0])
        self.assertIn("2 new station/measurement combination(s)", logs.output[0])
        self.assertIn("1 new station(s)", logs2.output[0])
        self.assertIn("2 new station/measurement combination(s)", logs2.output[0])

    async def test_update_data_changes_when_measurements_turn_stale(self) -> None:
        coordinator = _make_coordinator()
        first_poll = datetime(2026, 6, 24, 21, 30, tzinfo=UTC)
        second_poll = datetime(2026, 6, 24, 22, 0, tzinfo=UTC)
        third_poll = datetime(2026, 6, 24, 23, 0, tzinfo=UTC)

        with (
            patch.object(
                coordinator_module,
                "urlopen",
                side_effect=[
                    _Response(STATION_PAYLOAD),
                    _Response(LUMES_FIXTURE.read_bytes()),
                    _Response(LUMES_FIXTURE.read_bytes()),
                    _Response(LUMES_FIXTURE.read_bytes()),
                ],
            ),
            patch.object(
                coordinator_module.dt_util,
                "utcnow",
                side_effect=[
                    first_poll,
                    first_poll,
                    second_poll,
                    second_poll,
                    third_poll,
                    third_poll,
                ],
            ),
        ):
            first = await coordinator._async_update_data()
            second = await coordinator._async_update_data()
            third = await coordinator._async_update_data()

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(
            frozenset(
                key
                for key, reading in third.measurements.items()
                if reading.measured_at is not None
            ),
            third.stale_measurements,
        )

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
