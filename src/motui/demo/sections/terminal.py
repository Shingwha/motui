"""The terminal section: keys, mouse and paint, dissected.

One frame reports the cell budget, the sync pair, the color and marker
ladders and a live event feed. Every number is a constant, not a probe."""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.glyphs import GLYPHS, seat
from ...kernel.layout import Constraints
from ...kernel.style import FG_CODES, Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Canvas, Panel, Row
from ..common import FixedHeight, LinesView
from ..scene import Scene

__all__ = ["TerminalScene"]

#: Single-row clip for the composed rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: The shell's animation tick rate (``demo.TICK_HZ``); the frame budget
#: below follows from it, so the two stay one story.
_FRAME_HZ = 60

#: The per-frame time budget at :data:`_FRAME_HZ`, one decimal
#: (1000 ms / 60).  A constant, not a measurement.
_BUDGET_MS = "16.7"

#: The painter's synchronized-update pair (DECSET 2026), as literal text.
_SYNC_OPEN = "\\x1b[?2026h"
_SYNC_CLOSE = "\\x1b[?2026l"

#: The mouse-report triple a live session enables -- the demo boots
#: ``MouseMode.MOVE``, whose tracking pair is 1000 + 1003 + SGR 1006.
_MOUSE_ENABLE = "\\x1b[?1000h \\x1b[?1003h \\x1b[?1006h"

#: How many recent click reports the feed keeps (newest last).
_FEED_DEPTH = 4

#: The staircase every marker plots: eight points in value space, so the
#: three resolutions draw the same shape at three sub-cell densities.
_STAIR = tuple((x, (x * 5) % 7) for x in range(8))

#: The sixteen base colors in :data:`FG_CODES` order (xterm index 0..15).
_BASE16 = tuple(FG_CODES)

#: The 256 bar: the 24-step gray ramp (the ``8 + 10 * step`` ladder the
#: kernel's quantizer searches), then the blue channel's six cube levels.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
_BAR_256 = tuple(
    f"#{value:02x}{value:02x}{value:02x}"
    for value in (8 + 10 * step for step in range(24))
) + tuple(f"#0000{value:02x}" for value in _CUBE_LEVELS)

#: The truecolor bar's endpoints: a raised dark surface into the accent hue.
_TRUE_FROM = (22, 29, 39)
_TRUE_TO = (83, 200, 240)
_TRUE_STEPS = 32


def _gradient() -> tuple[str, ...]:
    """The 24-bit sweep, one ``#rrggbb`` per step, integer interpolation."""
    span = _TRUE_STEPS - 1
    return [
        "#{:02x}{:02x}{:02x}".format(
            *(a + (b - a) * step // span for a, b in zip(
                _TRUE_FROM, _TRUE_TO, strict=True
            ))
        )
        for step in range(_TRUE_STEPS)
    ]


class TerminalScene(Scene):
    """The terminal report: a 2x2 panel grid whose only mutable state is the
    click feed; ``enter`` clears it. Everything else is a pure function of
    the constraints."""

    name = "terminal"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._feed: list[str] = []
        self._cursor = Pos(x=0, y=0)
        self._width = 100
        self._height = 30

        # -- the two static panels -----------------------------------
        self._bars = LinesView(theme)
        self._bars.lines = self._bar_lines()
        self._ladder = LinesView(theme)
        self._ladder.lines = self._ladder_lines()
        # -- the two panels that re-answer every frame ----------------
        self._session = LinesView(theme)
        self._feed_view = LinesView(theme)
        self._session_panel = Panel(self._session, title="session", theme=theme)
        self._feed_panel = Panel(self._feed_view, title="events \u00b7 live", theme=theme)
        self._bars_panel = Panel(
            self._bars, title="color by capability", theme=theme
        )
        self._ladder_panel = Panel(self._ladder, title="marker ladder", theme=theme)
        self._top = Row(
            [FixedHeight(self._session_panel), FixedHeight(self._feed_panel)],
            widths=[52, None],
            gap=1,
        )
        self._bottom = Row(
            [FixedHeight(self._bars_panel), FixedHeight(self._ladder_panel)],
            widths=[52, None],
            gap=1,
        )
        self._refresh_feed()

    def enter(self) -> None:
        super().enter()
        self._feed.clear()
        self._refresh_feed()

    @property
    def feed(self) -> tuple[str, ...]:
        return tuple(self._feed)

    # -- the static panels -------------------------------------------------------

    def _bar_line(self, label: str, colors: tuple[str, ...]) -> Line:
        """One swatch bar: a mode label, then one block per palette entry."""
        swatches = tuple(
            Segment(GLYPHS.bar_full, Style(fg=color)) for color in colors
        )
        return Line((Segment(f"{label:<5}", self.theme.text.muted), *swatches))

    def _bar_lines(self) -> list[Line]:
        """The capability ladder: what the 16 / 256 / truecolor modes name."""
        return [
            self._bar_line("16", _BASE16),
            self._bar_line("256", _BAR_256),
            self._bar_line("rgb", _gradient()),
            Line(
                (
                    Segment(
                        "16 base \u00b7 24 gray + 6 cube \u00b7 24-bit sweep",
                        self.theme.text.faint,
                    ),
                )
            ),
        ]

    def _ladder_row(self, name: str) -> Line:
        """One marker step: the staircase at ``name``'s resolution, then its mark."""
        canvas = Canvas(
            width=10, height=1, plot_marker=name, theme=self.theme
        )
        canvas.plot(_STAIR, style=self.theme.content.accent)
        return (
            Line((Segment(f"{name:<8}", self.theme.text.muted),))
            + canvas.surface()[0]
            + Line(
                (
                    Segment(" "),
                    Segment(seat(GLYPHS.notice_success), self.theme.status.success),
                    Segment("ok", self.theme.text.faint),
                )
            )
        )

    def _ladder_lines(self) -> list[Line]:
        """The marker ladder: cell, half and braille pass; octant is unprobed."""
        return [
            self._ladder_row("cell"),
            self._ladder_row("half"),
            self._ladder_row("braille"),
            Line(
                (
                    Segment("octant  ", self.theme.text.muted),
                    Segment("\u2014", self.theme.text.faint),
                    Segment(
                        "  not probed (core: half/braille)",
                        self.theme.text.faint,
                    ),
                )
            ),
        ]

    # -- the live panels ---------------------------------------------------------

    def _fact(self, label: str, value: str) -> Line:
        """One label/value row of the session panel."""
        return Line(
            (
                Segment(f"{label:<8}", self.theme.text.muted),
                Segment(value, self.theme.text.base),
            )
        )

    def _refresh_session(self, width: int, height: int) -> None:
        self._width, self._height = width, height
        self._session.lines = [
            self._fact("size", f"{width} x {height} cells"),
            self._fact("probe", f"({self._cursor.x}, {self._cursor.y}) · arrows move"),
            self._fact("sync", f"{_SYNC_OPEN} {_SYNC_CLOSE}"),
            self._fact("route", "key → event → widget → diff → cells"),
            self._fact("budget", f"{_BUDGET_MS} ms/frame · unchanged rows write zero"),
        ]

    def _refresh_feed(self) -> None:
        lines = [
            Line(
                (
                    Segment("enable ", self.theme.text.muted),
                    Segment(_MOUSE_ENABLE, self.theme.text.faint),
                )
            )
        ]
        if self._feed:
            lines.extend(
                Line((Segment(report, self.theme.text.base),))
                for report in self._feed
            )
            lines.append(
                Line(
                    (
                        Segment(
                            "click again: the next report lands here",
                            self.theme.text.faint,
                        ),
                    )
                )
            )
        else:
            lines.extend(
                Line((Segment(text, self.theme.text.faint),))
                for text in (
                    "no reports yet (headless)",
                    "decode SGR-1006 / X10 / urxvt-1015",
                    "a live click lands here with its cell",
                )
            )
        self._feed_view.lines = lines

    # -- rendering ---------------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        """The heading, the 2x2 panel grid and the hint, clipped to the pane."""
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        self._refresh_session(width, height)

        left = min(52, max(30, width * 52 // 100))
        self._top.widths = [left, None]
        self._bottom.widths = [left, None]
        body = max(6, height - 2)  # the heading and the hint own one row each
        top_h = max(3, (body - 1) // 2)
        bottom_h = max(3, body - 1 - top_h)
        top_boxes, bottom_boxes = self._top.children, self._bottom.children
        for box in top_boxes:
            box.height = top_h
        for box in bottom_boxes:
            box.height = bottom_h

        top_rows = list(self._top.render(Constraints(width=width)))[:top_h]
        top_rows.extend(Line() for _ in range(top_h - len(top_rows)))
        bottom_rows = list(self._bottom.render(Constraints(width=width)))
        del bottom_rows[bottom_h:]
        bottom_rows.extend(Line() for _ in range(bottom_h - len(bottom_rows)))
        rows: list[Line] = [
            self._heading(),
            *top_rows,
            Line(),
            *bottom_rows,
            self._hint(),
        ]
        return Surface.of(
            [row.clip(_CLIP, width) for row in rows[:height]], width
        )

    def _heading(self) -> Line:
        """The one-row title: the section's name and its one-line pitch."""
        return Line(
            (
                Segment("X-RAY / INPUT TO CELLS", self.theme.content.accent),
                Segment(
                    " \u00b7 follow every event through the paint pipeline",
                    self.theme.text.faint,
                ),
            )
        )

    def _hint(self) -> Line:
        """The one-row key hint bar."""
        return Line.from_text(
            "arrows move \u00b7 enter/space emit \u00b7 click reports \u00b7 esc lab",
            self.theme.text.faint,
        )

    # -- behaviour ---------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "escape":
            return "menu"
        if key == "q":
            return "quit"
        if key in ("left", "right", "up", "down"):
            dx = -1 if key == "left" else 1 if key == "right" else 0
            dy = -1 if key == "up" else 1 if key == "down" else 0
            self._cursor = Pos(
                x=max(0, min(self._width - 1, self._cursor.x + dx)),
                y=max(0, min(self._height - 1, self._cursor.y + dy)),
            )
            self._refresh_session(self._width, self._height)
        elif key in ("enter", "space"):
            self._emit(f"{key} ({self._cursor.x}, {self._cursor.y})")
        return None

    def on_click(self, pos: Pos) -> str | None:
        self._cursor = pos
        self._emit(f"click ({pos.x}, {pos.y})")
        return None

    def _emit(self, report: str) -> None:
        self._feed.append(report)
        del self._feed[:-_FEED_DEPTH]
        self._refresh_feed()
        self._refresh_session(self._width, self._height)
