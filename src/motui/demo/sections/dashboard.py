"""The dashboard section: a live operations page streaming phase-derived data."""

from __future__ import annotations

import math

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import (
    Column,
    Divider,
    Panel,
    ProgressBar,
    Row,
    Sparkline,
    Table,
    Text,
)

__all__ = ["DashboardScene"]

#: Single-row clip for the composed hint rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: The dashboard's rolling window, log depth and simulated frame rate.
_DASHBOARD_POINTS = 48
_DASHBOARD_LOG = 4
_DASHBOARD_FPS = 30

#: A phase jump replays at most this many dashboard samples.
_MAX_SYNC = 4096


class DashboardScene:
    """A live operations page built from real widgets, never a clock read.

    The scene keeps a rolling window of 48 samples and pushes one point per
    tick, so a replay at phase N paints the same values on every machine.
    Four panels share a 2x2 grid: a braille ``Sparkline``, two
    ``ProgressBar`` gauges, a metric ``Table`` and a wrapped event log.  The
    grid is rebuilt from ``c.width``/``c.max_height`` every frame, so 80x24
    and 100x30 both reflow without clipping; the header's clock is
    ``phase // 30`` seconds, not the wall clock.
    """

    name = "dashboard"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self.samples: list[float] = []
        self.log: list[str] = []
        self.cpu = 0.0
        self.mem = 0.0
        self.rps = 0
        self.p95 = 0
        self.errors = 0
        self._seed()

        self.spark = Sparkline(
            list(self.samples), marker="braille", style=theme.status.success
        )
        self.cpu_bar = ProgressBar(self.cpu, label="cpu", theme=theme)
        self.mem_bar = ProgressBar(self.mem, label="mem", theme=theme)
        self.table = Table(
            ["metric", "value"],
            self._metric_rows(0),
            aligns=["left", "right"],
            theme=theme,
        )
        self._summary = Text("", style=theme.text.muted, theme=theme)
        self._events = Text("", style=theme.text.faint, theme=theme)
        self._spark_box = _FixedHeight(self.spark, 0)
        self._pressure_box = _FixedHeight(
            Column([self.cpu_bar, self.mem_bar, self._summary], gap=0), 0
        )
        self._metrics_box = _FixedHeight(self.table, 0)
        self._events_box = _FixedHeight(self._events, 0)
        self._spark_panel = Panel(
            self._spark_box, title="throughput", theme=theme
        )
        self._pressure_panel = Panel(
            self._pressure_box, title="pressure", theme=theme
        )
        self._metrics_panel = Panel(self._metrics_box, title="metrics", theme=theme)
        self._events_panel = Panel(self._events_box, title="events", theme=theme)
        self._refresh()

    # -- data --------------------------------------------------------------

    def _seed(self) -> None:
        """Fill the rolling window with the deterministic pre-history."""
        self.samples = [
            _sample(step) for step in range(-_DASHBOARD_POINTS + 1, 1)
        ]
        self.log = []
        for step in range(-_DASHBOARD_POINTS, 1, 6):
            self.log.append(_log_line(step))
        del self.log[:-_DASHBOARD_LOG]
        self._set_gauges(0)

    def _set_gauges(self, step: int) -> None:
        """Derive the gauges and counters from the tick number alone."""
        self.cpu = _clamp(0.42 + 0.30 * math.sin(step / 9.0) + 0.06 * math.cos(step / 2.5))
        self.mem = _clamp(0.55 + 0.18 * math.sin(step / 17.0 + 1.2))
        self.rps = 820 + round(140 * math.sin(step / 5.0) + 35 * math.cos(step / 1.9))
        self.p95 = 38 + (step * 7) % 23
        self.errors = (step * 3) % 4

    def _metric_rows(self, step: int) -> list[list[str]]:
        """The metrics table as it reads at ``step`` (uptime rides the summary)."""
        return [
            ["requests", f"{self.rps}/s"],
            ["p95", f"{self.p95} ms"],
            ["errors", str(self.errors)],
        ]

    def _push(self, step: int) -> None:
        """Append one sample and move every gauge with it."""
        self.samples = [*self.samples[1:], _sample(step)]
        self._set_gauges(step)
        if step % 6 == 0:
            self.log.append(_log_line(step))
            del self.log[:-_DASHBOARD_LOG]
        self._refresh()

    def _refresh(self) -> None:
        """Copy the model onto the real widgets (each assignment touches)."""
        self.spark.values = list(self.samples)
        self.cpu_bar.fraction = self.cpu
        self.mem_bar.fraction = self.mem
        self.table.rows = self._metric_rows(self._phase)
        self._summary.text = (
            f"{self.rps}/s \u00b7 p95 {self.p95} ms \u00b7 "
            f"{self.errors} errors \u00b7 up {max(0, self._phase) // _DASHBOARD_FPS}s"
        )
        self._events.text = "\n".join(self.log)

    def _sync(self, phase: int) -> None:
        """Replay the missing ticks; a backwards jump re-seeds the window."""
        if phase < self._phase:
            self._phase = 0
            self._seed()
            self._refresh()
        steps = min(max(0, phase - self._phase), _MAX_SYNC)
        for step in range(self._phase + 1, self._phase + steps + 1):
            self._push(step)
        self._phase = phase

    # -- protocol ----------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        self._sync(phase)
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        return "menu" if event.key in ("escape", "q") else None

    def on_click(self, pos: Pos) -> str | None:
        return None

    def render(self, c: Constraints, phase: int) -> Surface:
        """Compose the header, the 2x2 panel grid and the hint for this size."""
        height = c.max_height if c.max_height is not None else 24
        self._sync(phase)
        width = c.width

        inner = max(2, height - 4)
        top_h = max(3, inner // 2)
        bottom_h = max(3, inner - top_h)
        left_w = max(1, (width - 1) // 2)
        right_w = max(1, width - 1 - left_w)
        self._spark_box.height = max(0, top_h - 2)
        self._pressure_box.height = max(0, top_h - 2)
        self._metrics_box.height = max(0, bottom_h - 2)
        self._events_box.height = max(0, bottom_h - 2)
        top = Row(
            [self._spark_panel, self._pressure_panel],
            widths=[left_w, right_w],
            gap=1,
        ).render(Constraints(width=width))
        bottom = Row(
            [self._metrics_panel, self._events_panel],
            widths=[left_w, right_w],
            gap=1,
        ).render(Constraints(width=width))

        divider = Divider(label="live", theme=self.theme).render(
            Constraints(width=width)
        )
        hint = Line.from_text(
            "esc menu \u00b7 samples stream at "
            f"{_DASHBOARD_FPS} Hz \u00b7 clock from phase",
            self.theme.text.faint,
        ).clip(_CLIP, width)
        rows = [
            self._header(width),
            divider[0] if len(divider) else Line(),
            *list(top)[:top_h],
            Line(),
            *list(bottom)[:bottom_h],
            hint,
        ]
        rows = rows[:height]
        if len(rows) < height:
            rows.extend(Line() for _ in range(height - len(rows)))
        return Surface.of(rows, width)

    def _header(self, width: int) -> Line:
        """Title, derived clock and tick count on one row."""
        left = "motui dashboard"
        right = f"{_clock(self._phase)}  tick {self._phase:04d}"
        gap = max(1, width - len(left) - len(right) - 2)
        line = Line(
            (
                Segment(" "),
                Segment(left, self.theme.content.accent),
                Segment(" " * gap),
                Segment(right, self.theme.text.faint),
                Segment(" "),
            )
        )
        return line.clip(_CLIP, width)

    def __repr__(self) -> str:
        return f"DashboardScene(phase={self._phase}, samples={len(self.samples)})"


class _FixedHeight:
    """Render a child under a row budget and pad it to exactly that height.

    The dashboard's panels need equal heights in a ``Row``; ``Panel`` hands
    its child only a width, so this small adapter supplies the row budget a
    ``Sparkline`` or a ``Table`` needs and fills the remainder with blanks.
    """

    def __init__(self, child, height: int = 0) -> None:
        self.child = child
        self.height = height

    def render(self, c: Constraints) -> Surface:
        budget = max(0, self.height)
        rows = list(
            self.child.render(Constraints(width=c.width, max_height=budget))
        )
        rows = rows[:budget]
        rows.extend(Line() for _ in range(budget - len(rows)))
        return Surface.of(rows, c.width)


def _clamp(value: float) -> float:
    """Clamp a gauge into ``[0, 1]``."""
    return min(1.0, max(0.0, value))


def _sample(step: int) -> float:
    """One deterministic sample: two sines and a cosine, no clock, no random."""
    value = (
        0.5
        + 0.32 * math.sin(step / 6.0)
        + 0.12 * math.sin(step / 2.7)
        + 0.05 * math.cos(step / 1.7)
    )
    return _clamp(value)


def _log_line(step: int) -> str:
    """One event-log line for tick ``step``."""
    return f"t{step:05d}  sample {_sample(step):.2f}"


def _clock(phase: int) -> str:
    """``mm:ss.t`` derived from the phase at 30 ticks a second."""
    ticks = max(0, phase)
    seconds, rest = divmod(ticks, _DASHBOARD_FPS)
    minutes, seconds = divmod(seconds, 60)
    tenths = rest * 10 // _DASHBOARD_FPS
    return f"{minutes:02d}:{seconds:02d}.{tenths}"
