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
suite but substance does.

Cases derived from real designs must be rewritten as synthetic inputs that
reproduce the shape of the problem and nothing else — no PDK cell names, no
design hierarchy. See `docs/test-plan.md`, section J.
