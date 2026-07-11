"""Shared helpers for decoding and parsing source payloads."""

from __future__ import annotations

MISSING_VALUES = frozenset({"", "NE", "-999", "—", "---", "⸻"})


def decode_payload(payload: str | bytes) -> str:
    """Decode source payloads, accepting the Windows-1252 CSV encoding."""

    if isinstance(payload, str):
        return payload

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue


def parse_number(value: str | int | float | None) -> float | None:
    """Parse a source number, treating declared placeholders as missing."""

    if is_missing_number(value):
        return None
    if isinstance(value, int | float):
        return float(value)

    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        return None


def is_missing_number(value: str | int | float | None) -> bool:
    """Return whether a source number should be treated as missing."""

    if value is None:
        return True
    if isinstance(value, int | float):
        return value == -999
    return value.strip().upper() in MISSING_VALUES
