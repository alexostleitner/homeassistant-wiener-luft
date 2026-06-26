"""UI config flow for setup."""

from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN, NAME


class IntegrationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup via the UI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initiated from the UI."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=NAME, data={})
