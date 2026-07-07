"""Availability rules for stations and measurements."""

from __future__ import annotations

from .measurements import MEASUREMENT_SPECS
from .measurements_parser import MeasurementKey, SelectedMeasurements
from .station import Station

type AvailabilityItems = tuple[set[str], set[MeasurementKey]]


def availability_items(
    stations: dict[str, Station],
    measurements: SelectedMeasurements,
) -> AvailabilityItems:
    """Return the currently available station and measurement keys."""

    return (
        set(stations),
        {
            (station_code, component)
            for (station_code, component), reading in measurements.items()
            if station_code in stations
            and component in MEASUREMENT_SPECS
            and reading.value is not None
            and reading.measurement_type is not None
        },
    )


def availability_changes(
    previous: AvailabilityItems,
    current: AvailabilityItems,
) -> AvailabilityItems:
    """Return newly added station and measurement keys."""

    previous_station_codes, previous_measurement_keys = previous
    current_station_codes, current_measurement_keys = current
    return (
        current_station_codes - previous_station_codes,
        current_measurement_keys - previous_measurement_keys,
    )


def unknown_station_codes(
    stations: dict[str, Station],
    measurements: SelectedMeasurements,
) -> tuple[str, ...]:
    """Return measurement station codes that are missing from station metadata."""

    return tuple(
        station_code
        for station_code in dict.fromkeys(
            station_code for station_code, _component in measurements
        )
        if station_code not in stations
    )
