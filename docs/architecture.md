# Architecture

## Pipeline

```
  physical .v            library .cdl / .sp
       |                        |
       v                        v
  [verilog.parser]        [cdl.libreader]
       |                        |
       |  Design IR             |  CellLibrary
       |  (modules, nets,       |  (cell -> ordered pin list,
       |   instances)           |   pin directions)
       \________________________/
                   |
                   v
             [resolve]                  pin-order resolution,
                   |                    stub synthesis,
                   |  Resolved IR       physical-cell policy
                   v
             [cdl.writer] <--- [cdl.flavors]  (calibre | netgen | klayout)
                   |
                   v
              output .cdl
```

Four stages, four separable concerns. Each stage has one input type and one
output type, so each can be tested in isolation and any stage can be replaced
without touching the others.

## Why a hand-written Verilog parser

The input language is a tiny fixed subset (see `scope.md`). Pulling in Yosys or
slang would mean a heavy dependency, a build step, and an intermediate
representation that discards exactly what we care about — original spelling of
escaped identifiers, declaration order, source line numbers for diagnostics.

A dedicated lexer + recursive-descent parser for this subset is on the order of
several hundred lines, has no dependencies, and can carry source positions into
every error message. If the input grammar ever grows past the P&R subset, that
decision gets revisited — but growing it is not a goal.

## The core problem: pin order

Verilog instance connections are **named**:

```verilog
NAND2X1 u_g1 ( .B(n7), .A(n3), .Y(n9), .VDD(VDD), .VSS(VSS) );
```

CDL instance connections are **positional**:

```
XU_G1 n3 n7 n9 VDD VSS NAND2X1
```

So the converter cannot work from the Verilog alone. It must read the library
CDL, extract each cell's `.SUBCKT` pin order, and reorder accordingly. This is
what `v2lvs -s` does and there is no way around it.

`cdl.libreader` therefore scans `.SUBCKT` headers only — it does not parse
device statements or build a circuit model. It needs the cell name, the ordered
pin list, and, where `*.PININFO` is present, pin directions. Bodies are skipped.
This keeps it fast on multi-megabyte library files.

## Missing cells

A cell instantiated in the netlist but absent from every supplied library is a
hard decision point, not a warning to bury:

- `--on-missing=error` (default): fail, list every missing cell at once.
- `--on-missing=stub`: synthesize a `.SUBCKT` from the instance's own
  connection list, emit `*.PININFO` with directions inferred where possible,
  and record it in the run report.

Stub pin order is then whatever the first instance used, which is arbitrary but
self-consistent — acceptable only because the same tool writes both sides.

## Intermediate representation

Deliberately dumb: a `Design` holding `Module`s, each with ordered `Port`s,
`Net`s and `Instance`s. Nets carry their original Verilog spelling plus a
normalized key. No graph analysis, no connectivity solving — the netlist is
already fully elaborated.

## Flavors

Name escaping, bus delimiters, `.GLOBAL` emission, `*.PININFO` emission and case
handling differ between consumers. Those differences live in `cdl/flavors.py`
as data, and the writer consults them. They must not leak into `resolve` or the
parser. See `flavors.md`.

## Diagnostics

Every error carries file, line and column. A conversion that dies on line
812,401 of a million-instance netlist with "unexpected token" and no location is
useless, and that is the failure mode this tool exists to avoid.
