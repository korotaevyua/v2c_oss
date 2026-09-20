"""Smoke tests: the package imports and the CLI describes itself.

Real coverage arrives with M1; see docs/test-plan.md.
"""

import v2c
from v2c.cdl.flavors import FLAVORS
from v2c.cli import build_parser


def test_version_present():
    assert v2c.__version__


def test_flavors_registered():
    assert set(FLAVORS) == {"calibre", "netgen", "klayout"}


def test_cli_parses_convert():
    args = build_parser().parse_args(
        ["convert", "d.v", "-s", "lib.cdl", "-o", "d.cdl"]
    )
    assert args.command == "convert"
    assert args.spice == ["lib.cdl"]
    assert args.flavor == "calibre"
    assert args.on_missing == "error"
