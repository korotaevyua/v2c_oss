"""Pin-order resolution, stub synthesis, physical-cell policy.

The core of the tool: Verilog connections are named, CDL connections are
positional, so every instance must be reordered against its library .SUBCKT.
See docs/architecture.md.
"""

from __future__ import annotations

from .model import CellLibrary, Design


def resolve(design: Design, library: CellLibrary, on_missing: str = "error"):
    raise NotImplementedError("M1")
