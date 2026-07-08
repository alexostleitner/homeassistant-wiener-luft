"""Parser for station metadata payloads."""

from __future__ import annotations

import json
import logging
from typing import Any

from .parsing import decode_payload, is_missing_number, parse_number
from .station import Station

LOGGER = logging.getLogger(__name__)


def parse_station_geojson(payload: str | bytes | dict[str, Any]) -> dict[str, Station]:
    """Parse station metadata GeoJSON keyed by NAME_KURZ."""

    data = payload if isinstance(payload, dict) else json.loads(decode_payload(payload))
    features = data.get("features")
    if not isinstance(features, list):
        msg = "Station GeoJSON must contain a features list"
        raise ValueError(msg)

    stations: dict[str, Station] = {}
    for feature in features:
        feature_data = _station_feature_data(feature)
        if feature_data is None:
            continue
        code, station = feature_data
        if code in stations:
            LOGGER.warning("Duplicate station metadata for NAME_KURZ=%s", code)
        stations[code] = station

    return stations


def _station_feature_data(feature: Any) -> tuple[str, Station] | None:
    if not isinstance(feature, dict):
        return None

    properties = feature.get("properties") or {}
    code = str(properties.get("NAME_KURZ") or "").strip().upper()
    if not code:
        LOGGER.warning("Skipping station feature without NAME_KURZ")
        return None

    return code, _station_from_feature(feature, properties, code)


def _station_from_feature(
    feature: dict[str, Any], properties: Any, code: str
) -> Station:
    longitude, latitude = _coordinates_from_feature(feature, code)
    district = _parse_station_number(
        properties.get("BEZIRK"), code=code, field="BEZIRK"
    )
    return Station(
        code=code,
        name=str(properties.get("NAME") or code).strip(),
        district=int(district) if district is not None else None,
        latitude=latitude,
        longitude=longitude,
        station_url=str(properties.get("URL_INFO") or "").strip() or None,
    )


def _coordinates_from_feature(
    feature: dict[str, Any],
    code: str,
) -> tuple[float | None, float | None]:
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        return None, None

    longitude = _parse_station_number(coordinates[0], code=code, field="longitude")
    latitude = _parse_station_number(coordinates[1], code=code, field="latitude")
    return longitude, latitude


def _parse_station_number(
    value: str | int | float | None, *, code: str, field: str
) -> float | None:
    parsed = parse_number(value)
    if parsed is None and not is_missing_number(value):
        LOGGER.warning(
            "Could not parse station %s value %r for %s",
            field,
            value,
            code,
        )
    return parsed
