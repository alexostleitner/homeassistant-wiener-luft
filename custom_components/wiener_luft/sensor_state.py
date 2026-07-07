"""Pure sensor state derivation helpers."""

from __future__ import annotations

from .const import CALM_WIND_SPEED_MPS
from .measurements_parser import SelectedMetric


def measurement_native_value(
    measurement_code: str,
    reading: SelectedMetric | None,
    wind_speed_reading: SelectedMetric | None,
) -> float | None:
    """Return the sensor value derived from current coordinator readings."""

    if reading is None:
        return None
    if measurement_code == "WR" and _wind_speed_is_calm(wind_speed_reading):
        return None
    return reading.value


def measurement_availability_state(
    last_update_success: bool,
    reading: SelectedMetric | None,
    is_stale: bool,
) -> str:
    """Return the current availability state for one measurement."""

    if not last_update_success:
        return "coordinator_unavailable"
    if reading is None or reading.value is None:
        return "missing"
    if is_stale:
        return "stale"
    return "available"


def _wind_speed_is_calm(wind_speed_reading: SelectedMetric | None) -> bool:
    """Return whether the latest wind speed should suppress wind direction."""

    if wind_speed_reading is None or wind_speed_reading.value is None:
        return False
    if wind_speed_reading.unit == "m/s":
        return wind_speed_reading.value < CALM_WIND_SPEED_MPS
    if wind_speed_reading.unit == "km/h":
        return wind_speed_reading.value / 3.6 < CALM_WIND_SPEED_MPS
    return False
