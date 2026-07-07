"""Helpers for serializing and restoring persisted snapshots."""

from __future__ import annotations

from dataclasses import asdict

from .measurements import MEASUREMENT_SPECS
from .measurements_parser import MeasurementKey, SelectedMeasurements
from .models import SourceSnapshot
from .station import Station

type AvailabilityItems = tuple[set[str], set[MeasurementKey]]


def restore_availability_snapshot(value: object) -> AvailabilityItems | None:
    """Restore the stored availability snapshot from config entry data or options."""

    if not isinstance(value, dict):
        return None

    station_codes = value.get("station_codes")
    measurement_keys = value.get("measurement_keys")
    if not isinstance(station_codes, list) or not isinstance(measurement_keys, list):
        return None

    if any(not isinstance(item, (list, tuple)) for item in measurement_keys):
        return None

    previous_station_codes = set(station_codes)
    previous_measurement_keys = {tuple(item) for item in measurement_keys}
    if any(
        not isinstance(station_code, str) for station_code in previous_station_codes
    ):
        return None
    if any(
        len(item) != 2 or not isinstance(item[0], str) or not isinstance(item[1], str)
        for item in previous_measurement_keys
    ):
        return None

    return previous_station_codes, previous_measurement_keys


def _availability_items(
    stations: dict[str, Station],
    measurements: SelectedMeasurements,
) -> AvailabilityItems:
    """Return the currently available station and measurement keys."""

    current_station_codes = set(stations)
    current_measurement_keys = {
        (station_code, component)
        for (station_code, component), reading in measurements.items()
        if station_code in stations
        and component in MEASUREMENT_SPECS
        and reading.value is not None
        and reading.measurement_type is not None
    }
    return current_station_codes, current_measurement_keys


def build_availability_snapshot(
    stations: dict[str, Station],
    measurements: SelectedMeasurements,
) -> SourceSnapshot:
    """Serialize the currently available station and measurement keys."""

    station_codes, measurement_keys = _availability_items(stations, measurements)
    return SourceSnapshot(
        station_codes=sorted(station_codes),
        measurement_keys=[list(item) for item in sorted(measurement_keys)],
    )


def build_station_snapshot(
    stations: dict[str, Station],
) -> dict[str, dict[str, object]]:
    """Serialize station metadata for persistence."""

    return {code: asdict(station) for code, station in sorted(stations.items())}


def restore_station_snapshot(value: object) -> dict[str, Station] | None:
    """Restore a persisted station snapshot."""

    if not isinstance(value, dict):
        return None

    stations: dict[str, Station] = {}
    for code, station_data in value.items():
        station = _restore_station_snapshot_entry(code, station_data)
        if station is None:
            return None
        stations[code] = station
    return stations


def _restore_station_snapshot_entry(code: object, value: object) -> Station | None:
    """Restore one persisted station entry."""

    if not isinstance(code, str) or not isinstance(value, dict):
        return None

    stored_code = value.get("code", code)
    name = value.get("name")
    district = value.get("district")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    station_url = value.get("station_url")
    if stored_code != code or not isinstance(name, str):
        return None
    if district is not None and not isinstance(district, int):
        return None
    if latitude is not None and not isinstance(latitude, (int, float)):
        return None
    if longitude is not None and not isinstance(longitude, (int, float)):
        return None
    if station_url is not None and not isinstance(station_url, str):
        return None

    return Station(
        code=code,
        name=name,
        district=district,
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        station_url=station_url,
    )
