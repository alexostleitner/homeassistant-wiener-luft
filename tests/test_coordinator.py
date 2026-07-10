"""Regression tests for coordinator refresh behavior."""

from __future__ import annotations

import io
import json
import types
import unittest
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from homeassistant_stubs import (
    install_homeassistant_stubs,
    make_entry,
    make_hass,
    make_metric,
    make_station,
)

install_homeassistant_stubs()

from custom_components.wiener_luft import (  # noqa: E402
    coordinator as coordinator_module,
)
from custom_components.wiener_luft import exceptions as exceptions_module  # noqa: E402
from custom_components.wiener_luft import fetch as fetch_module  # noqa: E402
from custom_components.wiener_luft import snapshots as snapshots_module  # noqa: E402
from custom_components.wiener_luft.const import (  # noqa: E402
    MEASUREMENTS_URL,
    STATIONS_URL,
)
from custom_components.wiener_luft.models import IntegrationData  # noqa: E402

FIXTURE_DIR = Path(__file__).with_name("fixtures")
LUMES_FIXTURE = FIXTURE_DIR / "lumes_sanitized.csv"
NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


def make_response(payload: bytes):
    return nullcontext(io.BytesIO(payload))


def make_coordinator(
    *, data=None, options=None
) -> tuple[coordinator_module.IntegrationCoordinator, Mock]:
    async_update_entry = Mock(
        side_effect=lambda entry, **changes: setattr(entry, "data", changes["data"])
    )
    hass = make_hass(
        config_entries=types.SimpleNamespace(async_update_entry=async_update_entry)
    )
    coordinator = coordinator_module.IntegrationCoordinator(
        hass,
        make_entry(data=data, options=options),
    )
    return coordinator, async_update_entry


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
    def test_restore_availability_snapshot_rejects_invalid_shapes(self) -> None:
        for value in (
            {"station_codes": ["STA1"], "measurement_keys": ["STA1"]},
            {"station_codes": [1], "measurement_keys": [["STA1", "PM25"]]},
        ):
            with self.subTest(value=value):
                self.assertIsNone(snapshots_module.restore_availability_snapshot(value))

    async def test_refresh_stations_caches_within_one_day(self) -> None:
        coordinator, _async_update_entry = make_coordinator()

        with (
            patch.object(
                fetch_module,
                "urlopen",
                return_value=make_response(STATION_PAYLOAD),
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
        self.assertEqual({"STA1", "STA2"}, set(coordinator._cached_stations))

    async def test_refresh_stations_raises_without_cached_data(self) -> None:
        coordinator, _async_update_entry = make_coordinator()

        with (
            patch.object(
                fetch_module, "urlopen", side_effect=RuntimeError("network down")
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
            self.assertRaises(coordinator_module.UpdateFailed),
        ):
            await coordinator.async_refresh_stations(force=True)

    async def test_refresh_stations_keeps_cached_data_on_failure(self) -> None:
        coordinator, _async_update_entry = make_coordinator()
        coordinator._cached_stations = {
            "STA1": make_station(
                code="STA1",
                name="Station Alpha",
                district=3,
                latitude=48.21,
                longitude=16.31,
            )
        }

        with (
            patch.object(
                fetch_module, "urlopen", side_effect=RuntimeError("network down")
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
        ):
            refreshed = await coordinator.async_refresh_stations(force=True)

        self.assertFalse(refreshed)
        self.assertEqual({"STA1"}, set(coordinator._cached_stations))

    async def test_refresh_stations_persists_station_snapshot(self) -> None:
        coordinator, async_update_entry = make_coordinator()

        with (
            patch.object(
                fetch_module, "urlopen", return_value=make_response(STATION_PAYLOAD)
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
        ):
            refreshed = await coordinator.async_refresh_stations(force=True)

        self.assertTrue(refreshed)
        self.assertEqual(
            snapshots_module.build_station_snapshot(coordinator._cached_stations),
            coordinator.config_entry.data[coordinator_module.STATION_SNAPSHOT],
        )
        async_update_entry.assert_called_once()

    async def test_async_setup_loads_cached_station_snapshot(self) -> None:
        cached_stations = {
            "STA1": make_station(
                code="STA1",
                name="Station Alpha",
                district=3,
                latitude=48.21,
                longitude=16.31,
                station_url="https://example.test/stations/sta1",
            )
        }
        snapshot = snapshots_module.build_station_snapshot(cached_stations)
        coordinator, _async_update_entry = make_coordinator(
            data={coordinator_module.STATION_SNAPSHOT: snapshot}
        )

        with (
            patch.object(
                fetch_module, "urlopen", side_effect=RuntimeError("network down")
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
        ):
            await coordinator._async_setup()

        self.assertEqual(cached_stations, coordinator._cached_stations)

    async def test_update_data_logs_unknown_station_codes(self) -> None:
        coordinator, _async_update_entry = make_coordinator()

        with (
            patch.object(
                fetch_module,
                "urlopen",
                side_effect=[
                    make_response(STATION_PAYLOAD),
                    make_response(LUMES_FIXTURE.read_bytes()),
                ],
            ) as urlopen_mock,
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
            self.assertLogs(coordinator_module.LOGGER.name, level="WARNING") as logs,
        ):
            data = await coordinator._async_update_data()

        self.assertIsInstance(data, IntegrationData)
        self.assertIn("unknown station code STA3", "\n".join(logs.output))
        self.assertIn("STA3", {key[0] for key in data.measurements})
        self.assertEqual(2, urlopen_mock.call_count)

    def test_log_new_source_items_uses_saved_snapshot(self) -> None:
        base_stations = {
            "STA1": make_station(
                code="STA1",
                name="Station Alpha",
                district=3,
                latitude=48.21,
                longitude=16.31,
            ),
            "STA2": make_station(
                code="STA2",
                name="Station Beta",
                district=4,
                latitude=48.22,
                longitude=16.32,
            ),
        }
        base_measurements = {
            ("STA1", "PM25"): make_metric(12.3, "1MW"),
            ("STA2", "O3"): make_metric(4.5, "HMW"),
        }
        expanded_stations = base_stations | {
            "STA3": make_station(
                code="STA3",
                name="Station Gamma",
                district=5,
                latitude=48.23,
                longitude=16.33,
            )
        }
        expanded_measurements = base_measurements | {
            ("STA3", "PM25"): make_metric(3.2, "1MW"),
            ("STA1", "O3"): make_metric(6.7, "HMW"),
        }
        base_data = IntegrationData(
            stations=base_stations,
            measurements=base_measurements,
        )
        expanded_data = IntegrationData(
            stations=expanded_stations,
            measurements=expanded_measurements,
        )
        coordinator, _async_update_entry = make_coordinator(
            data={
                coordinator_module.SOURCE_SNAPSHOT: (
                    snapshots_module.build_availability_snapshot(base_data)
                )
            }
        )
        coordinator._cached_stations = expanded_stations

        with self.assertLogs(
            coordinator_module.LOGGER.name, level="INFO"
        ) as first_logs:
            coordinator._log_new_source_items(expanded_data)
        with self.assertLogs(
            coordinator_module.LOGGER.name, level="INFO"
        ) as second_logs:
            coordinator._log_new_source_items(expanded_data)

        coordinator.config_entry.options = {
            coordinator_module.SOURCE_SNAPSHOT: (
                snapshots_module.build_availability_snapshot(expanded_data)
            )
        }
        with self.assertNoLogs(coordinator_module.LOGGER.name, level="INFO"):
            coordinator._log_new_source_items(expanded_data)

        self.assertIn("1 new station(s)", first_logs.output[0])
        self.assertIn("2 new station/measurement combination(s)", first_logs.output[0])
        self.assertIn("1 new station(s)", second_logs.output[0])

    async def test_update_data_changes_when_measurements_turn_stale(self) -> None:
        coordinator, _async_update_entry = make_coordinator()
        first_poll = datetime(2026, 6, 24, 21, 30, tzinfo=UTC)
        second_poll = datetime(2026, 6, 24, 22, 0, tzinfo=UTC)
        third_poll = datetime(2026, 6, 24, 23, 0, tzinfo=UTC)

        with (
            patch.object(
                fetch_module,
                "urlopen",
                side_effect=[
                    make_response(STATION_PAYLOAD),
                    make_response(LUMES_FIXTURE.read_bytes()),
                    make_response(LUMES_FIXTURE.read_bytes()),
                    make_response(LUMES_FIXTURE.read_bytes()),
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
        coordinator, _async_update_entry = make_coordinator()

        with (
            patch.object(
                fetch_module,
                "urlopen",
                side_effect=[
                    make_response(STATION_PAYLOAD),
                    RuntimeError("measurement feed down"),
                ],
            ),
            patch.object(coordinator_module.dt_util, "utcnow", return_value=NOW),
            self.assertRaises(coordinator_module.UpdateFailed),
        ):
            await coordinator._async_update_data()

    def test_snapshot_parsers_reject_invalid_values(self) -> None:
        for value in (
            None,
            {"station_codes": "STA1", "measurement_keys": []},
            {"station_codes": [], "measurement_keys": "bad"},
            {"station_codes": ["STA1"], "measurement_keys": [["STA1"]]},
            {"station_codes": ["STA1"], "measurement_keys": [["STA1", "PM25", "x"]]},
            {"station_codes": ["STA1"], "measurement_keys": [["STA1", 25]]},
        ):
            with self.subTest(parser="source", value=value):
                self.assertIsNone(snapshots_module.restore_availability_snapshot(value))

        for value in (None, {"STA1": {"name": 123}}):
            with self.subTest(parser="station", value=value):
                self.assertIsNone(snapshots_module.restore_station_snapshot(value))

    def test_restore_station_snapshot_rejects_invalid_entry_types(self) -> None:
        base = {
            "code": "STA1",
            "name": "Station Alpha",
            "district": 3,
            "latitude": 48.21,
            "longitude": 16.31,
            "station_url": "https://example.test/stations/sta1",
        }

        for changes in (
            {"district": "3"},
            {"latitude": "48.21"},
            {"longitude": "16.31"},
            {"station_url": 123},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(
                    snapshots_module.restore_station_snapshot(
                        {
                            "STA1": base | changes,
                        }
                    )
                )

    def test_station_snapshot_roundtrip(self) -> None:
        stations = {
            "STA1": make_station(
                code="STA1",
                name="Station Alpha",
                district=3,
                latitude=48.21,
                longitude=16.31,
                station_url="https://example.test/stations/sta1",
            ),
            "STA2": make_station(
                code="STA2",
                name="Station Beta",
                district=None,
                latitude=None,
                longitude=None,
                station_url=None,
            ),
        }

        self.assertEqual(
            stations,
            snapshots_module.restore_station_snapshot(
                snapshots_module.build_station_snapshot(stations)
            ),
        )

    def test_source_snapshot_keeps_only_usable_measurements(self) -> None:
        self.assertEqual(
            {
                "station_codes": ["STA1"],
                "measurement_keys": [["STA1", "PM25"]],
            },
            snapshots_module.build_availability_snapshot(
                IntegrationData(
                    stations={
                        "STA1": make_station(
                            code="STA1",
                            name="Station Alpha",
                            district=3,
                            latitude=48.21,
                            longitude=16.31,
                        )
                    },
                    measurements={
                        ("STA1", "PM25"): make_metric(12.3, "1MW"),
                        ("STA1", "O3"): make_metric(None, "HMW"),
                        ("STA1", "NO2"): make_metric(5.0, None),
                        ("STA2", "PM25"): make_metric(7.0, "1MW"),
                        ("STA1", "ZZ"): make_metric(4.0, "1MW"),
                    },
                )
            ),
        )

    async def test_async_fetch_stations_raises_on_invalid_response(self) -> None:
        with (
            patch.object(fetch_module, "_fetch_payload", return_value=b"{}"),
            patch.object(fetch_module, "parse_station_geojson", return_value={}),
            self.assertRaises(exceptions_module.FlowFetchError) as err,
        ):
            await fetch_module.async_fetch_stations(make_hass())

        self.assertEqual("invalid_response", err.exception.reason)
        self.assertEqual({"url": STATIONS_URL}, err.exception.placeholders)

    async def test_async_fetch_measurements_wraps_parser_error(self) -> None:
        with (
            patch.object(fetch_module, "_fetch_payload", return_value=b"{}"),
            patch.object(
                fetch_module, "parse_lumes_csv", side_effect=ValueError("bad csv")
            ),
            self.assertRaises(exceptions_module.FlowFetchError) as err,
        ):
            await fetch_module.async_fetch_measurements(make_hass())

        self.assertEqual("invalid_response", err.exception.reason)
        self.assertEqual({"url": MEASUREMENTS_URL}, err.exception.placeholders)

    async def test_async_fetch_reraises_flow_fetch_error(self) -> None:
        for fetch, expected_url in (
            (fetch_module.async_fetch_stations, STATIONS_URL),
            (fetch_module.async_fetch_measurements, MEASUREMENTS_URL),
        ):
            with self.subTest(fetch=fetch.__name__):
                with (
                    patch.object(
                        fetch_module,
                        "_fetch_payload",
                        side_effect=exceptions_module.FlowFetchError(
                            "cannot_connect", {"url": expected_url}
                        ),
                    ),
                    self.assertRaises(exceptions_module.FlowFetchError) as err,
                ):
                    await fetch(make_hass())
                self.assertEqual("cannot_connect", err.exception.reason)

    def test_stale_measurement_keys_marks_only_old_values(self) -> None:
        self.assertEqual(
            frozenset({("STA1", "O3")}),
            coordinator_module._stale_measurement_keys(
                {
                    ("STA1", "PM25"): make_metric(
                        1.0,
                        "1MW",
                        measured_at=NOW - timedelta(minutes=1),
                    ),
                    ("STA1", "O3"): make_metric(
                        2.0,
                        "1MW",
                        measured_at=NOW
                        - coordinator_module.STALE_AFTER
                        - timedelta(seconds=1),
                    ),
                },
                NOW,
            ),
        )
