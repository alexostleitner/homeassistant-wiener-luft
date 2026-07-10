"""Station model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Station:
    """Station metadata."""

    code: str
    name: str
    district: int | None
    latitude: float | None
    longitude: float | None
    station_url: str | None
