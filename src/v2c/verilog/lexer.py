"""Tokenizer for the structural Verilog subset.

Handles escaped identifiers (backslash ... whitespace) as single tokens with
their original spelling preserved, because that spelling is what the CDL writer
has to rewrite deterministically. See docs/flavors.md.
"""

from __future__ import annotations

from collections.abc import Iterator


def tokenize(text: str, filename: str = "<input>") -> Iterator[tuple]:
    raise NotImplementedError("M1")
