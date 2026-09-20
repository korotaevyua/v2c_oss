"""Intermediate representation.

Deliberately dumb: the input netlist is already fully elaborated, so nothing
here analyzes connectivity. See docs/architecture.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import Location


@dataclass
class Port:
    name: str
    direction: str  # "input" | "output" | "inout"
    msb: int | None = None
    lsb: int | None = None
    location: Location | None = None

    @property
    def is_bus(self) -> bool:
        return self.msb is not None


@dataclass
class Net:
    name: str  # original Verilog spelling, escaping intact
    is_supply: bool = False
    supply_value: int | None = None  # 0 or 1 for supply0/supply1
    location: Location | None = None


@dataclass
class Instance:
    name: str
    cell: str
    # Ordered as written in the source; resolution against the library happens
    # later, in resolve.py.
    connections: list[tuple[str, str | None]] = field(default_factory=list)
    location: Location | None = None


@dataclass
class Module:
    name: str
    ports: list[Port] = field(default_factory=list)
    nets: dict[str, Net] = field(default_factory=dict)
    instances: list[Instance] = field(default_factory=list)
    location: Location | None = None


@dataclass
class Design:
    modules: dict[str, Module] = field(default_factory=dict)
    top: str | None = None


@dataclass
class LibCell:
    """A .SUBCKT header from a library file. Bodies are never parsed."""

    name: str
    pins: list[str]
    directions: dict[str, str] = field(default_factory=dict)  # from *.PININFO
    source_file: str | None = None
    is_stub: bool = False


@dataclass
class CellLibrary:
    cells: dict[str, LibCell] = field(default_factory=dict)

    def get(self, cell_name: str) -> LibCell | None:
        return self.cells.get(cell_name)
