"""Parsers and normalized data models for measurement payloads."""

from __future__ import annotations

import csv
import logging
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone, tzinfo

from .measurements import (
    MEASUREMENT_PRIORITY,
    MEASUREMENT_SPECS,
)
from .parsing import MISSING_VALUES, decode_payload, is_missing_number, parse_number

LOGGER = logging.getLogger(__name__)
TIMEZONES: dict[str, tzinfo] = {
    "UTC": UTC,
    "MEZ": timezone(timedelta(hours=1), name="MEZ"),
    "MESZ": timezone(timedelta(hours=2), name="MESZ"),
    "CET": timezone(timedelta(hours=1), name="CET"),
    "CEST": timezone(timedelta(hours=2), name="CEST"),
}
type MeasurementKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class SelectedMetric:
    """Selected measurement value."""

    value: float | None
    unit: str
    measurement_type: str | None
    measured_at: datetime | None


@dataclass(frozen=True, slots=True)
class MeasurementColumn:
    """Header metadata for one measurement value column."""

    value_index: int
    averaging_type: str
    unit: str
    time_index: int | None
    time_zone: str | None


type SelectedMeasurements = dict[MeasurementKey, SelectedMetric]


def parse_lumes_csv(payload: str | bytes) -> SelectedMeasurements:
    """Parse the Lumes v2 CSV and select one reading per station/measurement."""

    text = decode_payload(payload)
    rows = list(csv.reader(text.splitlines(), delimiter=";"))

    component_row, averaging_row, unit_row = _parse_lumes_header(rows)
    columns_by_component = _collect_columns(component_row, averaging_row, unit_row)
    width = len(component_row)
    selected: SelectedMeasurements = {}

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

    return selected


def _choose_column(
    station_code: str,
    component: str,
    row: list[str],
    candidates: list[MeasurementColumn],
) -> MeasurementColumn | None:
    invalid_value: str | int | float | None = None
    for averaging_type in MEASUREMENT_PRIORITY:
        for column in (
            column
            for column in candidates
            if column.averaging_type == averaging_type
        ):
            raw_value = _column_value(row, column)
            if parse_number(raw_value) is not None:
                return column
            if invalid_value is None and not is_missing_number(raw_value):
                invalid_value = raw_value
    if invalid_value is not None:
        LOGGER.warning(
            "Could not parse measurement value %r for station %s component %s",
            invalid_value,
            station_code,
            component,
        )
    return None


def _column_value(row: list[str], column: MeasurementColumn) -> str | None:
    """Return the raw CSV value for one measurement column."""

    return row[column.value_index] if column.value_index < len(row) else None


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
) -> dict[str, list[MeasurementColumn]]:
    columns_by_component: dict[str, list[MeasurementColumn]] = {}
    current_time_index: int | None = None
    current_time_zone: str | None = None
    for index, raw_name in enumerate(component_row):
        name = raw_name.strip()
        if name.startswith("Zeit-"):
            current_time_index = index
            current_time_zone = unit_row[index].strip() or None
            continue

        averaging_type = averaging_row[index].strip()
        if not averaging_type:
            continue

        component = name.strip()
        if component not in MEASUREMENT_SPECS:
            continue

        spec = MEASUREMENT_SPECS[component]
        unit = (
            unit_row[index]
            .strip()
            .replace("\u00b5", unicodedata.normalize("NFKC", "\u00b5"))
            or spec.unit
        )
        columns_by_component.setdefault(component, []).append(
            MeasurementColumn(
                value_index=index,
                averaging_type=averaging_type,
                unit=unit,
                time_index=current_time_index,
                time_zone=current_time_zone,
            )
        )
    return columns_by_component


def _select_row_measurements(
    selected: SelectedMeasurements,
    station_code: str,
    row: list[str],
    columns_by_component: dict[str, list[MeasurementColumn]],
) -> None:
    for component, component_columns in columns_by_component.items():
        chosen_column = _choose_column(station_code, component, row, component_columns)
        selected[(station_code, component)] = _build_selected_metric(
            component,
            row,
            component_columns,
            chosen_column,
        )


def _build_selected_metric(
    component: str,
    row: list[str],
    component_columns: list[MeasurementColumn],
    chosen_column: MeasurementColumn | None,
) -> SelectedMetric:
    """Build the selected metric for one station/component row."""

    unit = component_columns[0].unit or MEASUREMENT_SPECS[component].unit
    if chosen_column is None:
        return SelectedMetric(
            value=None,
            unit=unit,
            measurement_type=None,
            measured_at=None,
        )

    return SelectedMetric(
        value=parse_number(
            row[chosen_column.value_index]
            if chosen_column.value_index < len(row)
            else None
        ),
        unit=chosen_column.unit or unit,
        measurement_type=chosen_column.averaging_type,
        measured_at=_parse_measured_at(row, chosen_column),
    )


def _parse_measured_at(
    row: list[str],
    chosen_column: MeasurementColumn,
) -> datetime | None:
    """Parse the measurement timestamp for one chosen CSV column."""

    measured_at_text = (
        row[chosen_column.time_index]
        if chosen_column.time_index is not None and chosen_column.time_index < len(row)
        else None
    )
    parsed_time_zone = _parse_time_zone(chosen_column.time_zone)
    if measured_at_text is None or parsed_time_zone is None:
        return None

    try:
        return datetime.strptime(measured_at_text, "%d.%m.%Y, %H:%M").replace(
            tzinfo=parsed_time_zone
        )
    except ValueError:
        LOGGER.warning("Could not parse datetime value %r", measured_at_text)
        return None


def _parse_time_zone(time_zone: str | None) -> tzinfo | None:
    """Parse the persisted time zone label for one measurement column."""

    if time_zone is None:
        return None

    time_zone_text = time_zone.strip().upper()
    if not time_zone_text or time_zone_text in MISSING_VALUES:
        return None

    parsed_time_zone = TIMEZONES.get(time_zone_text)
    if parsed_time_zone is None:
        LOGGER.warning("Could not parse timezone value %r", time_zone)
    return parsed_time_zone
