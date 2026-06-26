"""Measurement specs and source priority rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    """Metadata for one measurement."""

    name: str
    unit: str
    device_class: str | None = None

MEASUREMENT_SPECS: dict[str, MeasurementSpec] = {
    "PM25": MeasurementSpec(
        name="PM2.5",
        unit="µg/m³",
        device_class="PM25",
    ),
    "PM10": MeasurementSpec(
        name="PM10",
        unit="µg/m³",
        device_class="PM10",
    ),
    "NO2": MeasurementSpec(
        name="NO2",
        unit="µg/m³",
        device_class="NITROGEN_DIOXIDE",
    ),
    "O3": MeasurementSpec(
        name="O3",
        unit="µg/m³",
        device_class="OZONE",
    ),
    "NOX": MeasurementSpec(
        name="NOX",
        unit="µg/m³",
    ),
    "SO2": MeasurementSpec(
        name="SO2",
        unit="µg/m³",
        device_class="SULPHUR_DIOXIDE",
    ),
    "CO": MeasurementSpec(
        name="CO",
        unit="mg/m³",
        device_class="CO",
    ),
    "LTM": MeasurementSpec(
        name="Air temperature",
        unit="°C",
        device_class="TEMPERATURE",
    ),
    "RF": MeasurementSpec(
        name="Relative humidity",
        unit="%",
        device_class="HUMIDITY",
    ),
    "WG": MeasurementSpec(
        name="Wind speed",
        unit="km/h",
        device_class="WIND_SPEED",
    ),
    "WR": MeasurementSpec(
        name="Wind direction",
        unit="°",
        device_class="WIND_DIRECTION",
    ),
}
MEASUREMENT_PRIORITY = ("HMW", "1MW", "MW8", "MW24")
MISSING_VALUES = frozenset({"", "NE", "-999", "—","---", "⸻"})
