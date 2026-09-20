# Output flavors

The same resolved netlist has to be acceptable to different consumers. The
differences are small and almost entirely lexical — which is exactly why they
cause silent mismatches rather than loud errors.

Flavors are data, not code paths. Adding one should mean adding a table entry.

| Concern | `calibre` | `netgen` | `klayout` |
|---|---|---|---|
| Bus delimiter | `<>` | `[]` | `[]` |
| `.GLOBAL` for supplies | yes | yes | yes |
| `*.PININFO` in stubs | yes | ignored (comment) | needs reader delegate |
| Name case | preserve, compare case-insensitively | preserve | preserve |
| Escaped identifiers | quote/rewrite per rules below | rewrite | rewrite |
| Comment prefix | `*` | `*` | `*` |
| Line continuation | `+` | `+` | `+` |

## Escaped identifiers

The single most common source of quiet divergence. P&R output is full of names
like:

```verilog
\u_core/data_reg[3]  \mux_out[0]
```

Verilog escaping (backslash ... whitespace) has no CDL equivalent. The converter
must apply a deterministic, documented, reversible rewrite, and the rewrite must
be identical to whatever the extraction side does to the layout names — or every
such net becomes a mismatch.

Policy: configurable per flavor, defaulting to strip the leading backslash and
the trailing space, then map the bus delimiter. Any character remaining that the
target flavor cannot represent is a hard error, not a silent substitution.

## `*.PININFO`

Calibre uses it to establish pin direction on stub subcircuits. netgen treats
`*` lines as comments and ignores it harmlessly. KLayout's SPICE reader does not
handle CDL specifics natively; reading `*.PININFO` there requires a reader
delegate. Emitting it is therefore safe everywhere and useful in two of three
cases.

## Case sensitivity

Calibre's CDL handling is conventionally case-insensitive; Verilog is
case-sensitive. Two nets differing only in case are legal in the input and
collide in the output. This must be detected and reported, not folded silently.

## Verification of flavors

Flavor correctness is not a matter of opinion: for `netgen` and `klayout` the
test is whether those tools parse the output and find the expected cells and
pins. Those checks belong in the test suite and run when the tools are present.
