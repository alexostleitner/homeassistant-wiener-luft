"""Measurement specs and source priority rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    """Metadata for one measurement."""

    translation_key: str
    unit: str
    device_class: str | None = None
    state_class: str = "MEASUREMENT"
    icon: str | None = None
    entity_id_slug: str | None = None

MEASUREMENT_SPECS: dict[str, MeasurementSpec] = {
    "PM25": MeasurementSpec(
        translation_key="pm25",
        unit="µg/m³",
        device_class="PM25",
    ),
    "PM10": MeasurementSpec(
        translation_key="pm10",
        unit="µg/m³",
        device_class="PM10",
    ),
    "NO2": MeasurementSpec(
        translation_key="no2",
        unit="µg/m³",
        device_class="NITROGEN_DIOXIDE",
    ),
    "O3": MeasurementSpec(
        translation_key="o3",
        unit="µg/m³",
        device_class="OZONE",
    ),
    "NOX": MeasurementSpec(
        translation_key="nox",
        unit="µg/m³",
        icon="mdi:molecule",
    ),
    "SO2": MeasurementSpec(
        translation_key="so2",
        unit="µg/m³",
        device_class="SULPHUR_DIOXIDE",
    ),
    "CO": MeasurementSpec(
        translation_key="co",
        unit="mg/m³",
        device_class="CO",
    ),
    "LTM": MeasurementSpec(
        translation_key="temperature",
        unit="°C",
        device_class="TEMPERATURE",
        entity_id_slug="temperature",
    ),
    "RF": MeasurementSpec(
        translation_key="humidity",
        unit="%",
        device_class="HUMIDITY",
        entity_id_slug="humidity",
    ),
    "WG": MeasurementSpec(
        translation_key="wind_speed",
        unit="km/h",
        device_class="WIND_SPEED",
        entity_id_slug="wind_speed",
    ),
    "WR": MeasurementSpec(
        translation_key="wind_direction",
        unit="°",
        device_class="WIND_DIRECTION",
        state_class="MEASUREMENT_ANGLE",
        entity_id_slug="wind_direction",
    ),
}
MEASUREMENT_PRIORITY = ("HMW", "1MW", "MW8", "MW24")
MISSING_VALUES = frozenset({"", "NE", "-999", "—","---", "⸻"})
