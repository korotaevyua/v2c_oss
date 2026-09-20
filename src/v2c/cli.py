"""Command line interface.

    v2c convert design.v -s stdcells.cdl -s macros.cdl -o design.cdl
    v2c normalize a.cdl
"""

from __future__ import annotations

import argparse
import sys

from .cdl.flavors import FLAVORS
from .errors import V2CError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="v2c", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    conv = sub.add_parser("convert", help="physical Verilog netlist -> CDL")
    conv.add_argument("netlist", help="physical (post-route) Verilog netlist")
    conv.add_argument("-s", "--spice", action="append", default=[],
                      metavar="FILE",
                      help="library CDL/SPICE providing .SUBCKT pin order "
                           "(repeatable; searched in order)")
    conv.add_argument("-o", "--output", required=True)
    conv.add_argument("--top", help="top module (default: inferred)")
    conv.add_argument("--flavor", choices=sorted(FLAVORS), default="calibre")
    conv.add_argument("--on-missing", choices=("error", "stub"), default="error",
                      help="what to do with cells absent from every library")

    norm = sub.add_parser("normalize", help="canonicalize CDL for diffing")
    norm.add_argument("input")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raise NotImplementedError("M1")
    except V2CError as exc:
        print(f"v2c: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
