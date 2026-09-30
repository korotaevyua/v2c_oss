import pytest

from v2c.errors import ParseError
from v2c.model import Concat, Const, NetRef
from v2c.verilog.parser import parse_text

NETLIST = """
module top (y, a, VDD, VSS);
  input a;
  output y;
  inout VDD, VSS;
  wire n1;
  wire [3:0] bus;
  supply0 gnd;

  INV u1 (.A(a), .Y(n1), .VDD(VDD), .VSS(VSS));
  CELL u2 (.A(bus[2]), .B(bus[3:1]), .C(1'b1), .D({a, n1}), .E());
  TAP tap0 ();
endmodule
"""


def test_ports_follow_the_port_list_not_the_declarations():
    top = parse_text(NETLIST).modules["top"]
    assert [(p.name, p.direction) for p in top.ports] == [
        ("y", "output"), ("a", "input"), ("VDD", "inout"), ("VSS", "inout"),
    ]


def test_net_declarations():
    nets = parse_text(NETLIST).modules["top"].nets
    assert (nets["bus"].msb, nets["bus"].lsb) == (3, 0)
    assert nets["gnd"].is_supply and nets["gnd"].supply_value == 0
    assert not nets["n1"].is_bus and not nets["n1"].is_supply


def test_instances_and_connection_expressions():
    top = parse_text(NETLIST, "t.v").modules["top"]
    u1, u2, tap = top.instances
    assert (u1.cell, u1.name) == ("INV", "u1")
    assert [(c.pin, c.expr) for c in u1.connections] == [
        ("A", NetRef("a")), ("Y", NetRef("n1")), ("VDD", NetRef("VDD")), ("VSS", NetRef("VSS")),
    ]
    assert [c.expr for c in u2.connections] == [
        NetRef("bus", 2, 2), NetRef("bus", 3, 1), Const("1'b1"),
        Concat((NetRef("a"), NetRef("n1"))), None,
    ]
    assert tap.connections == []
    assert str(u1.location) == "t.v:10:3"
    assert str(u1.connections[1].location) == "t.v:10:18"


def test_escaped_names_keep_their_spelling():
    design = parse_text(r"module top (); wire \a/b[0] ; X \u/1  (.A(\a/b[0] )); endmodule")
    top = design.modules["top"]
    assert list(top.nets) == [r"\a/b[0]"]
    assert top.instances[0].name == r"\u/1"
    assert top.instances[0].connections[0].expr == NetRef(r"\a/b[0]")


def test_modules_keep_source_order():
    design = parse_text("module b; endmodule\nmodule a; endmodule\n")
    assert list(design.modules) == ["b", "a"]


@pytest.mark.parametrize(
    "src, message, line",
    [
        ("module top (a);\n  input a;\n  INV u1 (a);\nendmodule",
         "positional port connections are not supported", 3),
        ("module top (input a);\nendmodule", "ANSI-style port declarations", 1),
        ("module top (a, y);\n  input a;\nendmodule",
         "port 'y' has no input, output or inout declaration", 1),
        ("module top (a);\n  input a;\n  output y;\nendmodule",
         "'y' is declared output but is not in the port list of module 'top'", 3),
        ("module top (a);\n  input a;\n  input a;\nendmodule", "'a' is already declared input", 3),
        ("module top;\n  wire n;\n  wire n;\nendmodule", "net 'n' is already declared", 3),
        ("module top (a);\n  input a;\n  always @(a);\nendmodule", "'always' is not supported", 3),
        ("module top (a);\n  input a;\n  assign b = a;\nendmodule",
         "'assign' statements are not supported yet", 3),
        ("module a;\nendmodule\nmodule a;\nendmodule", "module 'a' is already defined at", 3),
        ("module a;\nmodule b;\nendmodule", "missing 'endmodule' for module 'a'", 2),
        # H4: truncated mid-instance
        ("module top (a);\n  input a;\n  INV u1 (.A(a),\n", "found end of file", 4),
        ("module top (a);\n  input a;\n", "unexpected end of file in module 'top'", 3),
    ],
)
def test_errors_carry_a_location(src, message, line):
    with pytest.raises(ParseError) as exc:
        parse_text(src, "t.v")
    assert message in exc.value.message
    assert exc.value.location.file == "t.v"
    assert exc.value.location.line == line
