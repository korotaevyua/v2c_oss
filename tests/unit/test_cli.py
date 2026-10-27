import gzip
import os
import subprocess
import sys
from pathlib import Path

import pytest

from v2c.cli import main

NETLIST = """\
module top (a, y, VDD, VSS);
  input a; output y; inout VDD, VSS;
  INV u0 (.Y(y), .A(a), .VDD(VDD), .VSS(VSS));
endmodule
"""
LIB = ".SUBCKT INV A Y VDD VSS\n.ENDS INV\n"


@pytest.fixture
def files(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "d.v").write_text(NETLIST)
    (tmp_path / "lib.cdl").write_text(LIB)
    return tmp_path


def test_convert(files: Path):
    assert main(["convert", "d.v", "-s", "lib.cdl", "-o", "d.cdl"]) == 0
    assert "Xu0 a y VDD VSS INV\n" in (files / "d.cdl").read_text()


def test_error_is_located_and_leaves_no_output(files: Path, capsys):
    (files / "d.cdl").write_text("previous result\n")
    (files / "d.v").write_text(NETLIST.replace(".A(a)", ".Q(a)"))

    assert main(["convert", "d.v", "-s", "lib.cdl", "-o", "d.cdl"]) == 1

    err = capsys.readouterr().err
    assert err.startswith("v2c: error: d.v:3:18: cell 'INV' has no pin 'Q'")
    assert (files / "d.cdl").read_text() == "previous result\n"
    assert not (files / "d.cdl.tmp").exists()


def test_unreadable_input(files: Path, capsys):
    assert main(["convert", "nope.v", "-s", "lib.cdl", "-o", "d.cdl"]) == 1
    assert capsys.readouterr().err == "v2c: error: nope.v: No such file or directory\n"


@pytest.mark.parametrize(
    "argv, message",
    [
        (["convert", "d.v", "-s", "lib.cdl", "-o", "d.cdl", "--flavor", "netgen"],
         "flavor 'netgen' is not supported yet"),
        (["normalize", "d.cdl"], "'normalize' is not implemented yet"),
    ],
)
def test_not_yet_available(files: Path, capsys, argv, message):
    assert main(argv) == 1
    assert capsys.readouterr().err == f"v2c: error: {message}\n"


def test_gzipped_netlist_and_library(files: Path):
    for name in ("d.v", "lib.cdl"):
        data = (files / name).read_bytes()
        (files / name).unlink()
        (files / f"{name}.gz").write_bytes(gzip.compress(data))
    assert main(["convert", "d.v.gz", "-s", "lib.cdl.gz", "-o", "d.cdl"]) == 0
    assert "Xu0 a y VDD VSS INV\n" in (files / "d.cdl").read_text()


def test_corrupt_gzip_is_a_located_error(files: Path, capsys):
    (files / "d.v.gz").write_bytes(gzip.compress(NETLIST.encode())[:-12])
    assert main(["convert", "d.v.gz", "-s", "lib.cdl", "-o", "d.cdl"]) == 1
    assert capsys.readouterr().err.startswith("v2c: error: d.v.gz:1: corrupt gzip data: ")


def test_launcher_script_runs_from_anywhere(files: Path):
    launcher = Path(__file__).resolve().parents[2] / "v2c"
    result = subprocess.run(
        [sys.executable, str(launcher), "convert", "d.v", "-s", "lib.cdl", "-o", "d.cdl"],
        capture_output=True, text=True, check=False, env={"PATH": os.environ.get("PATH", "")},
    )
    assert (result.returncode, result.stderr) == (0, "")
    assert (files / "d.cdl").exists()
