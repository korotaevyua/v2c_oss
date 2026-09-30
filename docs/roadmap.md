# Roadmap

Milestones, not dates.

## M0 — skeleton

Repository layout, scope, architecture, test plan. No working conversion.

## M1 — walking skeleton (this commit)

Convert the simplest real thing end to end: a flat module, a handful of standard
cells, one library CDL, Calibre flavor only.

- Verilog lexer + parser for the P&R subset
- `.SUBCKT` header scanner
- pin-order resolution
- CDL writer
- CLI: `v2c convert design.v -s lib.cdl -o design.cdl`
- golden cases A1–A4, B1

Done when a small design converts and Calibre accepts the result.

The parser accepts the whole P&R subset; constructs that still need a policy
are rejected by the resolver or writer with a located "not supported yet"
error, never passed through: buses, escaped identifiers, constants,
concatenations, `supply0`/`supply1`, unconnected pins, `--on-missing=stub`,
and every flavor but `calibre`.

## M2 — the things that break first

- escaped identifiers and bus handling (C group)
- unconnected pins and constants (B2, F1, F4, F5), supply declarations (D2)
- missing cells: error and stub modes (B5–B8, G group)
- physical-only cells (E group)
- diagnostics with file/line/column everywhere (H group)
- the normalizer, and the differential harness

Done when real post-route netlists convert without hand-editing.

## M3 — flavors and open-source consumers

- flavor tables, `--flavor` on the CLI
- netgen and KLayout output validated by those tools
- a documented end-to-end example on an open PDK, so the project is
  reproducible by someone without commercial tools

Done when someone outside a commercial environment can run the whole thing.

## M4 — scale and packaging

- performance work against the K group budgets
- published package, versioning, changelog
- CI running unit + golden + consumer tests

## Later, maybe

- LEF-assisted pin-direction inference for stubs
- a `v2c check` subcommand that reports library coverage for a netlist before
  conversion is attempted
- reading the extracted-layout netlist to cross-check name conventions
