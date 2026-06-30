"""Minimal voluptuous stub for unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Required:
    """Minimal representation of voluptuous.Required."""

    schema: str
    default: Any = None

    def __hash__(self) -> int:
        return hash(self.schema)


class Schema:
    """Minimal schema wrapper used by the tests."""

    def __init__(self, schema: Any) -> None:
        self.schema = schema
