"""Pin-order resolution, stub synthesis, physical-cell policy.

The core of the tool: Verilog connections are named, CDL connections are
positional, so every instance must be reordered against its library .SUBCKT.
See docs/architecture.md.

A cell is either a module of the netlist itself (pin order = its port list) or
a library cell (pin order = its .SUBCKT header). A name that is both is an
error: emitting it would redefine the library cell.

The parser accepts the whole P&R subset; this stage converts scalar nets with
every pin connected. Buses, constants, concatenations, supply declarations and
unconnected pins are reported as not supported yet, with their location, until
the milestones that give them a policy (docs/roadmap.md). Nets used without a
declaration are implicit wires, as in Verilog.
"""

from __future__ import annotations

from typing import NoReturn

from .errors import Location, ResolveError
from .model import (
    CellLibrary,
    Design,
    Instance,
    Module,
    NetRef,
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
    for module in design.modules.values():
        if module.name not in used:
            continue
        cell = library.get(module.name)
        if cell is not None:
            raise ResolveError(
                f"module '{module.name}' is also a library cell (defined at {cell.location})",
                module.location,
            )
        resolved.modules.append(_resolve_module(module, design, library, missing))

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


def _resolve_module(
    module: Module,
    design: Design,
    library: CellLibrary,
    missing: dict[str, Location | None],
) -> ResolvedModule:
    for port in module.ports:
        if port.is_bus:
            _not_yet(f"bus port '{port.name}[{port.msb}:{port.lsb}]'", port.location)
    for net in module.nets.values():
        if net.is_bus:
            _not_yet(f"bus net '{net.name}[{net.msb}:{net.lsb}]'", net.location)
        if net.is_supply:
            _not_yet(f"supply{net.supply_value} net '{net.name}'", net.location)

    resolved = ResolvedModule(
        module.name,
        pins=[p.name for p in module.ports],
        directions={p.name: p.direction for p in module.ports},
        location=module.location,
    )
    for inst in module.instances:
        pins, defined_at = _cell_pins(inst.cell, design, library)
        if pins is None:
            missing.setdefault(inst.cell, inst.location)
            continue
        nets = _order_connections(inst, pins, defined_at)
        resolved.instances.append(ResolvedInstance(inst.name, inst.cell, nets, inst.location))
    return resolved


def _cell_pins(
    cell: str, design: Design, library: CellLibrary
) -> tuple[list[str] | None, Location | None]:
    module = design.modules.get(cell)
    if module is not None:
        return [p.name for p in module.ports], module.location
    lib_cell = library.get(cell)
    if lib_cell is not None:
        return lib_cell.pins, lib_cell.location
    return None, None


def _order_connections(
    inst: Instance, pins: list[str], defined_at: Location | None
) -> list[str]:
    """The heart of it: named connections, reordered into the cell's pin order."""
    by_pin: dict[str, str] = {}
    known = set(pins)
    for conn in inst.connections:
        if conn.pin in by_pin:
            raise ResolveError(
                f"pin '{conn.pin}' of instance '{inst.name}' is connected twice",
                conn.location,
            )
        if conn.pin not in known:
            raise ResolveError(
                f"cell '{inst.cell}' has no pin '{conn.pin}' "
                f"(instance '{inst.name}'; cell defined at {defined_at})",
                conn.location,
            )
        expr = conn.expr
        if expr is None:
            _not_yet(f"unconnected pin '.{conn.pin}()'", conn.location)
        if not isinstance(expr, NetRef):
            _not_yet(f"connecting '{expr}' to pin '{conn.pin}'", conn.location)
        if expr.msb is not None:
            _not_yet(f"bus select '{expr}' on pin '{conn.pin}'", conn.location)
        by_pin[conn.pin] = expr.name

    left_open = [pin for pin in pins if pin not in by_pin]
    if left_open:
        raise ResolveError(
            f"instance '{inst.name}' of '{inst.cell}' does not connect "
            f"{_plural(len(left_open), 'pin')} {', '.join(left_open)} "
            f"(cell defined at {defined_at})",
            inst.location,
        )
    return [by_pin[pin] for pin in pins]


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
