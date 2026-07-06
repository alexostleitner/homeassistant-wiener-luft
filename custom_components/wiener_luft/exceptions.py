"""Integration-specific exceptions."""

from __future__ import annotations

from dataclasses import dataclass


class IntegrationError(Exception):
    """Base exception for integration-specific failures."""


@dataclass(frozen=True, slots=True)
class FlowFetchError(IntegrationError):
    """Structured fetch error that can be surfaced in config flow UI."""

    reason: str
    placeholders: dict[str, str] | None = None
