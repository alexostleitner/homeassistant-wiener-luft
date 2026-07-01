"""Regression tests for package setup and unload wiring."""

from __future__ import annotations

import types
import unittest
from unittest.mock import AsyncMock, patch

from homeassistant_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

import custom_components.wiener_luft as integration_module  # noqa: E402


class IntegrationSetupTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_and_unload_manage_runtime_data(self) -> None:
        coordinator = types.SimpleNamespace(refreshed=False)

        async def first_refresh() -> None:
            coordinator.refreshed = True

        coordinator.async_config_entry_first_refresh = first_refresh
        coordinator.data = types.SimpleNamespace(stations={}, measurements={})
        hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(
                async_forward_entry_setups=AsyncMock(return_value=True),
                async_unload_platforms=AsyncMock(return_value=True),
            )
        )
        entry = types.SimpleNamespace(runtime_data=None, data={}, options={})

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
