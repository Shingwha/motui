"""The showcase's scene machine: one widget, five matching scenes.

``Showcase`` is the widget ``python -m motui`` fills its pane with.  It
owns the current scene's name and one integer **phase** -- the animation
clock -- and delegates rendering and input to the scene object.  The
runner ticks it about thirty times a second; a scene that wants to leave
answers ``Showcase`` with the next scene's name (or ``"quit"``).

The scene protocol is deliberately narrow: ``render``, ``tick``, ``on_key``
and ``on_click``.  Scenes are plain objects, not widgets: the showcase is
the one focus target and hands the scene its own coordinates, which keeps
the App's focus ring out of the demo's business.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Protocol

from ..kernel.cell import Line, Segment, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets import (
    Column,
    Divider,
    Input,
    Markdown,
    Panel,
    ProgressBar,
    Row,
    Slider,
    Sparkline,
    Table,
    Text,
    Tree,
    TreeNode,
)
from ..widgets.base import Widget
from ..widgets.choice import Option, Select
from .art import big_text, center, gradient_styles
from .snake import SnakeScene

__all__ = [
    "SCENES",
    "DashboardScene",
    "GalleryScene",
    "MenuScene",
    "Scene",
    "Showcase",
    "SnakeScene",
    "SplashScene",
]

#: Single-row clip for the composed menu rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: The scenes in tour order: splash, menu, snake, dashboard, gallery.
SCENES: tuple[str, ...] = ("splash", "menu", "snake", "dashboard", "gallery")

#: The dashboard's rolling window, log depth and simulated frame rate.
_DASHBOARD_POINTS = 48
_DASHBOARD_LOG = 4
_DASHBOARD_FPS = 30

#: A phase jump replays at most this many dashboard samples.
_MAX_SYNC = 4096

#: The phase (animation tick) a scene starts on when it is entered.
START_PHASE = 0

#: How long one splash style holds: four seconds at 30 Hz.
SPLASH_ROTATE_TICKS = 120

#: How often the logo's fill glyph morphs inside a style.
SPLASH_GLYPH_TICKS = 18

#: The style packs the splash rotates through.  Each changes both glyphs and
#: colors; ``starfield`` also draws a field of stars around the word.
SPLASH_STYLES: tuple[str, ...] = ("neon", "plasma", "retro", "starfield")

#: The fill glyphs each pack morphs between (all single-width).
SPLASH_GLYPHS: dict[str, tuple[str, ...]] = {
    "neon": ("\u2588", "\u2593", "\u25a0", "\u2588"),
    "plasma": ("\u2588", "\u2593", "\u2592", "\u25a0"),
    "retro": ("\u2588", "\u2593"),
    "starfield": ("\u25a0", "\u25a3", "\u2726", "\u2588"),
}

#: The logo's ink: the accent fades into the inline-code lavender.
LOGO_START = "#53c8f0"
LOGO_END = "#c4b5fd"


class Scene(Protocol):
    """One showcase scene: render a frame, advance, route input.

    ``render`` answers the rows for the whole pane, filled by the
    :class:`Showcase`; ``tick`` runs once per animation tick and may name
    the next scene; ``on_key``/``on_click`` may do the same or answer
    ``None``.  A transition is one of :data:`SCENES` or ``"quit"``.
    """

    name: str

    def render(self, c: Constraints, phase: int) -> Surface: ...

    def tick(self, phase: int) -> str | None: ...

    def on_key(self, event: KeyEvent) -> str | None: ...

    def on_click(self, pos: Pos) -> str | None: ...


def _hsl(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
    """One HSL color as an RGB triple (the plasma/starfield palettes)."""
    h = (hue % 360.0) / 60.0
    chroma = (1 - abs(2 * lightness - 1)) * saturation
    second = chroma * (1 - abs(h % 2 - 1))
    base = lightness - chroma / 2
    if h < 1:
        rgb = (chroma, second, 0.0)
    elif h < 2:
        rgb = (second, chroma, 0.0)
    elif h < 3:
        rgb = (0.0, chroma, second)
    elif h < 4:
        rgb = (0.0, second, chroma)
    elif h < 5:
        rgb = (second, 0.0, chroma)
    else:
        rgb = (chroma, 0.0, second)
    return tuple(round((value + base) * 255) for value in rgb)


class SplashScene:
    """The opening: a 5x7 logo in one of four animated style packs.

    The splash never times out.  It rotates through :data:`SPLASH_STYLES`
    every :data:`SPLASH_ROTATE_TICKS` animation ticks (about four seconds),
    reshuffling the order whenever it is entered, and only a key or a click
    leaves for the menu.  Each pack changes both the fill glyph and the
    colors: ``neon`` is the cyan-to-lavender ramp with a white sweep,
    ``plasma`` walks the hue wheel across the word, ``retro`` is a green or
    amber CRT with dim scanlines, and ``starfield`` colors cells from a
    drifting star palette with occasional red/cyan glitch bands and a field
    of stars around the logo.

    ``seed`` pins the shuffle for a headless snapshot; ``None`` seeds from
    the system for a live run, so every launch starts on a different pack.
    """

    name = "splash"

    def __init__(self, theme: Theme, *, seed: int | None = 0) -> None:
        self.theme = theme
        self._logo_width = 5 * len("MOTUI") + 4
        self._neon_styles = gradient_styles(LOGO_START, LOGO_END, self._logo_width)
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._order = list(SPLASH_STYLES)
        self.restart()

    def restart(self) -> None:
        """Reshuffle the style order; the next visit starts somewhere new."""
        self._rng.shuffle(self._order)

    def style_name(self, phase: int) -> str:
        """The pack active at ``phase`` (exposed for tests and the hint row)."""
        return self._order[(phase // SPLASH_ROTATE_TICKS) % len(self._order)]

    def _glyph(self, pack: str, phase: int) -> str:
        glyphs = SPLASH_GLYPHS[pack]
        return glyphs[(phase // SPLASH_GLYPH_TICKS) % len(glyphs)]

    def _accent(self, pack: str, phase: int) -> Style:
        """The subtitle/indicator color the active pack uses."""
        if pack == "neon":
            return Style(fg=self._neon_styles[self._logo_width // 2].fg, bold=True)
        if pack == "plasma":
            return Style(fg=_hsl(phase * 4, 0.7, 0.65), bold=True)
        if pack == "retro":
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            return Style(fg=(255, 176, 0) if amber else (51, 255, 153), bold=True)
        return Style(fg=(220, 230, 255), bold=True)

    def _style_at(self, pack: str, phase: int, x: int, y: int) -> Style:
        """One logo cell's style for the active pack."""
        if pack == "neon":
            base = self._neon_styles[x % len(self._neon_styles)]
            sweep = (phase % (self._logo_width + 12)) - 6
            if x == sweep:
                return Style(fg=(255, 255, 255), bold=True)
            return Style(fg=base.fg, bold=(phase // 8 + x // 4) % 2 == 0)
        if pack == "plasma":
            hue = (x * 11 + phase * 6) % 360
            light = 0.55 + 0.12 * math.sin((x + phase / 7) / 3)
            return Style(fg=_hsl(hue, 0.72, light), bold=(x + phase // 9) % 4 == 0)
        if pack == "retro":
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            rgb = (255, 176, 0) if amber else (51, 255, 153)
            if y % 2:
                rgb = tuple(channel // 2 for channel in rgb)
            sweep = (phase % (self._logo_width + 16)) - 8
            if x == sweep:
                return Style(fg=(255, 255, 255), bold=True)
            return Style(fg=rgb, bold=not amber and x % 3 == 0)
        # starfield
        hue = (x * 47 + y * 29 + (phase // 5) * 31) % 360
        glitch = (phase // 37) % 4 == 0 and (x * 7 + y * 13 + phase) % 19 < 2
        if glitch:
            hue = 0 if (x + y) % 2 == 0 else 180
        return Style(
            fg=_hsl(hue, 0.55, 0.6),
            bold=glitch or (x + y + phase // 8) % 7 == 0,
        )

    def _pulse(self, pack: str, phase: int) -> Line:
        """Five dots with one lit: the quiet breathing mark under the logo."""
        lit = (phase // 4) % 5
        accent = self._accent(pack, phase)
        segments: list[Segment] = []
        for index in range(5):
            if index:
                segments.append(Segment("   "))
            segments.append(
                Segment(
                    "\u25cf" if index == lit else "\u00b7",
                    accent if index == lit else self.theme.text.faint,
                )
            )
        return Line(segments)

    def _stars(self, width: int, phase: int) -> list[Line]:
        """Two rows of deterministic stars: the starfield pack's air."""
        rows: list[Line] = []
        for row in range(2):
            segments: list[Segment] = []
            for x in range(max(0, width)):
                seed = x * 37 + row * 91 + (phase // 6) * 17
                if seed % 19 == 0:
                    segments.append(
                        Segment("\u2726", Style(fg=_hsl((seed * 7) % 360, 0.45, 0.62)))
                    )
                elif seed % 11 == 0:
                    segments.append(Segment("\u00b7", self.theme.text.faint))
                else:
                    segments.append(Segment(" "))
            rows.append(Line(segments))
        return rows

    def render(self, c: Constraints, phase: int) -> Surface:
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        pack = self.style_name(phase)
        logo = center(
            width,
            big_text(
                "MOTUI",
                pixel=self._glyph(pack, phase),
                style_at=lambda x, y: self._style_at(pack, phase, x, y),
            ),
        )
        subtitle = center(
            width,
            [Line.from_text("a terminal UI kernel \u00b7 2.0.0", self.theme.text.muted)],
        )
        dots = center(width, [self._pulse(pack, phase)])
        hint = center(
            width,
            [Line.from_text(f"press any key  \u00b7  {pack}", self.theme.text.faint)],
        )
        content = [
            *logo,
            Line(),
            *subtitle,
            Line(),
            *dots,
            Line(),
            *hint,
        ]
        if pack == "starfield":
            content = [
                *self._stars(width, phase),
                Line(),
                *content,
                Line(),
                *self._stars(width, phase + 7),
            ]
        top = max(0, (height - len(content)) // 2)
        rows = [Line() for _ in range(top)] + content
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        """The splash never times out; only a key or a click leaves it."""
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        return "menu"

    def on_click(self, pos: Pos) -> str | None:
        return "menu"


class MenuScene:
    """The hub: a centred panel of four destinations.

    ``Snake`` and ``Dashboard`` are playable/live in this build alongside
    ``Gallery``; ``Quit`` leaves.  Up/down (or j/k) move the cursor, enter
    opens the choice, a click selects a row, ``esc`` returns to the splash
    and ``q`` quits.
    """

    name = "menu"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._top = 0
        self._left = 0
        self.options = [
            Option("Snake", "snake", "a snake, a bite, a tail"),
            Option("Dashboard", "dashboard", "live sparklines"),
            Option("Gallery", "gallery", "real components, one page"),
            Option("Quit", "quit", "leave the showcase"),
        ]
        self.list = Select(self.options, max_rows=None, theme=theme)
        self.list.focused = True
        self._title = Text("motui", style=theme.content.accent, theme=theme)
        self._version = Text(
            "2.0.0 \u00b7 Ink & Signal", style=theme.text.faint, theme=theme
        )
        self._hint = Text(
            "\u2191/\u2193 choose \u00b7 enter open \u00b7 esc back \u00b7 q quit",
            style=theme.text.faint,
            theme=theme,
        )
        heading = Column([self._title, self._version], gap=0)
        body = Column([heading, self.list, self._hint], gap=1)
        self.panel = Panel(body, title="showcase", theme=theme)

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        panel_width = min(48, max(24, width - 4))
        content = list(self.panel.render(Constraints(width=panel_width)))
        height = c.max_height if c.max_height is not None else len(content) + 4
        top = max(0, (height - len(content)) // 2)
        left = max(0, (width - panel_width) // 2)
        self._top = top
        self._left = left
        rows = [Line() for _ in range(top)]
        pad = Line((Segment(" " * left),)) if left else Line()
        for row in content:
            rows.append((pad + row).clip(_CLIP, width))
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key in ("up", "k"):
            self.list.move(-1)
        elif key in ("down", "j"):
            self.list.move(1)
        elif key in ("enter", "space"):
            return self._activate()
        elif key == "escape":
            return "splash"
        elif key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        if pos.y < self._top or pos.x < self._left:
            return None
        content = getattr(self.panel, "child_at", lambda row, col: None)(
            pos.y - self._top, pos.x - self._left
        )
        if content is None:
            return None
        body, row, col = content
        target = getattr(body, "child_at", lambda r, c: None)(row, col)
        if target is None:
            return None
        widget, inner_row, inner_col = target
        if widget is self.list:
            self.list.on_click(Pos(x=inner_col, y=inner_row))
        return None

    def _activate(self) -> str | None:
        """Open the chosen destination (``None`` only for an empty menu)."""
        option = self.list.options[self.list.index]
        return str(option.value)


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


class GalleryScene:
    """A live page of real 2.0 components, not pictures of them.

    Three panes share the width: a ``Tree`` (fold/unfold and a cursor), a
    ``Table`` (a row cursor) and a controls column holding a short
    ``Markdown`` note, an animated ``ProgressBar``, a ``Slider`` and an
    ``Input``.  ``tab`` cycles the focus between the four interactive
    widgets; the arrows and typing go to the focused one.  ``esc`` returns
    to the menu, and the layout is composed with ``Row``/``Column`` and
    real constraints, so 80x24 and 100x30 both reflow without a fixed
    width assumption.
    """

    name = "gallery"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._focus = 0
        self._top = 0
        self.tree = Tree(
            [
                TreeNode(
                    "app",
                    [
                        TreeNode("shell"),
                        TreeNode("gallery"),
                        TreeNode("inspector"),
                    ],
                    expanded=True,
                ),
                TreeNode("workspace", [TreeNode("runtime")], expanded=True),
            ],
            theme=theme,
        )
        self.table = Table(
            ["widget", "role"],
            [
                ["Tree", "fold"],
                ["Table", "grid"],
                ["Slider", "value"],
                ["Input", "type"],
            ],
            theme=theme,
        )
        self.table.index = 1
        self.markdown = Markdown(
            "**2.0 in one page**\n\n"
            "Every block here is a real widget:\n\n"
            "- `Tree` folds\n"
            "- `Table` selects\n"
            "- `Slider` steps\n"
            "- `Input` types\n",
            theme=theme,
        )
        self.progress = ProgressBar(0.6, label="render", theme=theme)
        self.slider = Slider(7, maximum=10, theme=theme)
        self.input = Input("type here", placeholder="type\u2026", theme=theme)
        self._targets = [self.tree, self.table, self.slider, self.input]
        self._set_focus(0)
        self._title = Text("Gallery", style=theme.content.accent, theme=theme)
        self._divider = Divider(label="real components", theme=theme)
        self._hint = Text(
            "tab focus \u00b7 \u2191\u2193 rows \u00b7 \u2190\u2192 value \u00b7 "
            "esc menu",
            style=theme.text.faint,
            theme=theme,
        )
        controls = Column(
            [self.markdown, self.progress, self.slider, self.input], gap=0
        )
        body = Row(
            [
                Panel(self.tree, title="tree", theme=theme),
                Panel(self.table, title="table", theme=theme),
                Panel(controls, title="controls", theme=theme),
            ],
            gap=1,
        )
        self._root = Column(
            [self._title, self._divider, body, self._hint], gap=1
        )

    def _set_focus(self, index: int) -> None:
        """Place the demo's own focus on one interactive widget."""
        self._focus = index % len(self._targets)
        for position, target in enumerate(self._targets):
            target.focused = position == self._focus

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        rows = list(self._root.render(Constraints(width=width)))
        top = max(0, (height - len(rows)) // 2)
        self._top = top
        rows = [Line() for _ in range(top)] + rows
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        self.progress.fraction = 0.55 + 0.4 * math.sin(phase / 7)
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "escape":
            return "menu"
        if key in ("tab", "s-tab", "backtab"):
            step = -1 if key in ("s-tab", "backtab") else 1
            self._set_focus(self._focus + step)
            return None
        target = self._targets[self._focus]
        if key == "q" and not isinstance(target, Input):
            return "quit"
        target.on_key(event)
        return None

    def on_click(self, pos: Pos) -> str | None:
        row = pos.y - self._top
        if row < 0:
            return None
        current: object = self._root
        r, c = row, pos.x
        for _ in range(16):
            child_at = getattr(current, "child_at", None)
            if child_at is None:
                break
            found = child_at(r, c)
            if found is None:
                break
            current, r, c = found
        for index, target in enumerate(self._targets):
            if current is target:
                self._set_focus(index)
                # Route the click into the focused component, not just the
                # gallery's own focus.  A branch row in the Tree is clicked
                # to fold/unfold it (desktop-tree semantics); every other
                # widget gets its own on_click at the local cell.
                if target.on_click(Pos(x=c, y=r)) and target is self.tree:
                    target.on_action("activate")
                break
        return None


def _scenes(theme: Theme, *, seed: int | None = 0) -> dict[str, Scene]:
    """Build one scene object per :data:`SCENES`, in tour order."""
    return {
        "splash": SplashScene(theme, seed=seed),
        "menu": MenuScene(theme),
        "snake": SnakeScene(theme),
        "dashboard": DashboardScene(theme),
        "gallery": GalleryScene(theme),
    }


class Showcase(Widget):
    """The whole demo: a scene name, a phase and the scene objects.

    ``render`` delegates to the current scene and pads the answer to the
    pane's height budget, so the fill section owns every row exactly as a
    full-screen widget must.  ``tick`` advances the phase (the scenes read
    it for sweeping, pulsing and progress) and applies a scene's transition;
    ``on_key``/``on_click`` do the same for input.  ``on_quit`` is the host's
    callback for the ``"quit"`` transition -- the showcase never touches the
    runtime itself.
    """

    __slots__ = ("_scenes", "on_quit", "phase", "scene")

    #: The host's quit callback (``App.quit`` under ``python -m motui``).
    on_quit: Callable[[], None] | None

    #: The showcase is the App's one focus target and takes mouse clicks.
    focusable = True
    clickable = True

    def __init__(
        self,
        scene: str = "splash",
        theme: Theme | None = None,
        *,
        seed: int | None = 0,
    ) -> None:
        if scene not in SCENES:
            raise ValueError(f"unknown scene {scene!r}: expected one of {SCENES}")
        resolved = Theme.dark() if theme is None else theme
        super().__init__(resolved)
        self._scenes = _scenes(resolved, seed=seed)
        self.scene = scene
        self.phase = START_PHASE
        self.on_quit = None

    def switch(self, name: str, *, phase: int = START_PHASE) -> None:
        """Make ``name`` the current scene, resetting the phase by default."""
        if name not in SCENES:
            raise ValueError(f"unknown scene {name!r}: expected one of {SCENES}")
        if name == "splash":
            # A fresh visit gets a fresh style order (and a live seed gives a
            # different order on every return to the splash).
            self._scenes["splash"].restart()
        self.scene = name
        self.phase = phase
        self.touch()

    def tick(self) -> str | None:
        """Advance one animation tick; answer the transition, if any."""
        self.phase += 1
        target = self._scenes[self.scene].tick(self.phase)
        if target is not None:
            self._route(target)
        else:
            self.touch()
        return target

    def on_key(self, event: KeyEvent) -> bool:
        """Route a key to the scene; the showcase consumes every key."""
        target = self._scenes[self.scene].on_key(event)
        self._route(target)
        return True

    def on_click(self, pos: Pos) -> bool:
        """Route a click to the scene; the showcase consumes it."""
        target = self._scenes[self.scene].on_click(pos)
        self._route(target)
        return True

    def _route(self, target: str | None) -> None:
        """Apply one scene transition (``None`` is a no-op)."""
        if target is None:
            return
        if target == "quit":
            if self.on_quit is not None:
                self.on_quit()
            return
        self.switch(target)

    def render(self, c: Constraints) -> Surface:
        """The current scene's rows, padded to the pane's height budget."""
        surface = self._scenes[self.scene].render(c, self.phase)
        rows = list(surface)
        budget = c.max_height
        if budget is None:
            return Surface.of(rows, c.width)
        rows = rows[:budget]
        if len(rows) < budget:
            rows.extend(Line() for _ in range(budget - len(rows)))
        return Surface.of(rows, c.width)

    def __repr__(self) -> str:
        return f"Showcase(scene={self.scene!r}, phase={self.phase})"
