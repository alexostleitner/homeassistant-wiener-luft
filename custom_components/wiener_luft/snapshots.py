"""Helpers for serializing and restoring persisted snapshots."""

from __future__ import annotations

from dataclasses import asdict
from typing import cast

from .models import AvailabilityItems, IntegrationData, SourceSnapshot
from .station import Station


def restore_availability_snapshot(value: object) -> AvailabilityItems | None:
    """Restore the stored availability snapshot from config entry data or options."""

    if not isinstance(value, dict):
        return None

    snapshot = cast(dict[str, object], value)
    station_codes = snapshot.get("station_codes")
    measurement_keys = snapshot.get("measurement_keys")
    if not isinstance(station_codes, list) or not isinstance(measurement_keys, list):
        return None

    station_code_items = cast(list[object], station_codes)
    measurement_key_items = cast(list[object], measurement_keys)

    if not all(isinstance(station_code, str) for station_code in station_code_items):
        return None
    if not all(
        isinstance(item, (list, tuple))
        and len(cast(list[object] | tuple[object, ...], item)) == 2
        and isinstance(item[0], str)
        and isinstance(item[1], str)
        for item in measurement_key_items
    ):
        return None

    previous_station_codes = set(cast(list[str], station_code_items))
    previous_measurement_keys = {
        (item[0], item[1])
        for item in cast(list[list[str] | tuple[str, str]], measurement_key_items)
    }
    return previous_station_codes, previous_measurement_keys


def build_availability_snapshot(integration_data: IntegrationData) -> SourceSnapshot:
    """Serialize the currently available station and measurement keys."""

    station_codes, measurement_keys = integration_data.availability_items()
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

    snapshot = cast(dict[str, object], value)
    stations: dict[str, Station] = {}
    for code, station_data in snapshot.items():
        station = _restore_station_snapshot_entry(code, station_data)
        if station is None:
            return None
        stations[code] = station
    return stations


def _restore_station_snapshot_entry(code: object, value: object) -> Station | None:
    """Restore one persisted station entry."""

    if not isinstance(code, str) or not isinstance(value, dict):
        return None

    station_data = cast(dict[str, object], value)
    stored_code = station_data.get("code", code)
    if stored_code != code:
        return None

    return _restore_station_from_snapshot_data(code, station_data)


# complexipy: ignore
def _restore_station_from_snapshot_data(
    code: str,
    value: dict[str, object],
) -> Station | None:
    """Restore station metadata from one persisted station entry."""

    name = value.get("name")
    district = value.get("district")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    station_url = value.get("station_url")

    if not isinstance(name, str):
        return None
    if district is not None and not isinstance(district, int):
        return None
    if latitude is not None and not isinstance(latitude, (int, float)):
        return None
    if longitude is not None and not isinstance(longitude, (int, float)):
        return None
    if station_url is not None and not isinstance(station_url, str):
        return None

    station_latitude = float(latitude) if latitude is not None else None
    station_longitude = float(longitude) if longitude is not None else None

    return Station(
        code=code,
        name=name,
        district=district,
        latitude=station_latitude,
        longitude=station_longitude,
        station_url=station_url,
    )
