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
