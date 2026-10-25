"""A dashboard: a braille Sparkline in the Fill slot, ticked by ``App.every``.

    uv run python examples/dashboard.py --headless    # replay N frames, summarize
    uv run python examples/dashboard.py               # live until quit

The example shows the 2.0 assembly surface in one file: ``App.add`` with
``Sizing.FILL`` for the plot, a periodic callback created by ``App.every``,
and ``Runtime.advance`` to replay deterministic frames without sleeping.
"""

from __future__ import annotations

import argparse
import math

from motui import App
from motui.kernel.document import Sizing
from motui.terminal import HeadlessScreen
from motui.widgets import Sparkline, Text

WIDTH, HEIGHT = 80, 20
POINTS = 64
FRAME_RATE = 20
DEFAULT_FRAMES = 40


class Feed:
    """A rolling window of samples; :meth:`sample` advances one point."""

    def __init__(self) -> None:
        self.values = [0.5] * POINTS
        self.frame = 0

    def sample(self) -> float:
        """Append one sine sample and answer it."""
        self.frame += 1
        value = 0.5 + 0.45 * math.sin(self.frame / 6.0)
        self.values = self.values[1:] + [value]
        return value


def build(screen: HeadlessScreen | None = None) -> tuple[App, Feed, Sparkline, Text]:
    """Assemble the App: a header row plus the sparkline filling the rest."""
    app = App(screen=screen, auto=False)
    feed = Feed()
    header = Text("motui dashboard | braille sparkline")
    spark = Sparkline(feed.values, marker="braille")
    app.add(header)
    app.add(spark, sizing=Sizing.FILL)

    def tick() -> None:
        value = feed.sample()
        spark.values = list(feed.values)
        header.text = f"motui dashboard | last={value:.3f}"
        app.invalidate()

    app.every(1.0 / FRAME_RATE, tick)
    return app, feed, spark, header


def headless(frames: int) -> int:
    """Replay ``frames`` deterministic frames and print one summary line."""
    app, feed, spark, _header = build(HeadlessScreen(WIDTH, HEIGHT))
    for _ in range(frames):
        app.runtime.advance(1.0 / FRAME_RATE)
        app.paint_now()
    painted = sum(1 for row in app.runtime.rows if row.text.strip())
    print(
        f"dashboard: {frames} frames at {FRAME_RATE} fps, "
        f"{len(spark.values)} points, last={feed.values[-1]:.3f}, "
        f"painted_rows={painted}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="motui dashboard example")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    args = parser.parse_args(argv)
    if args.headless:
        return headless(max(1, args.frames))
    app, _feed, _spark, _header = build()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
