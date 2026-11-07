# Roadmap

Milestones, not dates. `[x]` done, `[ ]` open.

## Where things stand

M1 is complete in code; its acceptance check — Calibre reading the output of a
real design — has not been run yet. M2 is in progress, driven by the first real
post-route netlist: each construct it stopped on (`assign`, buses, gzip input,
hierarchy split across files) has been handled in turn.

Constructs without a policy yet are rejected with a located "not supported
yet" error, never passed through: escaped names other than plain identifiers,
constants, unconnected pins, `supply0`/`supply1`, two ports joined by `assign`,
`--on-missing=stub`, and every flavor but `calibre`.

## M0 — skeleton

- [x] repository layout, scope, architecture, test plan

## M1 — walking skeleton

Convert the simplest real thing end to end: a flat module, a handful of standard
cells, one library CDL, Calibre flavor only.

- [x] Verilog lexer + parser for the P&R subset
- [x] `.SUBCKT` header scanner, following `.INCLUDE`
- [x] `-s` libraries `.INCLUDE`d in the output, `-lsp` for pin order only (as v2lvs)
- [x] pin-order resolution, hierarchy, top-module inference
- [x] CDL writer
- [x] CLI: `v2c convert design.v -s lib.cdl -o design.cdl`
- [x] golden cases A1–A4, B1, B9, B10
- [ ] Calibre accepts the output of a small real design

Done when a small design converts and Calibre accepts the result.

## M2 — the things that break first

- [x] bus handling: bit-blasting, selects, concatenations (C3–C5)
- [x] `assign` between nets, bit by bit (F3)
- [x] gzipped netlists and libraries; several netlist files for one design
- [x] runs on Python 3.8 with nothing installed
- [x] missing cells: all listed at once, with near-match hints (B5)
- [x] library conflicts and search order (B7, B8)
- [ ] escaped identifiers (C1, C2), case collisions (C6), unrepresentable
      characters (C7, C8)
- [ ] unconnected pins and constants (B2, F1, F4, F5)
- [ ] supply declarations (D2, D3)
- [ ] stub mode for missing cells (B6, G group)
- [ ] physical-only cells (E group)
- [ ] remaining diagnostics: duplicate instance names (H1), undeclared nets (H2)
- [ ] the normalizer, and the differential harness

Done when real post-route netlists convert without hand-editing.

## M3 — flavors and open-source consumers

- [ ] enable the netgen and KLayout flavors (the table and `--flavor` exist)
- [ ] netgen and KLayout output validated by those tools
- [ ] a documented end-to-end example on an open PDK, so the project is
      reproducible by someone without commercial tools

Done when someone outside a commercial environment can run the whole thing.

## M4 — scale and packaging

- [ ] performance work against the K group budgets
- [ ] published package, versioning, changelog
- [ ] CI running unit + golden + consumer tests

## Later, maybe

- LEF-assisted pin-direction inference for stubs
- a `v2c check` subcommand that reports library coverage for a netlist before
  conversion is attempted
- reading the extracted-layout netlist to cross-check name conventions
