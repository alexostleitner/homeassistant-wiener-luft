"""Regression tests for package setup and unload wiring."""

from __future__ import annotations

import types
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

import custom_components.wiener_luft as integration_module  # noqa: E402


class IntegrationSetupTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_and_unload_manage_runtime_data(self) -> None:
        coordinator = types.SimpleNamespace(refreshed=False)

        async def first_refresh() -> None:
            coordinator.refreshed = True

        coordinator.async_config_entry_first_refresh = first_refresh
        hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(
                async_forward_entry_setups=AsyncMock(return_value=True),
                async_unload_platforms=AsyncMock(return_value=True),
            )
        )
        entry = types.SimpleNamespace(runtime_data=None)

        with patch.object(
            integration_module,
            "IntegrationCoordinator",
            return_value=coordinator,
        ):
            self.assertTrue(await integration_module.async_setup_entry(hass, entry))

        self.assertIs(entry.runtime_data, coordinator)
        self.assertTrue(coordinator.refreshed)
        hass.config_entries.async_forward_entry_setups.assert_awaited_once()

        self.assertTrue(await integration_module.async_unload_entry(hass, entry))
        self.assertIsNone(entry.runtime_data)
        hass.config_entries.async_unload_platforms.assert_awaited_once()

    async def test_migrate_entry_updates_sensor_ids(self) -> None:
        registry = types.SimpleNamespace(
            entries=[
                types.SimpleNamespace(
                    config_entry_id="entry-1",
                    domain="sensor",
                    platform="wiener_luft",
                    entity_id="sensor.wiener_luft_temperature_station_1",
                    unique_id="wiener_luft_sta1_ltm",
                ),
                types.SimpleNamespace(
                    config_entry_id="entry-1",
                    domain="sensor",
                    platform="wiener_luft",
                    entity_id="sensor.wiener_luft_pm25_station_1",
                    unique_id="wiener_luft_sta1_pm25",
                ),
                types.SimpleNamespace(
                    config_entry_id="entry-1",
                    domain="button",
                    platform="wiener_luft",
                    entity_id="button.wiener_luft_refresh",
                    unique_id="wiener_luft_refresh",
                ),
            ],
            async_update_entity=MagicMock(),
        )
        hass = types.SimpleNamespace(
            entity_registry=registry,
            config_entries=types.SimpleNamespace(
                async_update_entry=MagicMock(),
            ),
        )
        entry = types.SimpleNamespace(
            entry_id="entry-1",
            version=1,
            minor_version=1,
        )

        with patch.object(integration_module.LOGGER, "warning") as warning_mock:
            self.assertTrue(await integration_module.async_migrate_entry(hass, entry))
        self.assertEqual(
            [
                call(
                    "sensor.wiener_luft_temperature_station_1",
                    new_unique_id="wiener_luft_temperature_sta1",
                    new_entity_id="sensor.wiener_luft_temperature_sta1",
                ),
                call(
                    "sensor.wiener_luft_pm25_station_1",
                    new_unique_id="wiener_luft_pm25_sta1",
                    new_entity_id="sensor.wiener_luft_pm25_sta1",
                ),
            ],
            registry.async_update_entity.call_args_list,
        )
        self.assertEqual(
            [
                call(
                    "Migrating entity registry entry %s: unique_id %s -> %s, entity_id %s -> %s",
                    "sensor.wiener_luft_temperature_station_1",
                    "wiener_luft_sta1_ltm",
                    "wiener_luft_temperature_sta1",
                    "sensor.wiener_luft_temperature_station_1",
                    "sensor.wiener_luft_temperature_sta1",
                ),
                call(
                    "Migrating entity registry entry %s: unique_id %s -> %s, entity_id %s -> %s",
                    "sensor.wiener_luft_pm25_station_1",
                    "wiener_luft_sta1_pm25",
                    "wiener_luft_pm25_sta1",
                    "sensor.wiener_luft_pm25_station_1",
                    "sensor.wiener_luft_pm25_sta1",
                ),
            ],
            warning_mock.call_args_list,
        )
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry, minor_version=2
        )

    async def test_migrate_entry_skips_current_minor_version(self) -> None:
        registry = types.SimpleNamespace(
            entries=[
                types.SimpleNamespace(
                    config_entry_id="entry-1",
                    domain="sensor",
                    platform="wiener_luft",
                    entity_id="sensor.wiener_luft_temperature_station_1",
                    unique_id="wiener_luft_sta1_ltm",
                )
            ],
            async_update_entity=MagicMock(),
        )
        hass = types.SimpleNamespace(
            entity_registry=registry,
            config_entries=types.SimpleNamespace(
                async_update_entry=MagicMock(),
            ),
        )
        entry = types.SimpleNamespace(
            entry_id="entry-1",
            version=1,
            minor_version=2,
        )

        self.assertTrue(await integration_module.async_migrate_entry(hass, entry))
        registry.async_update_entity.assert_not_called()
        hass.config_entries.async_update_entry.assert_not_called()
