"""Measurement specs and source priority rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    """Metadata for one measurement."""

    translation_key: str
    entity_id_slug: str
    unit: str
    device_class: str | None = None
    state_class: str = "MEASUREMENT"
    icon: str | None = None

MEASUREMENT_SPECS: dict[str, MeasurementSpec] = {
    "PM25": MeasurementSpec(
        translation_key="pm25",
        entity_id_slug="pm25",
        unit="µg/m³",
        device_class="PM25",
    ),
    "PM10": MeasurementSpec(
        translation_key="pm10",
        entity_id_slug="pm10",
        unit="µg/m³",
        device_class="PM10",
    ),
    "NO2": MeasurementSpec(
        translation_key="no2",
        entity_id_slug="no2",
        unit="µg/m³",
        device_class="NITROGEN_DIOXIDE",
    ),
    "O3": MeasurementSpec(
        translation_key="o3",
        entity_id_slug="o3",
        unit="µg/m³",
        device_class="OZONE",
    ),
    "NOX": MeasurementSpec(
        translation_key="nox",
        entity_id_slug="nox",
        unit="µg/m³",
        icon="mdi:molecule",
    ),
    "SO2": MeasurementSpec(
        translation_key="so2",
        entity_id_slug="so2",
        unit="µg/m³",
        device_class="SULPHUR_DIOXIDE",
    ),
    "CO": MeasurementSpec(
        translation_key="co",
        entity_id_slug="co",
        unit="mg/m³",
        device_class="CO",
    ),
    "LTM": MeasurementSpec(
        translation_key="temperature",
        entity_id_slug="temperature",
        unit="°C",
        device_class="TEMPERATURE",
    ),
    "RF": MeasurementSpec(
        translation_key="humidity",
        entity_id_slug="humidity",
        unit="%",
        device_class="HUMIDITY",
    ),
    "WG": MeasurementSpec(
        translation_key="wind_speed",
        entity_id_slug="wind_speed",
        unit="km/h",
        device_class="WIND_SPEED",
    ),
    "WR": MeasurementSpec(
        translation_key="wind_direction",
        entity_id_slug="wind_direction",
        unit="°",
        device_class="WIND_DIRECTION",
        state_class="MEASUREMENT_ANGLE",
    ),
}
MEASUREMENT_PRIORITY = ("HMW", "1MW", "MW8", "MW24")
MISSING_VALUES = frozenset({"", "NE", "-999", "—","---", "⸻"})
