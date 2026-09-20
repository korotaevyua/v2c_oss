# v2c_oss

An open-source converter from a **physical (post-route) Verilog netlist** to
**CDL**, for use as a standalone step in a staged LVS flow.

> Status: **M0 — skeleton.** Layout, scope and test plan are in place; the
> conversion itself is not implemented yet. See [docs/roadmap.md](docs/roadmap.md).

## What it is for

In a staged LVS flow, extraction, netlist conversion and comparison are three
separate steps with three inspectable artifacts. Comparators such as netgen and
KLayout can read structural Verilog directly and convert it internally — which
is convenient right up to the moment LVS fails, because then a translation bug
and a real mismatch look exactly the same.

This tool makes that step a file you can open, grep and diff.

The input is the netlist written at the end of the P&R flow, with power and
ground already present. Supply inference, RTL and SystemVerilog are explicitly
out of scope — see [docs/scope.md](docs/scope.md).

## Intended use

```
v2c convert design.v -s stdcells.cdl -s macros.cdl -o design.cdl
```

Verilog connections are named, CDL connections are positional, so the library
CDL is not optional: it is where the pin order comes from.

Output flavors (`--flavor calibre|netgen|klayout`) cover the lexical
differences between consumers — bus delimiters, escaping, `*.PININFO`.

## Documentation

| | |
|---|---|
| [docs/scope.md](docs/scope.md) | what this converts, and what it deliberately does not |
| [docs/architecture.md](docs/architecture.md) | pipeline, IR, why the parser is hand-written |
| [docs/flavors.md](docs/flavors.md) | Calibre / netgen / KLayout output differences |
| [docs/test-plan.md](docs/test-plan.md) | the test suite, case by case |
| [docs/roadmap.md](docs/roadmap.md) | milestones |

## Development

```
pip install -e ".[dev]"
pytest
```

## License

Apache-2.0.
