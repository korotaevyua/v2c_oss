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


def test_file_without_subckts_is_rejected(tmp_path):
    path = tmp_path / "not_a_library.v"
    path.write_text("module top; endmodule\n")
    with pytest.raises(LibraryError) as exc:
        read_library([str(path)])
    assert "no .SUBCKT definitions found" in exc.value.message
    assert exc.value.location.file == str(path)
