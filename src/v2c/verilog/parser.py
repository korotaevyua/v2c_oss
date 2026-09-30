"""Recursive-descent parser producing a Design.

Accepts only what P&R tools emit; see docs/scope.md for the grammar boundary.
Anything outside it is a ParseError with a location, never a silent skip.

    source      := { module } EOF
    module      := 'module' id [ '(' [ id { ',' id } ] ')' ] ';'
                   { item } 'endmodule'
    item        := direction [ 'wire' ] [ range ] id { ',' id } ';'
                 | ( 'wire' | 'supply0' | 'supply1' ) [ range ] id { ',' id } ';'
                 | id id '(' [ connection { ',' connection } ] ')' ';'
    direction   := 'input' | 'output' | 'inout'
    range       := '[' number ':' number ']'
    connection  := '.' id '(' [ expr ] ')'
    expr        := id [ '[' number [ ':' number ] ']' ]
                 | number | based
                 | '{' expr { ',' expr } '}'

Port lists are non-ANSI, connections are named: that is what P&R tools write.
Whether the resolver can convert every construct parsed here is a separate
question, answered in resolve.py.
"""

from __future__ import annotations

from ..errors import Location, ParseError
from ..model import Concat, Connection, Const, Design, Expr, Instance, Module, Net, NetRef, Port
from .lexer import Token, tokenize

_DIRECTIONS = {"input", "output", "inout"}
_NET_KINDS = {"wire", "supply0", "supply1"}

# Behavioral and RTL keywords: recognizable, and out of scope by design.
_OUT_OF_SCOPE = {
    "always", "initial", "reg", "integer", "real", "time", "event", "parameter",
    "localparam", "defparam", "generate", "genvar", "function", "task", "specify",
    "primitive", "tri", "tri0", "tri1", "triand", "trior", "trireg", "wand", "wor",
    "and", "nand", "or", "nor", "xor", "xnor", "buf", "not", "bufif0", "bufif1",
    "notif0", "notif1", "pullup", "pulldown",
}
# Part of the P&R subset, but not handled yet (see docs/test-plan.md, F3).
_NOT_YET = {"assign"}

_KEYWORDS = {"module", "endmodule"} | _DIRECTIONS | _NET_KINDS | _OUT_OF_SCOPE | _NOT_YET


def parse_file(path: str) -> Design:
    # latin-1 maps every byte to one character, so a stray non-ASCII byte
    # reaches the lexer and is reported with its location instead of failing
    # the decode with no location at all.
    with open(path, encoding="latin-1") as f:
        text = f.read()
    return parse_text(text, path)


def parse_text(text: str, filename: str = "<input>") -> Design:
    return _Parser(text, filename).parse()


class _Parser:
    def __init__(self, text: str, filename: str) -> None:
        self._filename = filename
        self._tokens = tokenize(text, filename)
        self._tok: Token = next(self._tokens)

    # --- token helpers ---------------------------------------------------

    def _advance(self) -> Token:
        tok = self._tok
        self._tok = next(self._tokens)
        return tok

    def _loc(self, tok: Token | None = None) -> Location:
        tok = tok or self._tok
        return Location(self._filename, tok.line, tok.column)

    def _error(self, message: str, tok: Token | None = None) -> ParseError:
        return ParseError(message, self._loc(tok))

    def _found(self) -> str:
        return "end of file" if self._tok.kind == "eof" else f"'{self._tok.text}'"

    def _at_sym(self, ch: str) -> bool:
        return self._tok.kind == "sym" and self._tok.text == ch

    def _at_keyword(self, word: str) -> bool:
        return self._tok.kind == "id" and self._tok.text == word

    def _expect_sym(self, ch: str) -> Token:
        if not self._at_sym(ch):
            raise self._error(f"expected '{ch}', found {self._found()}")
        return self._advance()

    def _expect_id(self, what: str) -> Token:
        tok = self._tok
        if tok.kind != "id" or tok.text in _KEYWORDS:
            raise self._error(f"expected {what}, found {self._found()}")
        return self._advance()

    def _expect_number(self) -> int:
        if self._tok.kind != "number":
            raise self._error(f"expected a number, found {self._found()}")
        return int(self._advance().text)

    # --- grammar ---------------------------------------------------------

    def parse(self) -> Design:
        design = Design()
        while self._tok.kind != "eof":
            if not self._at_keyword("module"):
                raise self._error(f"expected 'module', found {self._found()}")
            module = self._module()
            previous = design.modules.get(module.name)
            if previous is not None:
                raise ParseError(
                    f"module '{module.name}' is already defined at {previous.location}",
                    module.location,
                )
            design.modules[module.name] = module
        return design

    def _module(self) -> Module:
        self._advance()  # 'module'
        name_tok = self._expect_id("a module name")
        module = Module(name_tok.text, location=self._loc(name_tok))

        header: list[Token] = []
        if self._at_sym("("):
            self._advance()
            if not self._at_sym(")"):
                header.append(self._header_port())
                while self._at_sym(","):
                    self._advance()
                    header.append(self._header_port())
            self._expect_sym(")")
        self._expect_sym(";")

        # name -> (direction, msb, lsb, declaration token)
        directions: dict[str, tuple[str, int | None, int | None, Token]] = {}
        while not self._at_keyword("endmodule"):
            tok = self._tok
            if tok.kind == "eof":
                raise self._error(f"unexpected end of file in module '{module.name}'")
            if tok.kind != "id":
                raise self._error(f"expected a declaration or an instance, found {self._found()}")
            if tok.text in _DIRECTIONS:
                self._direction_decl(directions)
            elif tok.text == "module":
                raise self._error(f"missing 'endmodule' for module '{module.name}'")
            elif tok.text in _NET_KINDS:
                self._net_decl(module)
            elif tok.text in _OUT_OF_SCOPE:
                raise self._error(
                    f"'{tok.text}' is not supported: only structural netlists are "
                    f"accepted (see docs/scope.md)"
                )
            elif tok.text in _NOT_YET:
                raise self._error(f"'{tok.text}' statements are not supported yet")
            else:
                module.instances.append(self._instance())
        self._advance()  # 'endmodule'

        self._bind_ports(module, header, directions)
        return module

    def _header_port(self) -> Token:
        if self._tok.kind == "id" and self._tok.text in _DIRECTIONS:
            raise self._error(
                "ANSI-style port declarations are not supported; "
                "expected a plain list of port names"
            )
        return self._expect_id("a port name")

    def _bind_ports(self, module: Module, header: list[Token], directions: dict) -> None:
        seen: set[str] = set()
        for tok in header:
            if tok.text in seen:
                raise self._error(f"port '{tok.text}' is listed twice", tok)
            seen.add(tok.text)
            decl = directions.get(tok.text)
            if decl is None:
                raise self._error(
                    f"port '{tok.text}' has no input, output or inout declaration", tok
                )
            direction, msb, lsb, _ = decl
            module.ports.append(Port(tok.text, direction, msb, lsb, self._loc(tok)))
        for name, (direction, _, _, tok) in directions.items():
            if name not in seen:
                raise self._error(
                    f"'{name}' is declared {direction} but is not in the port list "
                    f"of module '{module.name}'",
                    tok,
                )

    def _range(self) -> tuple[int | None, int | None]:
        if not self._at_sym("["):
            return None, None
        self._advance()
        msb = self._expect_number()
        self._expect_sym(":")
        lsb = self._expect_number()
        self._expect_sym("]")
        return msb, lsb

    def _name_list(self) -> list[Token]:
        names = [self._expect_id("a name")]
        while self._at_sym(","):
            self._advance()
            names.append(self._expect_id("a name"))
        self._expect_sym(";")
        return names

    def _direction_decl(self, directions: dict) -> None:
        direction = self._advance().text
        if self._at_keyword("wire"):
            self._advance()
        msb, lsb = self._range()
        for tok in self._name_list():
            previous = directions.get(tok.text)
            if previous is not None:
                raise self._error(
                    f"'{tok.text}' is already declared {previous[0]} at {self._loc(previous[3])}",
                    tok,
                )
            directions[tok.text] = (direction, msb, lsb, tok)

    def _net_decl(self, module: Module) -> None:
        kind = self._advance().text
        msb, lsb = self._range()
        for tok in self._name_list():
            previous = module.nets.get(tok.text)
            if previous is not None:
                raise self._error(
                    f"net '{tok.text}' is already declared at {previous.location}", tok
                )
            supply = kind.startswith("supply")
            module.nets[tok.text] = Net(
                tok.text,
                is_supply=supply,
                supply_value=int(kind[-1]) if supply else None,
                msb=msb,
                lsb=lsb,
                location=self._loc(tok),
            )

    def _instance(self) -> Instance:
        cell_tok = self._expect_id("a cell name")
        name_tok = self._expect_id("an instance name")
        instance = Instance(name_tok.text, cell_tok.text, location=self._loc(cell_tok))
        self._expect_sym("(")
        if not self._at_sym(")"):
            instance.connections.append(self._connection())
            while self._at_sym(","):
                self._advance()
                instance.connections.append(self._connection())
        self._expect_sym(")")
        self._expect_sym(";")
        return instance

    def _connection(self) -> Connection:
        if not self._at_sym("."):
            if self._tok.kind in ("id", "number", "based") or self._at_sym("{"):
                raise self._error(
                    "positional port connections are not supported; "
                    "expected a named connection '.PIN(net)'"
                )
            raise self._error(f"expected a named connection '.PIN(net)', found {self._found()}")
        dot = self._advance()
        pin = self._expect_id("a pin name").text
        self._expect_sym("(")
        expr = None if self._at_sym(")") else self._expr()
        self._expect_sym(")")
        return Connection(pin, expr, self._loc(dot))

    def _expr(self) -> Expr:
        tok = self._tok
        if tok.kind in ("number", "based"):
            self._advance()
            return Const(tok.text)
        if self._at_sym("{"):
            self._advance()
            parts = [self._expr()]
            while self._at_sym(","):
                self._advance()
                parts.append(self._expr())
            self._expect_sym("}")
            return Concat(tuple(parts))
        name = self._expect_id("a net name").text
        if not self._at_sym("["):
            return NetRef(name)
        self._advance()
        msb = lsb = self._expect_number()
        if self._at_sym(":"):
            self._advance()
            lsb = self._expect_number()
        self._expect_sym("]")
        return NetRef(name, msb, lsb)
