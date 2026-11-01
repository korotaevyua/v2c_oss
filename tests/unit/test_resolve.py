from __future__ import annotations

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


def names(bits) -> list[str]:
    return [str(bit) for bit in bits]


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
    assert (inst.name, inst.cell, names(inst.nets)) == ("u1", "NAND2", ["a", "b", "y", "VDD", "VSS"])


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
    assert names(sub.pins) == ["y", "a", "VDD", "VSS"]
    assert sub.directions == {"y": "output", "a": "input", "VDD": "inout", "VSS": "inout"}
    assert names(top.instances[0].nets) == ["y", "a", "VDD", "VSS"]


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
        ("input a; supply1 w;", ".A(a)", "supply1 net 'w'"),
        ("input a; wire w;", ".A()", "unconnected pin '.A()'"),
        ("input a; wire w;", ".A(1'b0)", "connecting '1'b0' to pin 'A'"),
        ("input a; wire w;", ".A({a, 1'b0})", "constant '1'b0'"),
    ],
)
def test_constructs_without_a_policy_yet_are_rejected(decls, conn, message):
    err = resolve_error(f"module top (a, y, VDD, VSS);\n"
                        f"output y; inout VDD, VSS; {decls}\n"
                        f"INV u ({conn}, .Y(y), .VDD(VDD), .VSS(VSS));\nendmodule")
    assert err.message == f"{message}: not supported yet"
    assert err.location is not None


ASSIGN_TOP = """
module top (a, y, VDD, VSS);
  input a; output y; inout VDD, VSS;
  {assigns}
  INV u1 (.A(a), .Y(n1), .VDD(VDD), .VSS(VSS));
  INV u2 (.A(n2), .Y(n3), .VDD(VDD), .VSS(VSS));
endmodule
"""


def test_assign_merges_nets_and_keeps_port_names():
    # n3 -> y because y is a port; n1/n2 chain keeps the left-hand name n2
    design = run(ASSIGN_TOP.format(assigns="assign n3 = y; assign n2 = n1;"))
    assert [names(i.nets) for i in design.modules[0].instances] == [
        ["a", "n2", "VDD", "VSS"], ["n2", "y", "VDD", "VSS"],
    ]


def test_assign_chains_resolve_transitively():
    design = run(ASSIGN_TOP.format(assigns="assign n2 = n1; assign y = n9, n9 = n3;"))
    assert [names(i.nets) for i in design.modules[0].instances] == [
        ["a", "n2", "VDD", "VSS"], ["n2", "y", "VDD", "VSS"],
    ]


@pytest.mark.parametrize(
    "assigns, message",
    [
        ("assign y = a;", "assign 'y = a' joining ports 'y' and 'a'"),
        ("assign y = n3, n3 = a;", "assign 'n3 = a' joining ports 'y' and 'a'"),
        ("assign y = 1'b0;", "assign 'y = 1'b0' with a constant"),
    ],
)
def test_assigns_without_a_policy_yet_are_rejected(assigns, message):
    err = resolve_error(ASSIGN_TOP.format(assigns=assigns))
    assert err.message == f"{message}: not supported yet"
    assert err.location.line == 4


BUS_LIB = CellLibrary({
    c.name: c
    for c in scan_text(
        ".SUBCKT INV A Y VDD VSS\n.ENDS\n"
        ".SUBCKT RAM CK A<1> A<0> D[0] D[1] Q VDD VSS\n.ENDS\n", "lib.cdl"
    )
})

BUS_TOP = """
module top (ck, addr, q, VDD, VSS);
  input ck; input [1:0] addr; output q; inout VDD, VSS;
  wire [3:0] d;
  {body}
endmodule
"""


def test_buses_are_bit_blasted_onto_library_bus_pins():
    design = run(BUS_TOP.format(body=(
        "RAM u (.CK(ck), .A(addr), .D(d[2:1]), .Q(q), .VDD(VDD), .VSS(VSS));\n"
        "INV i (.A(addr[0]), .Y(d[3]), .VDD(VDD), .VSS(VSS));"
    )), library=BUS_LIB)
    top = design.modules[0]
    assert names(top.pins) == ["ck", "addr[1]", "addr[0]", "q", "VDD", "VSS"]
    ram, inv = top.instances
    # A<1> A<0> take addr msb first; D[0] D[1] are listed ascending in the library
    assert names(ram.nets) == ["ck", "addr[1]", "addr[0]", "d[1]", "d[2]", "q", "VDD", "VSS"]
    assert names(inv.nets) == ["addr[0]", "d[3]", "VDD", "VSS"]


def test_bus_ranges_keep_their_direction_through_hierarchy():
    design = run("""
module sub (y, a, VDD, VSS);
  input [4:7] a; output y; inout VDD, VSS;
  INV g (.A(a[5]), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule
module top (p, q, y, VDD, VSS);
  input [1:0] p; input [9:8] q; output y; inout VDD, VSS;
  sub u (.a({p, q}), .y(y), .VDD(VDD), .VSS(VSS));
endmodule
""")
    sub, top = design.modules
    assert names(sub.pins) == ["y", "a[4]", "a[5]", "a[6]", "a[7]", "VDD", "VSS"]
    assert names(sub.instances[0].nets) == ["a[5]", "y", "VDD", "VSS"]
    assert names(top.pins) == ["p[1]", "p[0]", "q[9]", "q[8]", "y", "VDD", "VSS"]
    assert names(top.instances[0].nets) == ["y", "p[1]", "p[0]", "q[9]", "q[8]", "VDD", "VSS"]


def test_assign_merges_buses_bit_by_bit():
    design = run(BUS_TOP.format(body=(
        "assign d[1:0] = addr;\n"
        "RAM u (.CK(ck), .A(d[1:0]), .D(d[3:2]), .Q(q), .VDD(VDD), .VSS(VSS));"
    )), library=BUS_LIB)
    assert names(design.modules[0].instances[0].nets) == [
        "ck", "addr[1]", "addr[0]", "d[2]", "d[3]", "q", "VDD", "VSS",
    ]


@pytest.mark.parametrize(
    "body, message",
    [
        ("INV i (.A(addr), .Y(q), .VDD(VDD), .VSS(VSS));",
         "pin 'A' of cell 'INV' is 1 bit wide, but 'addr' is 2 (instance 'i')"),
        ("INV i (.A(ck[0]), .Y(q), .VDD(VDD), .VSS(VSS));",
         "'ck[0]' selects bits of 'ck', which is not a bus"),
        ("INV i (.A(addr[2]), .Y(q), .VDD(VDD), .VSS(VSS));", "'addr[2]' is outside 'addr[1:0]'"),
        ("assign d = addr;", "assign 'd = addr': left side is 4 bits wide, right side 2"),
    ],
)
def test_bus_errors(body, message):
    err = resolve_error(BUS_TOP.format(body=body), library=BUS_LIB)
    assert err.message == message
    assert err.location.line == 5


def test_stub_mode_is_not_available_yet():
    assert "not supported yet" in resolve_error(SUB, on_missing="stub").message
