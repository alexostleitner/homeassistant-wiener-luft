"""Shared integration data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from .measurements_parser import MeasurementKey, SelectedMeasurements
from .station import Station

type StaleMeasurements = frozenset[MeasurementKey]


class SourceSnapshot(TypedDict):
    """Serialized source snapshot stored in config entry data or options."""

    station_codes: list[str]
    measurement_keys: list[list[str]]


@dataclass(frozen=True, slots=True)
class IntegrationData:
    """Normalized data exposed to entities."""

    stations: dict[str, Station]
    measurements: SelectedMeasurements
    stale_measurements: StaleMeasurements = field(default_factory=frozenset)
