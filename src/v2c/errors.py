"""Diagnostics.

Every user-facing failure carries a source location. See docs/architecture.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    file: str
    line: int
    column: int = 0

    def __str__(self) -> str:
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


class V2CError(Exception):
    """Base class for all expected, reportable failures."""

    def __init__(self, message: str, location: Location | None = None) -> None:
        self.message = message
        self.location = location
        super().__init__(f"{location}: {message}" if location else message)


class ParseError(V2CError):
    """Malformed input netlist."""


class LibraryError(V2CError):
    """Problem in a supplied library CDL/SPICE file."""


class ResolveError(V2CError):
    """Netlist and library disagree — missing cell, unknown pin, collision."""
