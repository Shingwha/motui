"""``python -m motui.demo``: the demo's module entry, beside the package one.

The documented spelling is ``python -m motui`` (:mod:`motui.__main__`); this
file exists so the demo package is runnable on its own too, the same
three-mode :func:`~motui.demo.main`.
"""

from __future__ import annotations

from . import main

if __name__ == "__main__":
    raise SystemExit(main())
