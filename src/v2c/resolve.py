"""Pin-order resolution, stub synthesis, physical-cell policy.

The core of the tool: Verilog connections are named, CDL connections are
positional, so every instance must be reordered against its library .SUBCKT.
See docs/architecture.md.

A cell is either a module of the netlist itself (pin order = its port list) or
a library cell (pin order = its .SUBCKT header). A name that is both is an
error: emitting it would redefine the library cell.

Buses are bit-blasted (docs/test-plan.md, C3-C5): a bus port becomes one pin
per bit, in the order its range is written, and every connection expression
(bus, bit or part select, concatenation) becomes the bits it denotes, most
significant first. Widths must match. A library bus pin, spelled A<1> A<0> or
A[1] A[0] in the .SUBCKT header, is connected through Verilog pin A, highest
index first.

`assign a = b;` merges nets bit by bit (F3). The merged net takes the port's
name if one side is a port, otherwise the left-hand side's. Two ports on one
net cannot be written as a .SUBCKT pin list, so that is not supported yet.

Constants, supply declarations and unconnected pins are reported as not
supported yet, with their location, until they get a policy
(docs/roadmap.md). Nets used without a declaration are implicit wires, as in
Verilog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NoReturn

from .errors import Location, ResolveError
from .model import (
    Bit,
    CellLibrary,
    Concat,
    Const,
    Design,
    Expr,
    Instance,
    Module,
    Port,
    ResolvedDesign,
    ResolvedInstance,
    ResolvedModule,
)


def resolve(
    design: Design,
    library: CellLibrary,
    top: str | None = None,
    on_missing: str = "error",
) -> ResolvedDesign:
    if on_missing != "error":
        raise ResolveError(f"--on-missing={on_missing} is not supported yet")

    top_name = top or design.top or _infer_top(design)
    if top_name not in design.modules:
        raise ResolveError(f"top module '{top_name}' is not defined in the netlist")
    used = _reachable(design, top_name)

    resolved = ResolvedDesign(top_name)
    missing: dict[str, Location | None] = {}
    interfaces: dict[str, _Interface | None] = {}
    for module in design.modules.values():
        if module.name not in used:
            continue
        cell = library.get(module.name)
        if cell is not None:
            raise ResolveError(
                f"module '{module.name}' is also a library cell (defined at {cell.location})",
                module.location,
            )
        resolved.modules.append(
            _resolve_module(module, design, library, interfaces, missing)
        )

    if missing:
        raise ResolveError(_missing_message(missing, library))
    return resolved


def _infer_top(design: Design) -> str:
    if not design.modules:
        raise ResolveError("the netlist defines no modules")
    instantiated = {
        inst.cell for module in design.modules.values() for inst in module.instances
    }
    roots = [name for name in design.modules if name not in instantiated]
    if len(roots) == 1:
        return roots[0]
    if not roots:
        raise ResolveError("cannot infer the top module: every module is instantiated")
    raise ResolveError(
        f"cannot infer the top module: {', '.join(roots)} are not instantiated "
        f"anywhere; choose one with --top"
    )


def _reachable(design: Design, top: str) -> set[str]:
    """Modules instantiated under top, top included. Iterative: deep hierarchies
    must not hit the recursion limit (docs/test-plan.md, K3)."""
    done: set[str] = set()
    path: list[str] = [top]
    on_path: set[str] = {top}
    stack = [iter(design.modules[top].instances)]
    while stack:
        inst = next(stack[-1], None)
        if inst is None:
            stack.pop()
            name = path.pop()
            on_path.discard(name)
            done.add(name)
            continue
        child = inst.cell
        if child not in design.modules or child in done:
            continue
        if child in on_path:
            cycle = " -> ".join(path[path.index(child):] + [child])
            raise ResolveError(f"recursive instantiation: {cycle}", inst.location)
        path.append(child)
        on_path.add(child)
        stack.append(iter(design.modules[child].instances))
    return done


@dataclass
class _Interface:
    """A cell as instances see it: Verilog pin name -> positions in the CDL pin
    list, most significant bit first."""

    width: int
    pins: dict[str, list[int]]
    labels: list[str]  # per position, for messages
    defined_at: Location | None


def _resolve_module(
    module: Module,
    design: Design,
    library: CellLibrary,
    interfaces: dict[str, _Interface | None],
    missing: dict[str, Location | None],
) -> ResolvedModule:
    for net in module.nets.values():
        if net.is_supply:
            _not_yet(f"supply{net.supply_value} net '{net.name}'", net.location)

    buses = _buses(module)
    merged = _merge_assigns(module, buses)
    resolved = ResolvedModule(
        module.name,
        pins=[bit for port in module.ports for bit in _port_bits(port)],
        directions={p.name: p.direction for p in module.ports},
        location=module.location,
    )
    for inst in module.instances:
        if inst.cell not in interfaces:
            interfaces[inst.cell] = _interface(inst.cell, design, library)
        interface = interfaces[inst.cell]
        if interface is None:
            missing.setdefault(inst.cell, inst.location)
            continue
        nets = [merged.get(bit, bit) for bit in _order_connections(inst, interface, buses)]
        resolved.instances.append(ResolvedInstance(inst.name, inst.cell, nets, inst.location))
    return resolved


def _buses(module: Module) -> dict[str, tuple[int, int]]:
    """Declared buses of a module, name -> (msb, lsb) as written."""
    buses = {n.name: (n.msb, n.lsb) for n in module.nets.values() if n.is_bus}
    buses.update({p.name: (p.msb, p.lsb) for p in module.ports if p.is_bus})
    return buses


def _span(left: int, right: int) -> range:
    """Indices from left to right inclusive, in the direction written."""
    return range(left, right + 1) if left <= right else range(left, right - 1, -1)


def _port_bits(port: Port) -> list[Bit]:
    if not port.is_bus:
        return [Bit(port.name)]
    return [Bit(port.name, i) for i in _span(port.msb, port.lsb)]


def _bits(expr: Expr, buses: dict[str, tuple[int, int]], location: Location | None) -> list[Bit]:
    """An expression as the bits it denotes, most significant first."""
    if isinstance(expr, Concat):
        return [bit for part in expr.parts for bit in _bits(part, buses, location)]
    if isinstance(expr, Const):
        _not_yet(f"constant '{expr}'", location)
    declared = buses.get(expr.name)
    if expr.msb is None:
        if declared is None:
            return [Bit(expr.name)]
        return [Bit(expr.name, i) for i in _span(*declared)]
    if declared is None:
        raise ResolveError(f"'{expr}' selects bits of '{expr.name}', which is not a bus", location)
    valid = _span(*declared)
    for index in (expr.msb, expr.lsb):
        if index not in valid:
            raise ResolveError(
                f"'{expr}' is outside '{expr.name}[{declared[0]}:{declared[1]}]'", location
            )
    return [Bit(expr.name, i) for i in _span(expr.msb, expr.lsb)]


def _merge_assigns(module: Module, buses: dict[str, tuple[int, int]]) -> dict[Bit, Bit]:
    """Bit -> the bit it was merged into by assign statements."""
    ports = {bit for port in module.ports for bit in _port_bits(port)}
    parent: dict[Bit, Bit] = {}

    def find(bit: Bit) -> Bit:
        while bit in parent:
            bit = parent[bit]
        return bit

    for assign in module.assigns:
        what = f"assign '{assign.lhs} = {assign.rhs}'"
        if isinstance(assign.lhs, Const) or isinstance(assign.rhs, Const):
            _not_yet(f"{what} with a constant", assign.location)
        lhs = _bits(assign.lhs, buses, assign.location)
        rhs = _bits(assign.rhs, buses, assign.location)
        if len(lhs) != len(rhs):
            raise ResolveError(
                f"{what}: left side is {len(lhs)} bits wide, right side {len(rhs)}",
                assign.location,
            )
        for left, right in zip(lhs, rhs):
            keep, drop = find(left), find(right)
            if keep == drop:
                continue
            if keep in ports and drop in ports:
                _not_yet(f"{what} joining ports '{keep}' and '{drop}'", assign.location)
            if drop in ports:
                keep, drop = drop, keep
            parent[drop] = keep

    return {bit: find(bit) for bit in parent}


_LIB_BUS_PIN_RE = re.compile(r"^(.+?)[<\[](\d+)[>\]]$")


def _interface(cell: str, design: Design, library: CellLibrary) -> _Interface | None:
    module = design.modules.get(cell)
    if module is not None:
        pins: dict[str, list[int]] = {}
        labels: list[str] = []
        for port in module.ports:
            bits = _port_bits(port)
            pins[port.name] = list(range(len(labels), len(labels) + len(bits)))
            labels += [str(bit) for bit in bits]
        return _Interface(len(labels), pins, labels, module.location)

    lib_cell = library.get(cell)
    if lib_cell is None:
        return None
    # Library bus pins are spelled A<1> A<0> or A[1] A[0]; a Verilog connection
    # to A covers them all, most significant index first.
    pins = {}
    bus_bits: dict[str, list[tuple[int, int]]] = {}
    for position, pin in enumerate(lib_cell.pins):
        m = _LIB_BUS_PIN_RE.match(pin)
        if m:
            bus_bits.setdefault(m.group(1), []).append((int(m.group(2)), position))
        else:
            pins[pin] = [position]
    for base, bits in bus_bits.items():
        if base not in pins:
            pins[base] = [position for _, position in sorted(bits, reverse=True)]
    return _Interface(len(lib_cell.pins), pins, list(lib_cell.pins), lib_cell.location)


def _order_connections(
    inst: Instance, interface: _Interface, buses: dict[str, tuple[int, int]]
) -> list[Bit]:
    """The heart of it: named connections, reordered into the cell's pin order."""
    slots: list[Bit | None] = [None] * interface.width
    seen: set[str] = set()
    for conn in inst.connections:
        if conn.pin in seen:
            raise ResolveError(
                f"pin '{conn.pin}' of instance '{inst.name}' is connected twice",
                conn.location,
            )
        seen.add(conn.pin)
        positions = interface.pins.get(conn.pin)
        if positions is None:
            raise ResolveError(
                f"cell '{inst.cell}' has no pin '{conn.pin}' "
                f"(instance '{inst.name}'; cell defined at {interface.defined_at})",
                conn.location,
            )
        if conn.expr is None:
            _not_yet(f"unconnected pin '.{conn.pin}()'", conn.location)
        if isinstance(conn.expr, Const):
            _not_yet(f"connecting '{conn.expr}' to pin '{conn.pin}'", conn.location)
        bits = _bits(conn.expr, buses, conn.location)
        if len(bits) != len(positions):
            raise ResolveError(
                f"pin '{conn.pin}' of cell '{inst.cell}' is {len(positions)} "
                f"{_plural(len(positions), 'bit')} wide, but '{conn.expr}' is {len(bits)} "
                f"(instance '{inst.name}')",
                conn.location,
            )
        for position, bit in zip(positions, bits):
            slots[position] = bit

    left_open = [interface.labels[i] for i, bit in enumerate(slots) if bit is None]
    if left_open:
        raise ResolveError(
            f"instance '{inst.name}' of '{inst.cell}' does not connect "
            f"{_plural(len(left_open), 'pin')} {', '.join(left_open)} "
            f"(cell defined at {interface.defined_at})",
            inst.location,
        )
    return slots  # type: ignore[return-value]  # every slot is filled


def _missing_message(missing: dict[str, Location | None], library: CellLibrary) -> str:
    count = len(missing)
    hint = "" if library.cells else " (no library was given with -s)"
    lines = [f"{count} {_plural(count, 'cell')} not found in the netlist or any library{hint}:"]
    lines += [f"  {location}: {cell}" for cell, location in missing.items()]
    return "\n".join(lines)


def _not_yet(what: str, location: Location | None) -> NoReturn:
    raise ResolveError(f"{what}: not supported yet", location)


def _plural(count: int, word: str) -> str:
    return word if count == 1 else f"{word}s"
