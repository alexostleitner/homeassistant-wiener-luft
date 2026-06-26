"""Shared helpers for decoding and parsing source payloads."""

from __future__ import annotations

import logging

from .measurements import MISSING_VALUES

LOGGER = logging.getLogger(__name__)


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
