"""Scanner for .SUBCKT headers in library CDL/SPICE files.

Only headers, pin lists and *.PININFO are read; device statements are skipped.
This is what makes the scan viable on multi-megabyte libraries.

Libraries are searched in the order given: when two files define the same
cell, the first one wins. Within one file, a cell defined twice with different
pins is an error rather than last-wins (docs/test-plan.md, B7).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from ..errors import LibraryError, Location
from ..model import CellLibrary, LibCell

_EQUALS_RE = re.compile(r"\s*=\s*")
_PARAM_KEYWORDS = {"PARAM:", "PARAMS:"}


def read_library(paths: list[str]) -> CellLibrary:
    library = CellLibrary()
    for path in paths:
        with open(path, encoding="latin-1") as f:
            cells = scan_lines(f, path)
        if not cells:
            raise LibraryError("no .SUBCKT definitions found", Location(path, 1))
        for cell in cells:
            library.cells.setdefault(cell.name, cell)
    return library


def scan_text(text: str, filename: str = "<library>") -> list[LibCell]:
    return scan_lines(text.splitlines(), filename)


def scan_lines(lines: Iterable[str], filename: str) -> list[LibCell]:
    cells: dict[str, LibCell] = {}
    current: LibCell | None = None

    for lineno, line in _logical_lines(lines):
        first = line[:1]
        if first == ".":
            keyword = line.split(None, 1)[0].upper()
            if keyword == ".SUBCKT":
                if current is not None:
                    raise LibraryError(
                        f"nested .SUBCKT inside '{current.name}' (opened at {current.location})",
                        Location(filename, lineno),
                    )
                current = _header(line, Location(filename, lineno))
            elif keyword == ".ENDS" and current is not None:
                _add(cells, current)
                current = None
        elif first == "*" and current is not None and line[:9].upper() == "*.PININFO":
            for item in line[9:].split():
                pin, sep, direction = item.rpartition(":")
                if sep:
                    current.directions[pin] = direction.upper()

    if current is not None:
        raise LibraryError(
            f".SUBCKT '{current.name}' has no matching .ENDS", current.location
        )
    return list(cells.values())


def _logical_lines(lines: Iterable[str]) -> Iterator[tuple[int, str]]:
    """Join '+' continuation lines onto the line they continue."""
    pending: str | None = None
    pending_line = 0
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if line.startswith("+"):
            if pending is not None:
                pending = f"{pending} {line[1:]}"
            continue
        if pending is not None:
            yield pending_line, pending
        pending, pending_line = line, lineno
    if pending is not None:
        yield pending_line, pending


def _header(line: str, location: Location) -> LibCell:
    fields = _EQUALS_RE.sub("=", line).split()
    if len(fields) < 2:
        raise LibraryError(".SUBCKT without a cell name", location)
    pins = []
    for field in fields[2:]:
        if "=" in field or field.upper() in _PARAM_KEYWORDS:
            break  # parameters follow the pins
        pins.append(field)
    return LibCell(fields[1], pins, location=location)


def _add(cells: dict[str, LibCell], cell: LibCell) -> None:
    previous = cells.get(cell.name)
    if previous is None:
        cells[cell.name] = cell
    elif previous.pins != cell.pins:
        raise LibraryError(
            f"cell '{cell.name}' is defined again with different pins "
            f"(first definition at {previous.location})",
            cell.location,
        )
