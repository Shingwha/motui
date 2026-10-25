"""A Markdown fenced line that scrolls instead of wrapping.

    uv run python examples/code.py --headless

``WrapMode.OVERFLOW`` keeps the code line at its natural width and a
two-axis ``ScrollPanel`` reaches its tail.  The run always uses a headless
screen, so a pipe exits 0; the marker check makes the scroll observable.
"""

from __future__ import annotations

import argparse

from motui import Markdown, ScrollPanel, headless_tui
from motui.kernel.text import WrapMode

VIEWPORT_WIDTH, VIEWPORT_HEIGHT = 60, 14
SLOT_HEIGHT, MARKER = 12, "tail-marker"
DOCUMENT = (
    "# code, unwrapped\n\nLong lines keep their natural width and scroll.\n\n"
    "```python\n"
    'def render(frame, samples): return f"{samples[frame % len(samples)]:.3f}"'
    f"  # {MARKER}\n"
    "```\n"
)


def headless() -> int:
    """Render, scroll to the right edge, and verify the tail marker."""
    panel = ScrollPanel(
        Markdown(DOCUMENT, code_wrap=WrapMode.OVERFLOW),
        axis="both",
        height=SLOT_HEIGHT,
        bar=True,
    )
    tui = headless_tui(VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
    tui.add(panel)
    tui.paint()
    panel.scroll_x_to_end()
    tui.paint()
    text = "\n".join(row.text for row in tui.rows)
    if MARKER not in text:
        print("code: the long line's tail is not reachable")
        return 1
    print(
        f"code: code_wrap=OVERFLOW, {panel.total_columns} columns, "
        f"x_offset={panel.x_offset}, {MARKER} visible"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="motui code example")
    parser.add_argument("--headless", action="store_true")
    parser.parse_args(argv)
    return headless()


if __name__ == "__main__":
    raise SystemExit(main())
