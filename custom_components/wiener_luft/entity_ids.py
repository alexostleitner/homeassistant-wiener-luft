"""Helpers for stable sensor entity and unique IDs."""

from __future__ import annotations

from homeassistant.util import slugify

from .const import DOMAIN
from .measurements import MeasurementSpec


def entity_id_base(measurement_spec: MeasurementSpec, station_code: str) -> str:
    """Return the shared slug used for unique_id and entity_id."""

    return f"{measurement_spec.entity_id_slug}_{slugify(station_code)}"


def sensor_unique_id(measurement_spec: MeasurementSpec, station_code: str) -> str:
    """Return the sensor unique ID for one station/measurement pair."""

    return f"{DOMAIN}_{entity_id_base(measurement_spec, station_code)}"


def sensor_entity_id(measurement_spec: MeasurementSpec, station_code: str) -> str:
    """Return the sensor entity ID for one station/measurement pair."""

    return f"sensor.{DOMAIN}_{entity_id_base(measurement_spec, station_code)}"
