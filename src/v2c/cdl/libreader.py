"""Scanner for .SUBCKT headers in library CDL/SPICE files.

Only headers, pin lists and *.PININFO are read; device statements are skipped.
This is what makes the scan viable on multi-megabyte libraries.

.INCLUDE statements are followed, so a library can be a file that does nothing
but list other files. A library is that file plus everything it includes.

Libraries are searched in the order given: when two libraries define the same
cell, the first one wins. Within one library, a cell defined twice with
different pins is an error rather than last-wins (docs/test-plan.md, B7).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator

from ..errors import LibraryError, Location
from ..model import CellLibrary, LibCell

_EQUALS_RE = re.compile(r"\s*=\s*")
_PARAM_KEYWORDS = {"PARAM:", "PARAMS:"}
_INCLUDE_KEYWORDS = {".INCLUDE", ".INC"}


def read_library(paths: list[str]) -> CellLibrary:
    library = CellLibrary()
    for path in paths:
        cells = scan_file(path)
        if not cells:
            raise LibraryError("no .SUBCKT definitions found", Location(path, 1))
        for cell in cells:
            library.cells.setdefault(cell.name, cell)
    return library


def scan_file(path: str) -> list[LibCell]:
    scanner = _Scanner()
    scanner.scan_file(path)
    return list(scanner.cells.values())


def scan_text(text: str, filename: str = "<library>") -> list[LibCell]:
    scanner = _Scanner()
    scanner.scan_lines(text.splitlines(), filename)
    return list(scanner.cells.values())


class _Scanner:
    """Reads one library: a file and, recursively, what it includes."""

    def __init__(self) -> None:
        self.cells: dict[str, LibCell] = {}
        self._open: list[str] = []  # real paths of the include chain being read

    def scan_file(self, path: str, included_at: Location | None = None) -> None:
        real = os.path.realpath(path)
        if real in self._open:
            raise LibraryError(f"recursive .INCLUDE of '{path}'", included_at)
        self._open.append(real)
        try:
            with open(path, encoding="latin-1") as f:
                self.scan_lines(f, path)
        except OSError as exc:
            if included_at is None:
                raise
            raise LibraryError(
                f"cannot read included file '{path}': {exc.strerror}", included_at
            ) from None
        self._open.pop()

    def scan_lines(self, lines: Iterable[str], filename: str) -> None:
        current: LibCell | None = None

        for lineno, line in _logical_lines(lines):
            first = line[:1]
            if first == ".":
                keyword = line.split(None, 1)[0].upper()
                if keyword == ".SUBCKT":
                    if current is not None:
                        raise LibraryError(
                            f"nested .SUBCKT inside '{current.name}' "
                            f"(opened at {current.location})",
                            Location(filename, lineno),
                        )
                    current = _header(line, Location(filename, lineno))
                elif keyword == ".ENDS" and current is not None:
                    self._add(current)
                    current = None
                elif keyword in _INCLUDE_KEYWORDS and current is None:
                    location = Location(filename, lineno)
                    target = _locate(_include_target(line, location), filename, location)
                    self.scan_file(target, location)
            elif first == "*" and current is not None and line[:9].upper() == "*.PININFO":
                for item in line[9:].split():
                    pin, sep, direction = item.rpartition(":")
                    if sep:
                        current.directions[pin] = direction.upper()

        if current is not None:
            raise LibraryError(
                f".SUBCKT '{current.name}' has no matching .ENDS", current.location
            )

    def _add(self, cell: LibCell) -> None:
        previous = self.cells.get(cell.name)
        if previous is None:
            self.cells[cell.name] = cell
        elif previous.pins != cell.pins:
            raise LibraryError(
                f"cell '{cell.name}' is defined again with different pins "
                f"(first definition at {previous.location})",
                cell.location,
            )


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


def _include_target(line: str, location: Location) -> str:
    parts = line.split(None, 1)
    target = parts[1].strip() if len(parts) > 1 else ""
    if len(target) >= 2 and target[0] == target[-1] and target[0] in "\"'":
        target = target[1:-1]
    if not target:
        raise LibraryError(".INCLUDE without a file name", location)
    return target


def _locate(target: str, including_file: str, location: Location) -> str:
    """Resolve a relative .INCLUDE path.

    It may be meant relative to the including file or to the working directory,
    and tools differ on which. Whichever exists is used; if both exist and are
    different files, the include is ambiguous and reported rather than guessed.
    """
    if os.path.isabs(target):
        return target
    beside = os.path.normpath(os.path.join(os.path.dirname(including_file), target))
    found = [path for path in (beside, os.path.normpath(target)) if os.path.isfile(path)]
    if len(found) == 2 and not os.path.samefile(*found):
        raise LibraryError(
            f".INCLUDE '{target}' is ambiguous: both {found[0]} (next to the including "
            f"file) and {found[1]} (in the working directory) exist; use an absolute path",
            location,
        )
    return found[0] if found else beside
