"""Integration-specific exceptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlowFetchError(Exception):
    """Structured fetch error that can be surfaced in config flow UI."""

    reason: str
    placeholders: dict[str, str] | None = None
