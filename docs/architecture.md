# Architecture

## Pipeline

```
  physical .v (.gz),     library .cdl / .sp (.gz),
  one or more files      following .INCLUDE
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
                   |                    bit-blasting, assign merging
                   |  Resolved IR       (planned: stubs, physical cells)
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
CDL, extract each cell's `.SUBCKT` pin order, and reorder accordingly. v2lvs
does the same with `-lsp`/`-lsr`, and there is no way around it.

`cdl.libreader` therefore scans `.SUBCKT` headers only — it does not parse
device statements or build a circuit model. It needs the cell name, the ordered
pin list, and, where `*.PININFO` is present, pin directions. Bodies are skipped.
This keeps it fast on multi-megabyte library files. `.INCLUDE` statements are
followed, so one file listing every library CDL can stand for all of them.

## Missing cells

A cell instantiated in the netlist but absent from the netlist's own modules
and from every supplied library is a hard decision point, not a warning to
bury:

- `--on-missing=error` (default): fail, list every missing cell at once with
  its first use, and point out near matches (same name in another case).
- `--on-missing=stub` (planned, M2): synthesize a `.SUBCKT` from the
  instance's own connection list, emit `*.PININFO` with directions inferred
  where possible, and record it in the run report.

Stub pin order is then whatever the first instance used, which is arbitrary but
self-consistent — acceptable only because the same tool writes both sides.

## Intermediate representation

Deliberately dumb: a `Design` holding `Module`s, each with ordered `Port`s,
`Net`s, `Instance`s and `assign`s. Names keep their Verilog spelling, except
that an escaped name spelled like a plain identifier (`\n1 `) becomes that
identifier, as Verilog defines it. No graph analysis, no connectivity solving —
the netlist is already fully elaborated.

The resolver turns this into the Resolved IR: per module, pins and instance
connections as positional lists of `Bit`s (a scalar name, or one bit of a
bus). Mapping a `Bit` to text — `d<3>` for Calibre — is the writer's job.

## Flavors

Name escaping, bus delimiters, `.GLOBAL` emission, `*.PININFO` emission and case
handling differ between consumers. Those differences live in `cdl/flavors.py`
as data, and the writer consults them. They must not leak into `resolve` or the
parser. See `flavors.md`.

## Diagnostics

Every error about the input carries file, line and column. A conversion that
dies on line 812,401 of a million-instance netlist with "unexpected token" and
no location is useless, and that is the failure mode this tool exists to avoid.
