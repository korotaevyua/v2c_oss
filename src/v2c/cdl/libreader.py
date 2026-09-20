"""Scanner for .SUBCKT headers in library CDL/SPICE files.

Only headers, pin lists and *.PININFO are read; device statements are skipped.
This is what makes the scan viable on multi-megabyte libraries.
"""

from __future__ import annotations

from ..model import CellLibrary


def read_library(paths: list[str]) -> CellLibrary:
    raise NotImplementedError("M1")
