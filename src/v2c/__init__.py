"""v2c — physical Verilog netlist to CDL converter for staged LVS."""

import sys

# Checked here, in syntax every Python 3 can parse, so an old interpreter gets
# one clear line instead of a SyntaxError from a module further down.
if sys.version_info < (3, 8):  # noqa: UP036 -- the point is to run on older ones
    raise SystemExit(
        "v2c: error: Python 3.8 or newer is required; this is Python %d.%d (%s)"  # noqa: UP031
        % (sys.version_info[0], sys.version_info[1], sys.executable)
    )

__version__ = "0.0.0"
