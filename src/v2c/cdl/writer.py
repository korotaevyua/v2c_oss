"""CDL emitter."""

from __future__ import annotations

from .flavors import Flavor


def write_cdl(resolved, flavor: Flavor, out_path: str) -> None:
    raise NotImplementedError("M1")
