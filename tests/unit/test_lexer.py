import pytest

from v2c.errors import Location, ParseError
from v2c.verilog.lexer import tokenize


def lex(src: str) -> list[tuple[str, str]]:
    return [(t.kind, t.text) for t in tokenize(src) if t.kind != "eof"]


def test_tokens_of_an_instance():
    assert lex("INV u1 (.A(n[3]), .B(1'b0));") == [
        ("id", "INV"), ("id", "u1"), ("sym", "("),
        ("sym", "."), ("id", "A"), ("sym", "("), ("id", "n"),
        ("sym", "["), ("number", "3"), ("sym", "]"), ("sym", ")"), ("sym", ","),
        ("sym", "."), ("id", "B"), ("sym", "("), ("based", "1'b0"), ("sym", ")"),
        ("sym", ")"), ("sym", ";"),
    ]


def test_escaped_identifier_keeps_its_spelling_and_ends_at_whitespace():
    assert lex(r"\u_core/data_reg[3] , \a+b;c ") == [
        ("id", r"\u_core/data_reg[3]"), ("sym", ","), ("id", r"\a+b;c"),
    ]


def test_comments_are_dropped_and_locations_survive_them():
    src = "// header\nmodule /* a\nb */ top ;\n"
    assert [(t.text, t.line, t.column) for t in tokenize(src)] == [
        ("module", 2, 1), ("top", 3, 6), (";", 3, 10), ("", 4, 1),
    ]


def test_crlf_line_endings():
    assert [(t.text, t.line) for t in tokenize("module\r\ntop;\r\n")] == [
        ("module", 1), ("top", 2), (";", 2), ("", 3),
    ]


def test_structurally_empty_directives_are_skipped():
    assert lex("`timescale 1ns/1ps\n`celldefine\nmodule") == [("id", "module")]


@pytest.mark.parametrize(
    "src, message, line, column",
    [
        ("module top;\n  x = 1;", "unexpected character '='", 2, 5),
        ("a /* never closed", "unterminated block comment", 1, 3),
        ("wire caf\xe9;", "non-ASCII byte 0xe9", 1, 9),
        ("`define W 4", "compiler directive `define is not supported", 1, 1),
    ],
)
def test_errors_carry_a_location(src, message, line, column):
    with pytest.raises(ParseError) as exc:
        list(tokenize(src, "t.v"))
    assert message in exc.value.message
    assert exc.value.location == Location("t.v", line, column)
