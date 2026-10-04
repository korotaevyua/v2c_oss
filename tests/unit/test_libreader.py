import pytest

from v2c.cdl.libreader import read_library, scan_text
from v2c.errors import LibraryError

LIB = """\
* comment
.subckt INV A Y VDD VSS
*.PININFO A:I Y:O VDD:P VSS:G
MP0 Y A VDD VDD pch W=1u L=0.1u
MN0 Y A VSS VSS nch
+ W=0.5u L=0.1u
.ends INV

.SUBCKT NAND2 A B
+ Y VDD VSS W = 1u
MN0 x
.ENDS

.SUBCKT BUF A Y PARAM: drive=1
.ENDS
"""


def test_headers_pins_and_directions():
    cells = {c.name: c for c in scan_text(LIB, "lib.cdl")}
    assert list(cells) == ["INV", "NAND2", "BUF"]
    assert cells["INV"].pins == ["A", "Y", "VDD", "VSS"]
    assert cells["INV"].directions == {"A": "I", "Y": "O", "VDD": "P", "VSS": "G"}
    assert str(cells["INV"].location) == "lib.cdl:2"


def test_continuation_lines_and_parameters():
    cells = {c.name: c for c in scan_text(LIB, "lib.cdl")}
    assert cells["NAND2"].pins == ["A", "B", "Y", "VDD", "VSS"]
    assert cells["BUF"].pins == ["A", "Y"]


def test_identical_redefinition_is_harmless():
    cells = scan_text(".SUBCKT A x y\n.ENDS\n.SUBCKT A x y\n.ENDS\n")
    assert [(c.name, c.pins) for c in cells] == [("A", ["x", "y"])]


@pytest.mark.parametrize(
    "src, message, line",
    [
        # B7: same cell, different pin order, one library -> conflict, not last-wins
        (".SUBCKT A x y\n.ENDS\n.SUBCKT A y x\n.ENDS\n",
         "cell 'A' is defined again with different pins (first definition at lib.cdl:1)", 3),
        (".SUBCKT A x\n.SUBCKT B y\n.ENDS\n.ENDS\n", "nested .SUBCKT inside 'A'", 2),
        (".SUBCKT A x\nM0 x x x x nch\n", ".SUBCKT 'A' has no matching .ENDS", 1),
        ("\n.SUBCKT\n.ENDS\n", ".SUBCKT without a cell name", 2),
    ],
)
def test_errors_carry_a_location(src, message, line):
    with pytest.raises(LibraryError) as exc:
        scan_text(src, "lib.cdl")
    assert message in exc.value.message
    assert exc.value.location.line == line


def test_libraries_are_searched_in_order(tmp_path):
    first = tmp_path / "first.cdl"
    second = tmp_path / "second.cdl"
    first.write_text(".SUBCKT INV A Y\n.ENDS\n")
    second.write_text(".SUBCKT INV Y A\n.ENDS\n.SUBCKT NAND2 A B Y\n.ENDS\n")
    library = read_library([str(first), str(second)])
    assert library.get("INV").pins == ["A", "Y"]
    assert library.get("NAND2").pins == ["A", "B", "Y"]


def test_includes_are_followed_relative_to_the_including_file(tmp_path, monkeypatch):
    (tmp_path / "pdk" / "cells").mkdir(parents=True)
    (tmp_path / "pdk" / "all.cdl").write_text(
        '.INCLUDE "cells/std.cdl"\n.inc cells/macro.cdl\n'
        f".include '{tmp_path / 'abs.cdl'}'\n"
    )
    (tmp_path / "pdk" / "cells" / "std.cdl").write_text(".SUBCKT INV A Y\n.ENDS\n")
    (tmp_path / "pdk" / "cells" / "macro.cdl").write_text(".SUBCKT RAM CK D Q\n.ENDS\n")
    (tmp_path / "abs.cdl").write_text(".SUBCKT TAP VDD VSS\n.ENDS\n")
    monkeypatch.chdir(tmp_path)

    library = read_library(["pdk/all.cdl"])

    assert {name: c.pins for name, c in library.cells.items()} == {
        "INV": ["A", "Y"], "RAM": ["CK", "D", "Q"], "TAP": ["VDD", "VSS"],
    }
    assert str(library.get("INV").location) == "pdk/cells/std.cdl:1"


def test_conflict_between_included_files_is_one_library(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "all.cdl").write_text('.INCLUDE "a.cdl"\n.INCLUDE "b.cdl"\n')
    (tmp_path / "a.cdl").write_text(".SUBCKT INV A Y\n.ENDS\n")
    (tmp_path / "b.cdl").write_text(".SUBCKT INV Y A\n.ENDS\n")
    with pytest.raises(LibraryError) as exc:
        read_library(["all.cdl"])
    assert "first definition at a.cdl:1" in exc.value.message
    assert str(exc.value.location) == "b.cdl:1"


@pytest.mark.parametrize(
    "files, message",
    [
        ({"all.cdl": '.INCLUDE "gone.cdl"\n'},
         "cannot read included file 'gone.cdl': No such file or directory"),
        ({"all.cdl": ".INCLUDE\n"}, ".INCLUDE without a file name"),
        ({"all.cdl": '.INCLUDE "b.cdl"\n', "b.cdl": '\n.INCLUDE "all.cdl"\n'},
         "recursive .INCLUDE of 'all.cdl'"),
    ],
)
def test_include_errors(tmp_path, monkeypatch, files, message):
    monkeypatch.chdir(tmp_path)
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    with pytest.raises(LibraryError) as exc:
        read_library(["all.cdl"])
    assert message in exc.value.message
    assert exc.value.location is not None


def test_relative_include_found_in_two_places_is_ambiguous(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "all.cdl").write_text('.INCLUDE "std.cdl"\n')
    (tmp_path / "lib" / "std.cdl").write_text(".SUBCKT INV A Y\n.ENDS\n")
    (tmp_path / "std.cdl").write_text(".SUBCKT INV Y A\n.ENDS\n")
    with pytest.raises(LibraryError) as exc:
        read_library(["lib/all.cdl"])
    assert exc.value.message == (
        ".INCLUDE 'std.cdl' is ambiguous: both lib/std.cdl (next to the including file) "
        "and std.cdl (in the working directory) exist; use an absolute path"
    )
    assert str(exc.value.location) == "lib/all.cdl:1"


def test_file_without_subckts_is_rejected(tmp_path):
    path = tmp_path / "not_a_library.v"
    path.write_text("module top; endmodule\n")
    with pytest.raises(LibraryError) as exc:
        read_library([str(path)])
    assert "no .SUBCKT definitions found" in exc.value.message
    assert exc.value.location.file == str(path)
