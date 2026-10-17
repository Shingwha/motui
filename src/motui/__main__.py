"""``python -m motui``: the demo's entry point.

The one documented way to run the shipped demo (``ref/demo.md`` §1): the
module entry the toolkit's peers use (``python -m rich``, ``python -m
textual``), so a plain ``pip install motui`` gets the exhibits without a
console script that would read as a CLI tool.  This file is only the
dispatch; the demo lives in :mod:`motui.demo`.
"""

from __future__ import annotations

from motui.demo import main

if __name__ == "__main__":
    raise SystemExit(main())
