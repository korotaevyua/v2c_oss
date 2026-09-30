"""Intermediate representation.

Deliberately dumb: the input netlist is already fully elaborated, so nothing
here analyzes connectivity. See docs/architecture.md.

Two layers: the Design IR as parsed (named connections, original spelling),
and the Resolved IR the writer consumes (positional connections, in the pin
order of the target cell).
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
    msb: int | None = None
    lsb: int | None = None
    location: Location | None = None

    @property
    def is_bus(self) -> bool:
        return self.msb is not None


# Connection expressions: what may appear inside .PIN( ... ).


@dataclass(frozen=True)
class NetRef:
    """A net, a bit select (msb == lsb) or a part select."""

    name: str
    msb: int | None = None
    lsb: int | None = None

    def __str__(self) -> str:
        if self.msb is None:
            return self.name
        if self.msb == self.lsb:
            return f"{self.name}[{self.msb}]"
        return f"{self.name}[{self.msb}:{self.lsb}]"


@dataclass(frozen=True)
class Const:
    text: str  # as written, e.g. "1'b0"

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class Concat:
    parts: tuple[Expr, ...]

    def __str__(self) -> str:
        return "{" + ", ".join(str(p) for p in self.parts) + "}"


Expr = NetRef | Const | Concat


@dataclass
class Connection:
    pin: str
    expr: Expr | None  # None for an explicitly empty .PIN()
    location: Location | None = None


@dataclass
class Instance:
    name: str
    cell: str
    # Ordered as written in the source; resolution against the library happens
    # later, in resolve.py.
    connections: list[Connection] = field(default_factory=list)
    location: Location | None = None


@dataclass
class Module:
    name: str
    ports: list[Port] = field(default_factory=list)  # in port-list order
    nets: dict[str, Net] = field(default_factory=dict)
    instances: list[Instance] = field(default_factory=list)
    location: Location | None = None


@dataclass
class Design:
    modules: dict[str, Module] = field(default_factory=dict)  # in source order
    top: str | None = None


@dataclass
class LibCell:
    """A .SUBCKT header from a library file. Bodies are never parsed."""

    name: str
    pins: list[str]
    directions: dict[str, str] = field(default_factory=dict)  # from *.PININFO
    location: Location | None = None
    is_stub: bool = False


@dataclass
class CellLibrary:
    cells: dict[str, LibCell] = field(default_factory=dict)

    def get(self, cell_name: str) -> LibCell | None:
        return self.cells.get(cell_name)


# Resolved IR: what the CDL writer consumes. Names are still Verilog spellings;
# mapping them to a flavor is the writer's job.


@dataclass
class ResolvedInstance:
    name: str
    cell: str
    nets: list[str]  # positional, in the cell's pin order
    location: Location | None = None


@dataclass
class ResolvedModule:
    name: str
    pins: list[str]
    directions: dict[str, str]  # pin -> "input" | "output" | "inout"
    instances: list[ResolvedInstance] = field(default_factory=list)
    location: Location | None = None


@dataclass
class ResolvedDesign:
    top: str
    modules: list[ResolvedModule] = field(default_factory=list)  # in source order
