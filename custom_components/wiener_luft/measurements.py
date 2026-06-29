"""Measurement specs and source priority rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    """Metadata for one measurement."""

    translation_key: str
    measurement_slug: str
    unit: str
    device_class: str | None = None
    state_class: str = "MEASUREMENT"
    icon: str | None = None


DISPLAY_PRECISION_BY_UNIT: dict[str, int] = {
    "μg/m³": 1,
    "mg/m³": 2,
    "°C": 1,
    "%": 0,
    "km/h": 1,
    "°": 0,
}

MEASUREMENT_SPECS: dict[str, MeasurementSpec] = {
    "PM25": MeasurementSpec(
        translation_key="pm25",
        measurement_slug="pm25",
        unit="μg/m³",
        device_class="PM25",
    ),
    "PM10": MeasurementSpec(
        translation_key="pm10",
        measurement_slug="pm10",
        unit="μg/m³",
        device_class="PM10",
    ),
    "NO2": MeasurementSpec(
        translation_key="no2",
        measurement_slug="no2",
        unit="μg/m³",
        device_class="NITROGEN_DIOXIDE",
    ),
    "O3": MeasurementSpec(
        translation_key="o3",
        measurement_slug="o3",
        unit="μg/m³",
        device_class="OZONE",
    ),
    "NOX": MeasurementSpec(
        translation_key="nox",
        measurement_slug="nox",
        unit="μg/m³",
        icon="mdi:molecule",
    ),
    "SO2": MeasurementSpec(
        translation_key="so2",
        measurement_slug="so2",
        unit="μg/m³",
        device_class="SULPHUR_DIOXIDE",
    ),
    "CO": MeasurementSpec(
        translation_key="co",
        measurement_slug="co",
        unit="mg/m³",
        device_class="CO",
    ),
    "LTM": MeasurementSpec(
        translation_key="temperature",
        measurement_slug="temperature",
        unit="°C",
        device_class="TEMPERATURE",
    ),
    "RF": MeasurementSpec(
        translation_key="humidity",
        measurement_slug="humidity",
        unit="%",
        device_class="HUMIDITY",
    ),
    "WG": MeasurementSpec(
        translation_key="wind_speed",
        measurement_slug="wind_speed",
        unit="km/h",
        device_class="WIND_SPEED",
    ),
    "WR": MeasurementSpec(
        translation_key="wind_direction",
        measurement_slug="wind_direction",
        unit="°",
        device_class="WIND_DIRECTION",
        state_class="MEASUREMENT_ANGLE",
    ),
}
MEASUREMENT_PRIORITY = ("HMW", "1MW", "MW8", "MW24")
MISSING_VALUES = frozenset({"", "NE", "-999", "—","---", "⸻"})
