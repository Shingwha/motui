"""A 200-column table in a horizontal ScrollPanel.

    uv run python examples/wide_table.py --headless   # scroll to the last column
    uv run python examples/wide_table.py              # live; left/right scroll
"""

from __future__ import annotations

import argparse

from motui import App, ScrollPanel, Table, headless_tui
from motui.kernel.text import WrapMode

COLUMNS = 200
VIEWPORT = 80


def build() -> ScrollPanel:
    """The panel: a 200-column OVERFLOW table, five rows tall plus its bar."""
    headers = [f"c{index:03d}" for index in range(COLUMNS)]
    values = [f"v{index:03d}" for index in range(COLUMNS)]
    table = Table(headers, [values], cell_wrap=WrapMode.OVERFLOW)
    return ScrollPanel(table, axis="x", height=6, bar=True)


def headless() -> int:
    """Render at 80 columns, scroll to the right edge, and verify the marker."""
    panel = build()
    tui = headless_tui(VIEWPORT, 8)
    tui.add(panel)
    tui.paint()
    panel.scroll_x_to_end()
    tui.paint()
    text = "\n".join(row.text for row in tui.rows)
    if "c199" not in text or "v199" not in text:
        print("wide_table: the rightmost column is not reachable")
        return 1
    print(
        f"wide_table: {COLUMNS} columns, x_offset={panel.x_offset}, "
        "rightmost c199/v199 visible"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="motui wide table example")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)
    if args.headless:
        return headless()
    panel = build()
    app = App()
    app.add(panel)
    app.bind("left", lambda: panel.scroll_x(-4))
    app.bind("right", lambda: panel.scroll_x(4))
    app.bind("home", lambda: panel.scroll_to_x(0))
    app.bind("end", panel.scroll_x_to_end)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
