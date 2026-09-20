# Test plan

Three layers, in order of how often they run:

1. **Unit** — parser, library reader, resolver, writer, in isolation. Fast.
2. **Golden** — small synthetic netlist + small library in, expected CDL out,
   byte-compared after normalization. This is the main regression net.
3. **Differential** — real netlists through both this tool and a reference
   converter, normalized and diffed. Runs only where the reference tool exists.
4. **Consumer** — output fed to netgen / KLayout, checked for parse and content.
   Runs only where those tools are installed.

Every case below gets a directory under `tests/golden/cases/<id>-<slug>/` with
`in.v`, `lib.cdl`, `expected.<flavor>.cdl`, and an optional `args` file.

---

## A. Structural basics

| id | case | checks |
|---|---|---|
| A1 | single instance, single cell | end-to-end minimal path |
| A2 | several instances of the same cell | instance naming, no state leakage |
| A3 | hierarchy: top instantiating a submodule | `.SUBCKT` per module, correct nesting |
| A4 | top-level port order | ports emitted in declaration order, not sorted |
| A5 | empty module | valid empty `.SUBCKT`, no crash |
| A6 | module with only physical cells | no signal nets at all |

## B. Pin-order resolution

The core of the tool. Most valuable tests in the suite.

| id | case | checks |
|---|---|---|
| B1 | named connections in an order differing from the library | reordering actually happens |
| B2 | instance omits a pin the library declares | placeholder net, documented policy |
| B3 | instance connects a pin absent from the library | hard error with cell + pin named |
| B4 | same cell instantiated with different connection subsets | per-instance resolution, no caching bug |
| B5 | cell missing from library, `--on-missing=error` | non-zero exit, all missing cells listed at once |
| B6 | cell missing from library, `--on-missing=stub` | stub emitted, pin order self-consistent |
| B7 | library defines the same cell twice with different pin order | conflict detected, not last-wins |
| B8 | two libraries supplied, cell in the second | search order respected |

## C. Names and nets

| id | case | checks |
|---|---|---|
| C1 | escaped identifier with `/` | rewrite per flavor policy |
| C2 | escaped identifier with `[` `]` | interaction of escaping and bus mapping |
| C3 | bus `wire [3:0] d` with bit selects | bit-blasting, delimiter per flavor |
| C4 | bus with non-zero LSB, e.g. `[7:4]` | index arithmetic |
| C5 | descending vs ascending ranges | orientation preserved |
| C6 | two nets differing only in case | collision reported, not folded |
| C7 | net name containing a character the flavor cannot express | hard error |
| C8 | very long hierarchical name | truncation policy is explicit or absent by design |

## D. Power and ground

Input is a physical netlist, so PG is present; these test that it survives.

| id | case | checks |
|---|---|---|
| D1 | per-instance PG connections | PG passed through in correct pin positions |
| D2 | `supply0` / `supply1` declarations | recognized, mapped to global nets |
| D3 | `.GLOBAL` emission toggled on/off | flag honored, nets still resolve |
| D4 | two supply domains | both preserved, no merging |
| D5 | level shifter with two supplies on one cell | multi-supply pin ordering |
| D6 | PG net name colliding with a signal name in a submodule | scoping correct |

## E. Physical-only cells

| id | case | checks |
|---|---|---|
| E1 | filler with PG pins only | emitted with no signal pins |
| E2 | tap / well-tie cell | same |
| E3 | endcap | same |
| E4 | decap | same |
| E5 | antenna diode | signal pin plus PG |
| E6 | exclusion list removes a class of cells | filtering matches extraction side |
| E7 | physical cell absent from library | stub with PG only |

## F. Constants and ties

| id | case | checks |
|---|---|---|
| F1 | `1'b0` / `1'b1` on an instance pin | mapped to the configured constant net |
| F2 | explicit tie-hi / tie-lo cells | treated as ordinary cells, untouched |
| F3 | `assign` statement between two nets | net merge or explicit policy |
| F4 | unconnected output pin `.Y()` | placeholder, unique per instance |
| F5 | `1'bx` or `1'bz` | rejected with a clear message |

## G. Macros and black boxes

| id | case | checks |
|---|---|---|
| G1 | macro with vendor CDL supplied | pin order from vendor file |
| G2 | macro with no CDL, stub mode | `*.PININFO` present, directions inferred |
| G3 | macro pin direction not inferable | documented default, warning emitted |
| G4 | macro instantiated inside a submodule | hierarchy + stub interaction |

## H. Robustness and diagnostics

Every case here asserts on the **message**, not just the exit code. A location
in the error is part of the contract.

| id | case | checks |
|---|---|---|
| H1 | duplicate instance name in one module | error naming both lines |
| H2 | net used but never declared | error or documented implicit-wire policy |
| H3 | duplicate module definition | error |
| H4 | truncated file mid-instance | error with line number, no traceback |
| H5 | non-ASCII bytes in input | error, no crash |
| H6 | library file that is not CDL at all | error identifies the file |
| H7 | CRLF line endings | handled |

## I. Flavors

| id | case | checks |
|---|---|---|
| I1 | one input, three flavors | outputs differ exactly where the table says |
| I2 | netgen reads the output | `netgen` parses; cells and pins match |
| I3 | KLayout reads the output | `NetlistSpiceReader` parses; cells and pins match |
| I4 | flavor-specific escaping round-trip | rewrite is deterministic and documented |

## J. Differential testing against a reference converter

Runs in an environment where a commercial converter is available. Not part of
the public suite; the harness is public, the inputs are not.

Procedure:

1. Run real physical netlists through both converters.
2. Normalize both outputs: strip comments and headers, sort instances by name,
   canonicalize whitespace and continuations.
3. Diff.
4. Each difference is triaged as (a) a bug here, (b) a deliberate divergence, or
   (c) a reference-tool quirk not worth copying. Every (b) and (c) becomes a
   documented entry plus a synthetic golden case.

The important property: a synthetic case reproducing the *shape* of the problem
can be published without exposing the PDK or the design. That is how real-silicon
findings reach the public suite.

## K. Scale

| id | case | checks |
|---|---|---|
| K1 | ~1M instances | wall time and peak RSS within a stated budget |
| K2 | library with ~10k cells | `.SUBCKT` scan stays linear |
| K3 | deep hierarchy, ~50 levels | no recursion limit failures |

---

## Bootstrapping order

Not all at once. A useful first pass is A1–A4, B1, B5, B6, C3, D1, E1, H4 —
that is enough to convert a trivial but real design and to fail comprehensibly
on the things that actually break first.
