"""Smoke tests: the package imports and the CLI describes itself."""

import v2c
from v2c.cdl.flavors import FLAVORS
from v2c.cli import Library, build_parser


def test_version_present():
    assert v2c.__version__


def test_flavors_registered():
    assert set(FLAVORS) == {"calibre", "netgen", "klayout"}


def test_cli_parses_convert():
    args = build_parser().parse_args(
        ["convert", "d.v", "-s", "lib.cdl", "-o", "d.cdl"]
    )
    assert args.command == "convert"
    assert args.libraries == [Library("lib.cdl", include=True)]
    assert args.flavor == "calibre"
    assert args.on_missing == "error"


def test_libraries_keep_command_line_order():
    args = build_parser().parse_args(
        ["convert", "d.v", "-lsp", "a.cdl", "-s", "b.cdl", "-lsp", "c.cdl", "-o", "d.cdl"]
    )
    assert args.libraries == [
        Library("a.cdl", include=False), Library("b.cdl", include=True),
        Library("c.cdl", include=False),
    ]
