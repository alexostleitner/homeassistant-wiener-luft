"""Parsers and normalization helpers for source payloads."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from typing import Any

from .measurements import (
    MEASUREMENT_PRIORITY,
    MEASUREMENT_SPECS,
    MISSING_VALUES,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Station:
    """Station metadata."""

    code: str
    name: str
    district: int | None
    latitude: float | None
    longitude: float | None
    station_url: str | None


@dataclass(frozen=True, slots=True)
class SelectedMetric:
    """Selected measurement value."""

    value: float | None
    unit: str
    measurement_type: str | None


@dataclass(frozen=True, slots=True)
class LumesMeasurements:
    """Parsed measurement data."""

    selected: dict[tuple[str, str], SelectedMetric]


def decode_payload(payload: str | bytes) -> str:
    """Decode source payloads, accepting the Windows-1252 CSV encoding."""

    if isinstance(payload, str):
        return payload

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    return payload.decode("latin-1", errors="replace")


def parse_number(value: str | int | float | None) -> float | None:
    """Parse a source number, treating declared placeholders as missing."""

    if value is None:
        return None
    if isinstance(value, int | float):
        return None if value == -999 else float(value)

    text = value.strip()
    if text.upper() in MISSING_VALUES:
        return None

    try:
        return float(text.replace(",", "."))
    except ValueError:
        LOGGER.warning("Could not parse numeric value %r", value)
        return None


def parse_lumes_csv(payload: str | bytes) -> LumesMeasurements:
    """Parse the Lumes v2 CSV and select one reading per station/measurement."""

    text = decode_payload(payload)
    rows = list(csv.reader(text.splitlines(), delimiter=";"))

    component_row, averaging_row, unit_row = _parse_lumes_header(rows)
    columns_by_component = _collect_columns(component_row, averaging_row, unit_row)
    width = len(component_row)
    selected: dict[tuple[str, str], SelectedMetric] = {}

    for row_number, row in enumerate(rows[4:], start=5):
        if not row or not row[0].strip():
            continue
        station_code = row[0].strip().upper()

        _select_row_measurements(
            selected,
            station_code,
            row,
            columns_by_component,
        )

        if len(row) != width:
            LOGGER.warning(
                "Lumes row %s for station %s has %s columns, expected %s",
                row_number,
                station_code,
                len(row),
                width,
            )

    return LumesMeasurements(selected=selected)


def parse_station_geojson(payload: str | bytes | dict[str, Any]) -> dict[str, Station]:
    """Parse station metadata GeoJSON keyed by NAME_KURZ."""

    data = (
        json.loads(decode_payload(payload))
        if not isinstance(payload, dict)
        else payload
    )
    features = data.get("features")
    if not isinstance(features, list):
        msg = "Station GeoJSON must contain a features list"
        raise ValueError(msg)

    stations: dict[str, Station] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties") or {}
        code = str(properties.get("NAME_KURZ") or "").strip().upper()
        if not code:
            LOGGER.warning("Skipping station feature without NAME_KURZ")
            continue

        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
            longitude = parse_number(coordinates[0])
            latitude = parse_number(coordinates[1])
        else:
            longitude = None
            latitude = None
        district = parse_number(properties.get("BEZIRK"))
        station_url = str(properties.get("URL_INFO") or "").strip() or None
        station = Station(
            code=code,
            name=str(properties.get("NAME") or code).strip(),
            district=int(district) if district is not None else None,
            latitude=latitude,
            longitude=longitude,
            station_url=station_url,
        )
        if code in stations:
            LOGGER.warning("Duplicate station metadata for NAME_KURZ=%s", code)
        stations[code] = station

    return stations


def _choose_column(
    row: list[str], candidates: list[tuple[int, str, str]]
) -> tuple[int, str, str] | None:
    for averaging_type in MEASUREMENT_PRIORITY:
        for column in candidates:
            if column[1] != averaging_type:
                continue
            if (
                parse_number(
                    row[column[0]] if column[0] < len(row) else None
                )
                is not None
            ):
                return column
    return None


def _parse_lumes_header(
    rows: list[list[str]],
) -> tuple[list[str], list[str], list[str]]:
    if len(rows) < 4:
        msg = "Lumes CSV must contain metadata and three header rows"
        raise ValueError(msg)

    _, component_row, averaging_row, unit_row = rows[:4]
    width = len(component_row)
    if len(averaging_row) != width or len(unit_row) != width:
        msg = "Lumes CSV header rows have inconsistent column counts"
        raise ValueError(msg)

    expected_components = set(MEASUREMENT_SPECS)
    actual_components = {
        name
        for name in (raw_name.strip() for raw_name in component_row)
        if name and not name.startswith("Zeit-")
    }
    missing_components = sorted(expected_components - actual_components)
    unexpected_components = sorted(actual_components - expected_components)
    if missing_components or unexpected_components:
        LOGGER.warning(
            "Lumes CSV measurement headers changed: missing=%s unexpected=%s",
            missing_components,
            unexpected_components,
        )

    return component_row, averaging_row, unit_row


def _collect_columns(
    component_row: list[str], averaging_row: list[str], unit_row: list[str]
) -> dict[str, list[tuple[int, str, str]]]:
    columns_by_component: dict[str, list[tuple[int, str, str]]] = {}
    for index, raw_name in enumerate(component_row):
        name = raw_name.strip()
        if name.startswith("Zeit-"):
            continue

        averaging_type = averaging_row[index].strip()
        if not averaging_type:
            continue

        component = name.strip()
        if component not in MEASUREMENT_SPECS:
            continue

        spec = MEASUREMENT_SPECS[component]
        unit = unit_row[index].strip() or spec.unit
        columns_by_component.setdefault(component, []).append(
            (index, averaging_type, unit)
        )
    return columns_by_component


def _select_row_measurements(
    selected: dict[tuple[str, str], SelectedMetric],
    station_code: str,
    row: list[str],
    columns_by_component: dict[str, list[tuple[int, str, str]]],
) -> None:
    for component, component_columns in columns_by_component.items():
        chosen_column = _choose_column(row, component_columns)
        unit = component_columns[0][2] or MEASUREMENT_SPECS[component].unit
        if chosen_column is None:
            selected[(station_code, component)] = SelectedMetric(
                value=None,
                unit=unit,
                measurement_type=None,
            )
            continue

        index, averaging_type, chosen_unit = chosen_column
        selected[(station_code, component)] = SelectedMetric(
            value=parse_number(row[index] if index < len(row) else None),
            unit=chosen_unit or unit,
            measurement_type=averaging_type,
        )
