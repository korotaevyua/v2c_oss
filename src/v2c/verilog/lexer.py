"""Tokenizer for the structural Verilog subset.

Handles escaped identifiers (backslash ... whitespace) as single tokens with
their original spelling preserved, because that spelling is what the CDL writer
has to rewrite deterministically. See docs/flavors.md.

Token kinds:

    id      identifier; escaped ones keep the leading backslash and drop the
            terminating whitespace, so ``\\a/b[3] `` becomes ``\\a/b[3]``
    number  unsized decimal, e.g. ``3``
    based   based literal, e.g. ``1'b0``, ``4'hF``
    sym     one of ``( ) [ ] { } ; : , .``
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
    | (?P<sym>[()\[\]{};:,.])
    """,
    re.VERBOSE | re.DOTALL,
)

# Directives that carry no structural meaning. `timescale takes the rest of
# its line as an argument; the others take none.
_IGNORED_DIRECTIVES = {"`timescale", "`celldefine", "`endcelldefine"}


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
