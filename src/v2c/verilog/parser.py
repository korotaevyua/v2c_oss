"""Recursive-descent parser producing a Design.

Accepts only what P&R tools emit; see docs/scope.md for the grammar boundary.
Anything outside it is a ParseError with a location, never a silent skip.
"""

from __future__ import annotations

from ..model import Design


def parse_file(path: str) -> Design:
    raise NotImplementedError("M1")
