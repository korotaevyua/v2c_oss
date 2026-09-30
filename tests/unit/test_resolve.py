import pytest

from v2c.cdl.libreader import scan_text
from v2c.errors import ResolveError
from v2c.model import CellLibrary
from v2c.resolve import resolve
from v2c.verilog.parser import parse_text

LIB = CellLibrary({
    c.name: c
    for c in scan_text(
        ".SUBCKT INV A Y VDD VSS\n.ENDS\n.SUBCKT NAND2 A B Y VDD VSS\n.ENDS\n", "lib.cdl"
    )
})

SUB = """
module sub (y, a, VDD, VSS);
  input a; output y; inout VDD, VSS;
  INV g (.A(a), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule
"""


def run(verilog: str, top: str | None = None, library: CellLibrary = LIB, **kw):
    return resolve(parse_text(verilog, "t.v"), library, top=top, **kw)


def resolve_error(verilog: str, **kw) -> ResolveError:
    with pytest.raises(ResolveError) as exc:
        run(verilog, **kw)
    return exc.value


def test_named_connections_follow_the_library_pin_order():
    design = run("""
module top (a, b, y, VDD, VSS);
  input a, b; output y; inout VDD, VSS;
  NAND2 u1 (.VSS(VSS), .Y(y), .B(b), .VDD(VDD), .A(a));
endmodule
""")
    (inst,) = design.modules[0].instances
    assert (inst.name, inst.cell, inst.nets) == ("u1", "NAND2", ["a", "b", "y", "VDD", "VSS"])


def test_module_instance_follows_the_module_port_list():
    design = run(SUB + """
module top (a, y, VDD, VSS);
  input a; output y; inout VDD, VSS;
  sub u (.a(a), .y(y), .VDD(VDD), .VSS(VSS));
endmodule
""")
    assert design.top == "top"
    assert [m.name for m in design.modules] == ["sub", "top"]
    sub, top = design.modules
    assert sub.pins == ["y", "a", "VDD", "VSS"]
    assert sub.directions == {"y": "output", "a": "input", "VDD": "inout", "VSS": "inout"}
    assert top.instances[0].nets == ["y", "a", "VDD", "VSS"]


def test_explicit_top_drops_modules_outside_its_hierarchy():
    design = run(SUB + "module other; endmodule\n", top="sub")
    assert [m.name for m in design.modules] == ["sub"]


def test_ambiguous_top():
    err = resolve_error(SUB + "module other; endmodule\n")
    assert "sub, other are not instantiated anywhere; choose one with --top" in err.message


def test_unknown_top():
    assert "top module 'nope' is not defined" in resolve_error(SUB, top="nope").message


def test_recursive_instantiation():
    err = resolve_error("""
module top; a u (); endmodule
module a; b u (); endmodule
module b; a u (); endmodule
""")
    assert "recursive instantiation: a -> b -> a" in err.message
    assert str(err.location) == "t.v:4:11"


def test_missing_cells_are_listed_at_once():
    err = resolve_error("""
module top (a, VDD, VSS);
  input a; inout VDD, VSS;
  FOO u1 (.A(a));
  BAR u2 (.A(a));
  FOO u3 (.A(a));
endmodule
""")
    assert err.location is None
    assert err.message.splitlines() == [
        "2 cells not found in the netlist or any library:",
        "  t.v:4:3: FOO",
        "  t.v:5:3: BAR",
    ]


def test_missing_cells_hint_when_no_library_was_given():
    err = resolve_error("module top; FOO u1 (); endmodule", library=CellLibrary())
    assert "(no library was given with -s)" in err.message


def test_module_that_is_also_a_library_cell():
    err = resolve_error("module top; INV u (); endmodule\nmodule INV; endmodule")
    assert "module 'INV' is also a library cell (defined at lib.cdl:1)" in err.message


@pytest.mark.parametrize(
    "body, message, column",
    [
        # B3
        ("INV u (.A(a), .Z(y), .VDD(VDD), .VSS(VSS));",
         "cell 'INV' has no pin 'Z' (instance 'u'; cell defined at lib.cdl:1)", 15),
        ("INV u (.A(a), .A(y), .VDD(VDD), .VSS(VSS));",
         "pin 'A' of instance 'u' is connected twice", 15),
        ("INV u (.A(a), .VDD(VDD));",
         "instance 'u' of 'INV' does not connect pins Y, VSS (cell defined at lib.cdl:1)", 1),
    ],
)
def test_pin_errors(body, message, column):
    err = resolve_error(f"module top (a, y, VDD, VSS);\n"
                        f"input a; output y; inout VDD, VSS;\n{body}\nendmodule")
    assert message in err.message
    assert (err.location.line, err.location.column) == (3, column)


@pytest.mark.parametrize(
    "decls, conn, message",
    [
        ("input [1:0] a;", ".A(a)", "bus port 'a[1:0]'"),
        ("input a; wire [1:0] w;", ".A(a)", "bus net 'w[1:0]'"),
        ("input a; supply1 w;", ".A(a)", "supply1 net 'w'"),
        ("input a; wire w;", ".A()", "unconnected pin '.A()'"),
        ("input a; wire w;", ".A(1'b0)", "connecting '1'b0' to pin 'A'"),
        ("input a; wire w;", ".A({a, w})", "connecting '{a, w}' to pin 'A'"),
        ("input a; wire w;", ".A(w[0])", "bus select 'w[0]' on pin 'A'"),
    ],
)
def test_constructs_without_a_policy_yet_are_rejected(decls, conn, message):
    err = resolve_error(f"module top (a, y, VDD, VSS);\n"
                        f"output y; inout VDD, VSS; {decls}\n"
                        f"INV u ({conn}, .Y(y), .VDD(VDD), .VSS(VSS));\nendmodule")
    assert err.message == f"{message}: not supported yet"
    assert err.location is not None


def test_stub_mode_is_not_available_yet():
    assert "not supported yet" in resolve_error(SUB, on_missing="stub").message
