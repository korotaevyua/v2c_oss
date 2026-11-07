"""Tokenizer for the structural Verilog subset.

Handles escaped identifiers (backslash ... whitespace) as single tokens with
their original spelling preserved, because that spelling is what the CDL writer
has to rewrite deterministically. See docs/flavors.md.

Token kinds:

    id      identifier; escaped ones keep the leading backslash and drop the
            terminating whitespace, so ``\\a/b[3] `` becomes ``\\a/b[3]``.
            An escaped name that is spelled like an ordinary identifier is the
            same identifier in Verilog, so ``\\n1 `` becomes ``n1``; reserved
            words keep the backslash (``\\if``).
    number  unsized decimal, e.g. ``3``
    based   based literal, e.g. ``1'b0``, ``4'hF``
    sym     one of ``( ) [ ] { } ; : , . =``
    eof     end of input

Comments and whitespace are dropped. Of the compiler directives, only the ones
that cannot change the structure of a netlist are accepted and skipped.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import NamedTuple

from ..errors import Location, ParseError


class Token(NamedTuple):
    kind: str
    text: str
    line: int
    column: int


_TOKEN_RE = re.compile(
    r"""
      (?P<ws>[ \t\r\f\v]+)
    | (?P<nl>\n)
    | (?P<lcomment>//[^\n]*)
    | (?P<bcomment>/\*.*?\*/)
    | (?P<id>\\[!-~]+|[A-Za-z_][A-Za-z0-9_$]*)
    | (?P<based>[0-9]*'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ?_]+)
    | (?P<number>[0-9]+)
    | (?P<directive>`[A-Za-z_][A-Za-z0-9_$]*)
    | (?P<sym>[()\[\]{};:,.=])
    """,
    re.VERBOSE | re.DOTALL,
)

# Directives that carry no structural meaning. `timescale takes the rest of
# its line as an argument; the others take none.
_IGNORED_DIRECTIVES = {"`timescale", "`celldefine", "`endcelldefine"}

_SIMPLE_ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")

# Verilog-2005 reserved words (IEEE 1364-2005, annex B).
_RESERVED = frozenset("""
    always and assign automatic begin buf bufif0 bufif1 case casex casez cell cmos
    config deassign default defparam design disable edge else end endcase endconfig
    endfunction endgenerate endmodule endprimitive endspecify endtable endtask event
    for force forever fork function generate genvar highz0 highz1 if ifnone incdir
    include initial inout input instance integer join large liblist library
    localparam macromodule medium module nand negedge nmos nor noshowcancelled not
    notif0 notif1 or output parameter pmos posedge primitive pull0 pull1 pulldown
    pullup pulsestyle_ondetect pulsestyle_onevent rcmos real realtime reg release
    repeat rnmos rpmos rtran rtranif0 rtranif1 scalared showcancelled signed small
    specify specparam strong0 strong1 supply0 supply1 table task time tran tranif0
    tranif1 tri tri0 tri1 triand trior trireg unsigned use uwire vectored wait wand
    weak0 weak1 while wire wor xnor xor
""".split())  # noqa: SIM905 -- a word list reads better


def tokenize(text: str, filename: str = "<input>") -> Iterator[Token]:
    pos = 0
    line = 1
    line_start = 0
    end = len(text)
    match = _TOKEN_RE.match

    while pos < end:
        m = match(text, pos)
        if m is None:
            column = pos - line_start + 1
            raise ParseError(_describe_bad_input(text, pos), Location(filename, line, column))

        kind = m.lastgroup
        tok_text = m.group()
        if kind == "nl":
            line += 1
            line_start = m.end()
        elif kind == "bcomment":
            newlines = tok_text.count("\n")
            if newlines:
                line += newlines
                line_start = pos + tok_text.rindex("\n") + 1
        elif kind == "directive":
            if tok_text not in _IGNORED_DIRECTIVES:
                raise ParseError(
                    f"compiler directive {tok_text} is not supported",
                    Location(filename, line, pos - line_start + 1),
                )
            if tok_text == "`timescale":
                newline = text.find("\n", m.end())
                pos = end if newline < 0 else newline
                continue
        elif kind not in ("ws", "lcomment"):
            if kind == "id" and tok_text[0] == "\\":
                body = tok_text[1:]
                if _SIMPLE_ID_RE.fullmatch(body) and body not in _RESERVED:
                    tok_text = body
            yield Token(kind, tok_text, line, pos - line_start + 1)
        pos = m.end()

    yield Token("eof", "", line, pos - line_start + 1)


def _describe_bad_input(text: str, pos: int) -> str:
    if text.startswith("/*", pos):
        return "unterminated block comment"
    ch = text[pos]
    if ch == "\\":
        return "empty escaped identifier"
    if ord(ch) > 0x7F:
        return f"non-ASCII byte 0x{ord(ch):02x} outside a comment"
    return f"unexpected character {ch!r}"
