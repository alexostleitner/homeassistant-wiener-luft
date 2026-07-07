"""UI config flow for setup and options."""

from __future__ import annotations

from typing import Any, TypedDict

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback

from .config_flow_data import async_fetch_flow_data, async_get_measurement_names
from .config_flow_measurements import build_measurement_schema, measurement_defaults
from .config_flow_stations import (
    build_station_schema,
    recommended_station_count,
    sorted_stations_for_flow,
    station_defaults,
)
from .const import CONF_MEASUREMENTS, CONF_STATIONS, DOMAIN, NAME
from .models import IntegrationData, SourceSnapshot
from .snapshots import build_availability_snapshot


class SavedPreferences(TypedDict):
    """Persisted station and measurement selections for config entries."""

    stations: list[str]
    measurements: list[str]
    _source_snapshot: SourceSnapshot


class IntegrationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup via the UI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""

        self._data: IntegrationData | None = None
        self._selected_stations: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> IntegrationOptionsFlow:
        """Return the options flow for this config entry."""

        return IntegrationOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the station selection step."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        result = await self._async_load_data_or_abort()
        if result is not None:
            return result

        if user_input is None:
            return self._show_station_form()

        self._selected_stations = list(user_input[CONF_STATIONS])
        if not self._selected_stations:
            return self._show_station_form(errors={"base": "station_required"})

        return await self.async_step_measurements()

    async def async_step_measurements(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the measurement selection step."""

        result = await self._async_load_data_or_abort()
        if result is not None:
            return result

        assert self._selected_stations

        if user_input is None:
            return await self._show_measurement_form()

        selected_measurements = list(user_input[CONF_MEASUREMENTS])
        if not selected_measurements:
            return await self._show_measurement_form(
                errors={"base": "measurement_required"}
            )

        assert self._data is not None
        return self.async_create_entry(
            title=NAME,
            data=_build_saved_preferences(
                self._data,
                self._selected_stations,
                selected_measurements,
            ),
        )

    async def _async_load_data_or_abort(self) -> ConfigFlowResult | None:
        """Load current source data or abort with the existing fetch errors."""

        if self._data is not None:
            return None

        self._data, error_key, placeholders = await async_fetch_flow_data(self.hass)
        if error_key is None:
            return None

        return self.async_abort(
            reason=error_key,
            description_placeholders=placeholders,
        )

    def _show_station_form(
        self,
        *,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup station selection form."""

        assert self._data is not None

        station_choices = sorted_stations_for_flow(self._data, self.hass)
        available_codes = [
            station.code for station, _distance_km in station_choices.options
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=build_station_schema(
                station_choices,
                station_defaults(
                    available_codes,
                    recommended_count=recommended_station_count(station_choices),
                ),
            ),
            description_placeholders={"station_count": str(len(available_codes))},
            errors=errors or {},
        )

    async def _show_measurement_form(
        self,
        *,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup measurement selection form."""

        assert self._data is not None
        assert self._selected_stations

        measurement_names = await async_get_measurement_names(self.hass)
        return self.async_show_form(
            step_id="measurements",
            data_schema=build_measurement_schema(
                self._data,
                self._selected_stations,
                measurement_defaults(
                    self._data,
                    self._selected_stations,
                ),
                measurement_names,
            ),
            errors=errors or {},
        )


class IntegrationOptionsFlow(OptionsFlowWithReload):
    """Handle options for an existing config entry."""

    def __init__(self) -> None:
        """Initialize options flow state."""

        self._data: IntegrationData | None = None
        self._selected_stations: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the station selection step for options."""

        result = await self._async_load_data_or_abort()
        if result is not None:
            return result

        if user_input is None:
            return self._show_station_form()

        self._selected_stations = list(user_input[CONF_STATIONS])
        if not self._selected_stations:
            return self._show_station_form(errors={"base": "station_required"})

        return await self.async_step_measurements()

    async def async_step_measurements(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the measurement selection step for options."""

        result = await self._async_load_data_or_abort()
        if result is not None:
            return result

        assert self._selected_stations

        if user_input is None:
            return await self._show_measurement_form()

        selected_measurements = list(user_input[CONF_MEASUREMENTS])
        if not selected_measurements:
            return await self._show_measurement_form(
                errors={"base": "measurement_required"}
            )

        assert self._data is not None
        return self.async_create_entry(
            data=_build_saved_preferences(
                self._data,
                self._selected_stations,
                selected_measurements,
            ),
        )

    def _saved_preferences(self) -> SavedPreferences | None:
        """Return merged saved preferences when both selections are present."""

        preferences = dict(self.config_entry.data)
        preferences.update(self.config_entry.options)
        if CONF_STATIONS not in preferences or CONF_MEASUREMENTS not in preferences:
            return None
        return preferences

    async def _async_load_data_or_abort(self) -> ConfigFlowResult | None:
        """Load current source data or abort with the existing fetch errors."""

        if self._data is not None:
            return None

        self._data, error_key, placeholders = await async_fetch_flow_data(self.hass)
        if error_key is None:
            return None

        return self.async_abort(
            reason=error_key,
            description_placeholders=placeholders,
        )

    def _show_station_form(
        self,
        *,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the options station selection form."""

        assert self._data is not None

        station_choices = sorted_stations_for_flow(self._data, self.hass)
        available_codes = [
            station.code for station, _distance_km in station_choices.options
        ]
        saved_preferences = self._saved_preferences()
        return self.async_show_form(
            step_id="init",
            data_schema=build_station_schema(
                station_choices,
                station_defaults(
                    available_codes,
                    (
                        list(saved_preferences.get(CONF_STATIONS, ()))
                        if saved_preferences is not None
                        else None
                    ),
                    recommended_count=recommended_station_count(station_choices),
                ),
            ),
            errors=errors or {},
        )

    async def _show_measurement_form(
        self,
        *,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the options measurement selection form."""

        assert self._data is not None
        assert self._selected_stations

        measurement_names = await async_get_measurement_names(self.hass)
        saved_preferences = self._saved_preferences()
        return self.async_show_form(
            step_id="measurements",
            data_schema=build_measurement_schema(
                self._data,
                self._selected_stations,
                measurement_defaults(
                    self._data,
                    self._selected_stations,
                    (
                        list(saved_preferences.get(CONF_MEASUREMENTS, ()))
                        if saved_preferences is not None
                        else None
                    ),
                ),
                measurement_names,
            ),
            errors=errors or {},
        )


def _build_saved_preferences(
    integration_data: IntegrationData,
    selected_stations: list[str],
    selected_measurements: list[str],
) -> SavedPreferences:
    """Return the payload saved in config entry data or options."""

    return SavedPreferences(
        stations=selected_stations,
        measurements=selected_measurements,
        _source_snapshot=build_availability_snapshot(
            integration_data.stations,
            integration_data.measurements,
        ),
    )
