"""The smallest motui app: a Text row and an Input, painted once headless.

    uv run python examples/quickstart.py --headless

The example always uses a ``HeadlessScreen``, so a run without a TTY exits 0.
"""

from __future__ import annotations

import argparse
import contextlib
import sys

from motui import App, Input, Text
from motui.terminal import HeadlessScreen, TerminalOptions


def _utf8_stdout() -> None:
    """The Input prompt is a Unicode glyph; a cp1252 console cannot hold it."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):
        reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description="motui quickstart")
    parser.add_argument("--headless", action="store_true", help="paint without a terminal")
    parser.parse_args(argv)
    app = App(terminal=TerminalOptions(screen=HeadlessScreen(60, 6)), auto=False)
    app.add(Text("Hello, motui."))
    app.add(Input("type here"))
    app.paint_now()
    for row in app.workspace.rows[:3]:
        print(row.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
