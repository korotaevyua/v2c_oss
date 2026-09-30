"""Command line interface.

    v2c convert design.v -s stdcells.cdl -s macros.cdl -o design.cdl
    v2c normalize a.cdl
"""

from __future__ import annotations

import argparse
import os
import sys

from .cdl.flavors import FLAVORS
from .cdl.libreader import read_library
from .cdl.writer import write_cdl
from .errors import V2CError
from .resolve import resolve
from .verilog.parser import parse_file

# Flavors whose output has been checked against the consuming tool.
_SUPPORTED_FLAVORS = {"calibre"}


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
        if args.command == "convert":
            convert(args)
        else:
            raise V2CError(f"'{args.command}' is not implemented yet")
    except V2CError as exc:
        print(f"v2c: error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"v2c: error: {exc.filename}: {exc.strerror}", file=sys.stderr)
        return 1
    return 0


def convert(args: argparse.Namespace) -> None:
    if args.flavor not in _SUPPORTED_FLAVORS:
        raise V2CError(f"flavor '{args.flavor}' is not supported yet")
    flavor = FLAVORS[args.flavor]

    design = parse_file(args.netlist)
    library = read_library(args.spice)
    resolved = resolve(design, library, top=args.top, on_missing=args.on_missing)

    # Write next to the target and rename, so a failure never leaves a
    # truncated file that looks like a result.
    tmp = f"{args.output}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as out:
            write_cdl(resolved, flavor, out, source=args.netlist)
        os.replace(tmp, args.output)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


if __name__ == "__main__":
    raise SystemExit(main())
