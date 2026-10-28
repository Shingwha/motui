"""The motion section: two drawing boards and a marker ladder.

The section's story is "two ways to draw a board".  The default ``rings``
mode is a judgment game painted on a :class:`~motui.widgets.PixelCanvas` --
sub-cell pixels in a slot/heat raster -- while the ``snake`` mode hands the
pane to the whole-cell :class:`~motui.demo.snake.SnakeScene` board (the
standalone ``"snake"`` scene stays the same object it always was).  ``tab``
swaps the boards, ``escape`` returns to the menu and ``q`` quits.

The rings game is the rhythm kind: rings are born on a fixed schedule and
shrink onto a target disc; ``space`` (or a click) judges the nearest
unjudged ring against its deadline.  The windows and scores are contract,
not taste: within 0.06 s of the deadline is a Perfect (+300), within 0.12 s
a Good (+100), within 0.20 s a force hit (the combo clears); a ring nobody
judged dissolves cold as a Miss.  Perfect and Good count hits; a force hit
and a Miss count attempts only, and the HUD shows combo/score/hits over
attempts.  Each ring takes the next color of the four ring slots (rotation
by concurrency order) and a uniform position inside the margin drawn from
one seeded :class:`random.Random` -- reset when the board is resized, so a
geometry change re-deals fairly.  The clock is the shell's integer phase
(``phase / 60``): no wall time enters anywhere, so a headless replay at a
fixed phase paints exactly the live frame.

Under both boards runs the marker ladder: the same test circle drawn by two
:class:`PixelCanvas` instances, one per marker (``half`` and ``braille``),
plus a third slot labeled ``unprobed`` -- octant support is an explicit
host capability and a widget never probes the terminal.

Measured cost of a whole motion frame at 100x30 (CPython 3.13.16, Windows;
7 rounds of 200 frames, median of per-round medians): rings mode with three
live rings answers **2.8 ms** (2.0 ms at 80x24).  The board rides the
kernel's transparent blank cells (no palette background is painted any
more -- the target disc is a solid half-block disc on the fill layer, the
rings braille two sub-cells thick), which is both the readable-on-a-real-
terminal shape and roughly three times cheaper than the pre-transparency
quantize; the 8 ms budget holds with room to spare at the full 80-cell
board.  Snake mode answers ~8.1 ms on the same protocol, of which ~7.4 ms
is the unchanged whole-cell snake board itself and the rest the ladder
chrome.  The splash's pixel wordmark measures 3.9-4.0 ms across its four
packs at the same geometry and protocol.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.pixel import PixelPalette
from ...kernel.style import Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import PixelCanvas
from ..snake import SnakeScene

__all__ = ["RINGS_SEED", "MotionScene"]

_CLIP = WrapMode.CLIP

#: The shell's tick rate: the rings clock is the phase divided by this.
_TICK_HZ = 60

#: The spawn sequence's seed; a board resize resets the generator to it.
RINGS_SEED = 20261028

#: The rings schedule, in seconds: the first birth, the spacing, the
#: approach, the three judgment windows around the deadline, the target
#: disc's pop, the hit burst and the miss fade.
_BIRTH_DELAY = 0.4
_SPAWN_PERIOD = 1.2
_APPROACH = 1.0
_OUTER_RADIUS = 26
_TARGET_RADIUS = 8
_WINDOW_PERFECT = 0.06
_WINDOW_GOOD = 0.12
_WINDOW_FORCE = 0.20
_POP = 0.15
_BURST = 0.35
_BURST_OVERSHOOT = 20
_MISS_FADE = 0.4

#: The good-window blink: the shrinking ring flashes white at ~10 Hz.
_BLINK_TICKS = 3

#: A phase jump longer than this starts a fresh board, like a rewind does.
_MAX_SYNC = 7200

#: The ladder: a label row plus the three rows of each 6-cell mini canvas.
_LADDER_ROWS = 4
_LADDER_CELLS = 6

#: The board palette: four ring slots rotating by concurrency order, the
#: judgment colors (white Perfect, pink Good, cold force/miss) and the
#: lavender ladder accent.
_RING_PALETTE = PixelPalette(
    slots={
        1: ((255, 99, 132), (122, 46, 64)),
        2: ((83, 200, 240), (30, 92, 118)),
        3: ((242, 193, 78), (124, 94, 36)),
        4: ((91, 209, 139), (36, 100, 68)),
        5: ((255, 255, 255), (170, 174, 192)),
        6: ((255, 128, 192), (130, 58, 98)),
        7: ((150, 154, 172), (86, 90, 106)),
        8: ((196, 181, 253), (94, 84, 130)),
    },
)

#: The ladder palette: one accent, so both markers draw the same circle.
_LADDER_PALETTE = PixelPalette(slots={1: ((83, 200, 240), (30, 92, 118))})

#: Burst colors by verdict: Perfect bursts white, Good pink, force cold.
_BURST_SLOTS = {"perfect": 5, "good": 6}


@dataclass(slots=True)
class _Ring:
    """One judgment circle: position, slot color and where it stands."""

    cx: float
    cy: float
    slot: int
    born: float
    state: str  # "live" | "burst" | "miss"
    verdict: str | None  # "perfect" | "good" | "force" on a judged ring
    at: float  # the judgment or miss time


def _ease_out_back(t: float) -> float:
    """The ease-out-back curve: overshoots ~1.1 mid-way, settles on 1.0."""
    c1 = 1.70158
    c3 = c1 + 1.0
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


class MotionScene:
    """The motion section: the rings board, the snake board, the ladder.

    State is public on purpose (``mode``, ``combo``, ``score``, ``hits``,
    ``attempts``), mirroring :class:`~motui.demo.snake.SnakeScene`: tests
    can read what a player's keys drive.  Every render is a pure function
    of the geometry and the phase -- the ring list is rebuilt from the
    phase-derived schedule and the seeded positions -- so replays are
    byte-identical.
    """

    name = "motion"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self.mode = "rings"
        self.combo = 0
        self.score = 0
        self.hits = 0
        self.attempts = 0
        self._phase = 0
        self._board = PixelCanvas(palette=_RING_PALETTE)
        self._half = PixelCanvas(_LADDER_CELLS, 3, marker="half", palette=_LADDER_PALETTE)
        self._braille = PixelCanvas(_LADDER_CELLS, 3, marker="braille", palette=_LADDER_PALETTE)
        self._snake = SnakeScene(theme)
        self._rings: list[_Ring] = []
        self._rng = random.Random(RINGS_SEED)
        self._born_count = 0
        # The board geometry until the first render says otherwise.
        self._geom = (160, 96)

    # -- schedule ----------------------------------------------------------

    def _sync(self, phase: int) -> None:
        """Advance the ring bookkeeping to ``phase``.

        A rewind (or a jump too long to replay honestly) starts a fresh
        board.  Births due by ``phase`` are dealt from the seeded RNG in
        order; a live ring whose force window has passed dissolves as a
        Miss; finished bursts and fades drop off the list.
        """
        if phase < self._phase or phase - self._phase > _MAX_SYNC:
            self._reset_board()
            # a rewind is a fresh entry (the shell resets its phase on every
            # switch): land on the default board, never a stale tab choice
            self.mode = "rings"
        self._phase = phase
        now = phase / _TICK_HZ
        while True:
            born = _BIRTH_DELAY + self._born_count * _SPAWN_PERIOD
            if born > now:
                break
            self._spawn(born)
        for ring in self._rings:
            deadline = ring.born + _APPROACH + _WINDOW_FORCE
            if ring.state == "live" and now > deadline:
                ring.state = "miss"
                ring.at = deadline
                self.combo = 0
                self.attempts += 1
        self._rings = [
            ring
            for ring in self._rings
            if ring.state == "live"
            or now - ring.at < (_BURST if ring.state == "burst" else _MISS_FADE)
        ]

    def _reset_board(self) -> None:
        """A fresh game: no rings, the seed and every counter reset."""
        self._rings.clear()
        self._born_count = 0
        self._rng = random.Random(RINGS_SEED)
        self.combo = 0
        self.score = 0
        self.hits = 0
        self.attempts = 0

    def _spawn(self, born: float) -> None:
        """Deal one ring: the next slot color, a uniform position inside
        the margin (``min(34, half the board)`` sub-cells), so the widest
        ring and its burst stay on the canvas."""
        width, height = self._geom
        margin = min(34, width // 2, height // 2)
        self._rings.append(
            _Ring(
                cx=self._rng.uniform(margin, width - margin),
                cy=self._rng.uniform(margin, height - margin),
                slot=1 + self._born_count % 4,
                born=born,
                state="live",
                verdict=None,
                at=0.0,
            )
        )
        self._born_count += 1

    def _judge(self, now: float) -> None:
        """Judge the nearest unjudged ring against its deadline.

        The windows are the contract: <=0.06 s Perfect +300, <=0.12 s Good
        +100, <=0.20 s a force hit (combo clears, no points); nothing
        inside any window and the press is a no-op.  A hit bursts the ring
        in its verdict's color; Perfect/Good raise the combo and count
        hits, a force hit counts an attempt only.
        """
        best: _Ring | None = None
        best_error = 0.0
        for ring in self._rings:
            if ring.state != "live":
                continue
            error = abs(now - (ring.born + _APPROACH))
            if best is None or error < best_error:
                best, best_error = ring, error
        if best is None:
            return
        if best_error <= _WINDOW_PERFECT:
            verdict, points = "perfect", 300
        elif best_error <= _WINDOW_GOOD:
            verdict, points = "good", 100
        elif best_error <= _WINDOW_FORCE:
            verdict, points = "force", 0
        else:
            return
        best.state = "burst"
        best.verdict = verdict
        best.at = now
        self.score += points
        if verdict == "force":
            self.combo = 0
        else:
            self.combo += 1
            self.hits += 1
        self.attempts += 1

    # -- input -------------------------------------------------------------

    def on_key(self, event: KeyEvent) -> str | None:
        """``tab`` swaps boards; rings mode judges on ``space``; the snake
        mode forwards everything else to its scene."""
        if event.key == "tab":
            self.mode = "snake" if self.mode == "rings" else "rings"
            return None
        if self.mode == "snake":
            return self._snake.on_key(event)
        if event.key == "space":
            self._judge(self._phase / _TICK_HZ)
            return None
        if event.key == "escape":
            return "menu"
        if event.key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        """A click judges (the mouse door of ``space``); the snake mode
        forwards to its scene."""
        if self.mode == "snake":
            return self._snake.on_click(pos)
        self._judge(self._phase / _TICK_HZ)
        return None

    def tick(self, phase: int) -> str | None:
        """Advance the active board; the section itself never leaves."""
        self._phase = phase
        if self.mode == "snake":
            self._snake.tick(phase)
        else:
            self._sync(phase)
        return None

    # -- rendering ---------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        """The active board, the marker ladder and the hint, at ``phase``."""
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        self._phase = phase
        if self.mode == "snake":
            rows = list(
                self._snake.render(
                    Constraints(width=width, max_height=max(1, height - _LADDER_ROWS - 1)),
                    phase,
                )
            )
        else:
            rows = self._render_rings(width, height, phase)
        rows = [*rows, *self._ladder(width), self._hint(width)]
        rows = rows[:height]
        rows.extend(Line() for _ in range(height - len(rows)))
        return Surface.of(rows, width)

    def _render_rings(self, width: int, height: int, phase: int) -> list[Line]:
        """The pixel board: HUD row, then the quantized rings frame.

        The board caps at 80 cells wide like the snake's block; a wider or
        taller pane centres the board rather than stretching it.  Since the
        kernel stopped painting blank cells, a 100x30 frame measures ~2 ms
        median and no further size cap is needed.
        """
        board_h = max(4, height - _LADDER_ROWS - 2)
        board_w = max(12, min(80, width))
        self._fit_board(board_w, board_h)
        self._sync(phase)
        canvas = self._board
        canvas.clear()
        now = phase / _TICK_HZ
        for ring in self._rings:
            self._paint(canvas, ring, now, phase)
        board = list(canvas.render(Constraints(width=board_w)))
        rows = [self._hud(board_w), *board]
        if board_w != width:
            pad = Line((Segment(" " * max(0, (width - board_w) // 2)),))
            rows = [pad + row for row in rows]
        return rows

    def _fit_board(self, width: int, height: int) -> None:
        """Sync the board canvas to the pane; a resize resets the spawn RNG."""
        if (width, height) != (self._board.width, self._board.height):
            self._board.resize(width, height)
            self._rng = random.Random(RINGS_SEED)
        self._geom = (self._board.art.width, self._board.art.height)

    def _paint(self, canvas: PixelCanvas, ring: _Ring, now: float, phase: int) -> None:
        """One ring's frame: approach ring, target disc, burst or fade.

        The target disc lands on the **fill** layer: a solid half-block
        disc survives every terminal font, while a braille disc reads as
        sparse dots (the marker ladder shows exactly that).  The rings
        ride the art layer two sub-cells thick so their braille dots
        bridge the font's gaps.
        """
        if ring.state == "live":
            age = now - ring.born
            if age <= _APPROACH:
                t = age / _APPROACH
                radius = _OUTER_RADIUS + (_TARGET_RADIUS - _OUTER_RADIUS) * t
                error = abs(now - (ring.born + _APPROACH))
                flash = error <= _WINDOW_GOOD and (phase // _BLINK_TICKS) % 2 == 0
                canvas.ring(ring.cx, ring.cy, radius, 2, 5 if flash else ring.slot)
            pop = min(1.0, age / _POP)
            canvas.fill_disc(ring.cx, ring.cy, _TARGET_RADIUS * _ease_out_back(pop), ring.slot)
        elif ring.state == "burst":
            t = (now - ring.at) / _BURST
            radius = _TARGET_RADIUS + _BURST_OVERSHOOT * _ease_out_back(min(1.0, t))
            self._fading_ring(
                canvas,
                ring.cx,
                ring.cy,
                radius,
                _BURST_SLOTS.get(ring.verdict or "", 7),
                max(0, round(255 * (1.0 - t))),
            )
        else:
            t = (now - ring.at) / _MISS_FADE
            self._fading_ring(
                canvas,
                ring.cx,
                ring.cy,
                _TARGET_RADIUS,
                7,
                max(0, round(255 * (1.0 - t))),
            )

    def _fading_ring(
        self, canvas: PixelCanvas, cx: float, cy: float, r: float, slot: int, heat: int
    ) -> None:
        """A ring whose ink carries an explicit heat (the fade), not 255.

        ``Raster.set`` always refreshes the heat to full, so a cooling
        ring -- a burst burning out or a miss dissolving -- writes the
        public rasters directly, the documented pattern
        :meth:`PixelCanvas.unset` uses.  This is drawing, not quantizing:
        the kernel still owns the pixels-to-cells pass.  Two half-step
        radii give the ring the same two-sub-cell thickness as
        :meth:`Raster.ring` at ``thickness=2``, so braille dots bridge
        the font's gaps.
        """
        art = canvas.art
        width, height = art.width, art.height
        slot_grid, heat_grid = art.slot, art.heat
        steps = max(32, int(2 * math.pi * r * 2))
        for index in range(steps):
            angle = 2 * math.pi * index / steps
            for radius in (r - 0.5, r + 0.5):
                x = int(cx + radius * math.cos(angle))
                y = int(cy + radius * math.sin(angle))
                if 0 <= x < width and 0 <= y < height:
                    cell = y * width + x
                    slot_grid[cell] = slot
                    heat_grid[cell] = heat

    # -- chrome ------------------------------------------------------------

    def _hud(self, width: int) -> Line:
        """One row: rings combo/score/hits on the left, the board on the right."""
        left = (
            f"rings  combo {self.combo:02d}  score {self.score:04d}"
            f"  hits {self.hits}/{self.attempts}"
        )
        return _ends(width, left, "pixel board", self.theme.text.muted, self.theme.content.accent)

    def _hint(self, width: int) -> Line:
        """The key hint of the active board, one clipped row."""
        if self.mode == "rings":
            text = "space judge \u00b7 click judge \u00b7 tab snake \u00b7 esc menu"
        else:
            text = "tab rings \u00b7 esc menu"
        return _fit(Line.from_text(text, self.theme.text.faint), width)

    def _ladder(self, width: int) -> list[Line]:
        """The marker ladder: the same test circle at ``half`` and at
        ``braille`` resolution, with the ``octant`` slot left ``unprobed``."""
        muted = self.theme.text.muted
        faint = self.theme.text.faint
        half = self._mini_circle(self._half)
        braille = self._mini_circle(self._braille)
        rows = [
            Line(
                (
                    Segment("  "),
                    Segment("half", muted),
                    Segment("      "),
                    Segment("braille", muted),
                    Segment("   "),
                    Segment("octant", muted),
                )
            )
        ]
        for index in range(3):
            row = (
                Line((Segment("  "),))
                + half[index]
                + Line((Segment("    "),))
                + braille[index]
                + Line((Segment("    "),))
            )
            if index == 1:
                row = row + Line((Segment("unprobed", faint),))
            rows.append(_fit(row, width))
        return rows

    def _mini_circle(self, canvas: PixelCanvas) -> list[Line]:
        """The ladder's test circle on one 6x3-cell mini canvas."""
        canvas.clear()
        canvas.ring(6, 6, 5, 1, 1)
        return list(canvas.render(Constraints(width=_LADDER_CELLS)))

    def __repr__(self) -> str:
        return (
            f"MotionScene(mode={self.mode!r}, score={self.score}, "
            f"combo={self.combo}, rings={len(self._rings)})"
        )


def _ends(
    width: int,
    left: str,
    right: str,
    left_style: Style,
    right_style: Style,
) -> Line:
    """One row with ``left`` at the start and ``right`` at the end."""
    gap = max(1, width - len(left) - len(right) - 2)
    line = Line(
        (
            Segment(" "),
            Segment(left, left_style),
            Segment(" " * gap),
            Segment(right, right_style),
            Segment(" "),
        )
    )
    return _fit(line, width)


def _fit(line: Line, width: int) -> Line:
    """The line when it fits (the common case), else clipped to ``width``.

    ``Line.clip`` pays a full column walk even for a fitting row, so the
    per-frame chrome only clips when a pane is genuinely too narrow.
    """
    return line if line.width <= width else line.clip(_CLIP, width)
