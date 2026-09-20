"""Output flavor tables.

Differences between Calibre, netgen and KLayout are data, not code paths, and
must not leak into the parser or the resolver. See docs/flavors.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Flavor:
    name: str
    bus_open: str
    bus_close: str
    emit_global: bool
    emit_pininfo: bool
    case_sensitive: bool


CALIBRE = Flavor("calibre", "<", ">", True, True, False)
NETGEN = Flavor("netgen", "[", "]", True, True, True)
KLAYOUT = Flavor("klayout", "[", "]", True, True, True)

FLAVORS = {f.name: f for f in (CALIBRE, NETGEN, KLAYOUT)}
