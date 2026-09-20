"""Canonicalize a CDL file for diffing.

Used by the differential harness: strip comments and headers, sort instances,
canonicalize whitespace and line continuations, so that two converters'
outputs can be compared for substance rather than formatting.
See docs/test-plan.md, section J.
"""

from __future__ import annotations


def normalize(text: str) -> str:
    raise NotImplementedError("M2")
