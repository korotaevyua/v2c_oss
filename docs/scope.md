# Scope

## The one job

Convert a **physical (post-route) gate-level Verilog netlist** into a **CDL netlist**
suitable for LVS, as a standalone, observable step.

Input is the netlist written at the very end of the P&R flow (e.g. Innovus
`saveNetlist -phys` with power/ground included). Output is CDL that an LVS
comparator will accept as the source/schematic side.

## Why a separate step

Some LVS comparators (netgen, KLayout) can read structural Verilog directly and
do this conversion internally. That is convenient and it is also the problem:
when LVS fails, there is no artifact to inspect, so a translation bug and a real
layout/schematic mismatch look identical.

A standalone converter produces a file you can open, grep, and diff against the
previous run. Debuggability is the point; capability is not.

This mirrors a staged LVS flow where extraction, conversion and comparison are
three separate, individually inspectable steps.

## In scope

- Structural Verilog as emitted by P&R tools: `module` / `input` / `output` /
  `inout` / `wire` / `supply0` / `supply1` / instances with named port
  connections, bus declarations and bit selects, escaped identifiers.
- Pin-order resolution against a library CDL/SPICE (see `architecture.md`) —
  Verilog connections are named, CDL connections are positional.
- Stub `.SUBCKT` generation with `*.PININFO` for cells absent from the library.
- Physical-only cells (fillers, taps, endcaps, decaps, antenna diodes).
- Multiple output flavors (Calibre / netgen / KLayout) — see `flavors.md`.
- A normalizer for differential testing against a reference converter.

## Out of scope

Explicitly, and on purpose:

- **RTL.** No behavioral constructs, no `always`, no expressions, no
  parameters, no generate. If a human wrote it by hand, it is out of scope.
- **SystemVerilog.** The input language is the narrow subset P&R tools emit.
- **Synthesis, elaboration, optimization.** No logic is interpreted.
- **Power inference.** Power/ground arrive in the input netlist. This tool does
  not guess supplies, does not insert PG pins on instances that lack them, and
  does not implement the `v2lvs -p` / `-sp` family of behaviors. If the input
  has no PG, that is an input problem, not a conversion problem.
- **Extraction and comparison.** Those stay with whatever LVS tool is in use.

## Non-goals

- Being a drop-in `v2lvs` clone. Compatible where it matters, not bug-for-bug.
- Supporting every PDK's naming quirks in core. Those belong in flavor configs.
