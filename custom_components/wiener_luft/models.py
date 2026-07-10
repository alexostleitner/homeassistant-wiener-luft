"""Shared integration data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from .measurements import MEASUREMENT_SPECS, MeasurementKey, SelectedMeasurements
from .station import Station

type AvailabilityItems = tuple[set[str], set[MeasurementKey]]


class SourceSnapshot(TypedDict):
    """Serialized source snapshot stored in config entry data or options."""

    station_codes: list[str]
    measurement_keys: list[list[str]]


@dataclass(frozen=True, slots=True)
class IntegrationData:
    """Normalized data exposed to entities."""

    stations: dict[str, Station]
    measurements: SelectedMeasurements
    stale_measurements: frozenset[MeasurementKey] = field(default_factory=frozenset)

    def availability_items(self) -> AvailabilityItems:
        """Return the currently available station and measurement keys."""

        return (
            set(self.stations),
            {
                (station_code, measurement_code)
                for (
                    station_code,
                    measurement_code,
                ), reading in self.measurements.items()
                if station_code in self.stations
                and measurement_code in MEASUREMENT_SPECS
                and reading.value is not None
                and reading.measurement_type is not None
            },
        )

    def unknown_station_codes(self) -> tuple[str, ...]:
        """Return measurement station codes that are missing from metadata."""

        return tuple(
            station_code
            for station_code in dict.fromkeys(
                station_code for station_code, _measurement_code in self.measurements
            )
            if station_code not in self.stations
        )
