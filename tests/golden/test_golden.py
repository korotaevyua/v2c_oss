"""Golden cases: netlist + library in, expected CDL out. See README.md here."""

from pathlib import Path

import pytest

from v2c.cli import main

CASES = Path(__file__).parent / "cases"


def _cases():
    for case in sorted(p for p in CASES.iterdir() if p.is_dir()):
        for expected in sorted(case.glob("expected.*.cdl")):
            flavor = expected.name.split(".")[1]
            yield pytest.param(case, flavor, id=f"{case.name}-{flavor}")


def _significant(text: str) -> list[str]:
    """Comment lines are not part of the contract; *.PININFO and other '*.'
    directives are. Stand-in until the normalizer (M2) takes over."""
    return [line for line in text.splitlines() if not line.startswith("*") or line.startswith("*.")]


@pytest.mark.parametrize("case, flavor", list(_cases()))
def test_golden(case: Path, flavor: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(case)
    out = tmp_path / "out.cdl"
    args_file = case / "args"
    extra = args_file.read_text().split() if args_file.exists() else []

    rc = main(["convert", "in.v", "-s", "lib.cdl", "-o", str(out), "--flavor", flavor, *extra])

    assert rc == 0
    expected = (case / f"expected.{flavor}.cdl").read_text()
    assert _significant(out.read_text()) == _significant(expected)
