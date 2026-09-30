# Golden cases

One directory per case, named `<id>-<slug>/` where `<id>` is the identifier
from `docs/test-plan.md`:

```
A1-single-instance/
  in.v
  lib.cdl
  expected.calibre.cdl
  args              # optional, extra CLI arguments, one per line
```

Cases are compared after normalization, so formatting churn does not break the
suite but substance does. Until the normalizer lands (M2), the comparison is
line by line with comment lines ignored; `*.PININFO` and other `*.` lines
still count.

`test_golden.py` runs every `expected.<flavor>.cdl` it finds, as
`v2c convert in.v -s lib.cdl --flavor <flavor>` from inside the case directory.

Cases derived from real designs must be rewritten as synthetic inputs that
reproduce the shape of the problem and nothing else — no PDK cell names, no
design hierarchy. See `docs/test-plan.md`, section J.
