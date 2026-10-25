"""Snake: a deterministic, Canvas-painted snake game for the showcase.

The game owns no clock and no global random source: one ``tick`` advances the
animation, and the snake takes one integer step every few ticks, so a phase
replayed headlessly paints exactly the frame the live showcase paints.  Food
comes from a per-game :class:`random.Random` seeded with a fixed value, so the
same reset always deals the same board.

The playfield is boxed and capped at 80x24, centred in the pane, with one HUD
row above it and one key-hint row below.  The walls, the snake and the food
are Canvas cells; the scene is one Canvas plus three composed rows.

The state is public on purpose: score, alive/paused, the direction, the snake
segments and the food cell.  Tests can drive the same values a player's keys
drive, without reaching into a private simulation.
"""

from __future__ import annotations

import random

from ..kernel.cell import Line, Segment, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets import Canvas, Column, Panel, Text

__all__ = ["SnakeScene"]

#: The playfield's ceiling; a wider or taller pane keeps the block centred.
_MAX_WIDTH = 80
_MAX_HEIGHT = 24

#: The starting snake and the pace: one move every four animation ticks.
_START_LENGTH = 4
_STEP_TICKS = 4
_MAX_SYNC = 4096

#: A fixed seed makes a reset and a headless replay deal the same food.
_SEED = 20261025

_CLIP = WrapMode.CLIP

#: A terminal cell is about twice as tall as it is wide, so one logical game
#: cell is drawn as a half block: two logical rows share one screen row, and
#: every square is the same shape whether the snake runs across or down.
_HALF_TOP = "\u2580"
_HALF_BOTTOM = "\u2584"
_FULL = "\u2588"


class SnakeScene:
    """The whole game: state, movement, collision, input and Canvas rendering.

    Coordinates below the HUD are playfield-local: ``(0, 0)`` is the inner
    top-left cell.  The frame's wall box is drawn around them, so a head at
    ``x == 0`` touches the left wall and a head at ``y == 0`` the ceiling.
    """

    name = "snake"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._clock = 0
        # The capped block until the first render says otherwise.
        self._left = 0
        self._top = 0
        self._width = _MAX_WIDTH
        self._height = _MAX_HEIGHT - 2
        self._iw = _MAX_WIDTH - 2
        self._ih = 2 * (_MAX_HEIGHT - 4)
        # The public game state (see the module docstring).
        self.score = 0
        self.alive = True
        self.paused = False
        self.dx = 1
        self.dy = 0
        self.snake: list[tuple[int, int]] = []
        self.food: tuple[int, int] = (0, 0)
        self._rng = random.Random(_SEED)
        self._reset()

    # -- layout ------------------------------------------------------------

    def _place(self, width: int, height: int) -> None:
        """Fit the capped block into the pane; reset if the field outgrows it."""
        block_w = max(4, min(width, _MAX_WIDTH))
        block_h = max(4, min(height, _MAX_HEIGHT))
        self._left = max(0, (width - block_w) // 2)
        self._top = max(0, (height - block_h) // 2)
        self._width = block_w
        self._height = max(1, block_h - 2)
        self._iw = max(1, block_w - 2)
        # Two logical rows per screen row: each square is a half block.
        self._ih = max(2, 2 * max(1, self._height - 2))
        if any(
            x >= self._iw or y >= self._ih for x, y in self.snake
        ) or self.food[0] >= self._iw or self.food[1] >= self._ih:
            # A shrinking pane would otherwise hide part of the snake; a
            # fresh board is honest and keeps every cell addressable.
            self._reset()

    # -- state -------------------------------------------------------------

    def _reset(self) -> None:
        """A new game: a centred four-cell snake heading right, food dealt."""
        self.score = 0
        self.alive = True
        self.paused = False
        self.dx, self.dy = 1, 0
        cx = max(2, self._iw // 2)
        cy = max(2, self._ih // 2)
        # Head first: the body trails to the left of a right-moving head.
        self.snake = [(cx - index, cy) for index in range(_START_LENGTH)]
        self._rng = random.Random(_SEED)
        self._clock = 0
        self._phase = 0
        self._place_food()

    def _place_food(self) -> None:
        """Deal the next food cell from the free cells, deterministically."""
        occupied = set(self.snake)
        free = [
            (x, y)
            for y in range(self._ih)
            for x in range(self._iw)
            if (x, y) not in occupied
        ]
        if not free:
            self.food = (-1, -1)
            self.alive = False
            return
        self.food = free[self._rng.randrange(len(free))]

    # -- simulation --------------------------------------------------------

    def _sync(self, phase: int) -> None:
        """Advance to ``phase``; a backwards jump starts a new game."""
        if phase < self._phase:
            self._reset()
        steps = min(max(0, phase - self._phase), _MAX_SYNC)
        for _ in range(steps):
            self._advance()
        self._phase = phase

    def _advance(self) -> None:
        """One animation tick: pause/death are no-ops, a step lands every 4."""
        if not self.alive or self.paused:
            return
        self._clock += 1
        if self._clock % _STEP_TICKS:
            return
        self._step()

    def _step(self) -> None:
        """Move the head one cell; eat, grow, or collide."""
        head_x, head_y = self.snake[0]
        nx, ny = head_x + self.dx, head_y + self.dy
        if nx < 0 or nx >= self._iw or ny < 0 or ny >= self._ih:
            self.alive = False
            return
        eating = (nx, ny) == self.food
        body = self.snake if eating else self.snake[:-1]
        if (nx, ny) in body:
            self.alive = False
            return
        self.snake.insert(0, (nx, ny))
        if eating:
            self.score += 10
            self._place_food()
        else:
            self.snake.pop()

    # -- input -------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        """Advance one tick; the game itself never leaves the scene."""
        self._sync(phase)
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        """Steer, pause/restart, or return to the menu."""
        key = event.key
        if key in ("escape", "q"):
            return "menu"
        if key == "space":
            if not self.alive:
                self._reset()
            else:
                self.paused = not self.paused
            return None
        if key == "enter" and not self.alive:
            self._reset()
            return None
        turns = {
            "up": (0, -1),
            "w": (0, -1),
            "down": (0, 1),
            "s": (0, 1),
            "left": (-1, 0),
            "a": (-1, 0),
            "right": (1, 0),
            "d": (1, 0),
        }
        turn = turns.get(key)
        if turn is not None and (turn[0], turn[1]) != (-self.dx, -self.dy):
            self.dx, self.dy = turn
        return None

    def on_click(self, pos: Pos) -> str | None:
        """A click on a dead board restarts; a live board pauses or resumes."""
        if not self.alive:
            self._reset()
        else:
            self.paused = not self.paused
        return None

    # -- rendering ---------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        """The centred block: HUD, Canvas playfield and hint, at ``phase``."""
        height = c.max_height if c.max_height is not None else _MAX_HEIGHT
        self._place(c.width, height)
        self._sync(phase)
        rows: list[Line] = [
            self._hud(self._width),
            *self._field(self._width, self._height),
            self._hint(self._width),
        ]
        if self._left:
            prefix = Line((Segment(" " * self._left),))
            rows = [(prefix + row).clip(_CLIP, c.width) for row in rows]
        if self._top:
            rows = [Line() for _ in range(self._top)] + rows
        rows = rows[:height]
        if len(rows) < height:
            rows.extend(Line() for _ in range(height - len(rows)))
        return Surface.of(rows, c.width)

    def _field(self, width: int, height: int) -> list[Line]:
        """The boxed Canvas: food, snake and the game-over overlay."""
        canvas = Canvas(width, height, theme=self.theme)
        if width >= 4 and height >= 3:
            canvas.box(0, 0, width, height, style=self.theme.borders.base)

        food_style = self.theme.status.warning.merge(Style(bold=True))
        head_style = self.theme.content.accent.merge(Style(bold=True))
        body_style = self.theme.status.success
        # Two logical rows per terminal row: a logical cell owns the top or
        # bottom half of the screen cell.  Composing halves is what keeps a
        # vertical run gap-free while every block stays square-ish.
        tops: dict[tuple[int, int], Style] = {}
        bottoms: dict[tuple[int, int], Style] = {}

        def mark(x: int, y: int, style: Style) -> None:
            key = (x, y // 2)
            (tops if y % 2 == 0 else bottoms)[key] = style

        if self.food[0] >= 0:
            mark(self.food[0], self.food[1], food_style)
        for index, (x, y) in enumerate(self.snake):
            mark(x, y, head_style if index == 0 else body_style)

        for key in sorted(set(tops) | set(bottoms)):
            tx, ty = key
            has_top = key in tops
            has_bottom = key in bottoms
            if has_top and has_bottom:
                style = (
                    head_style
                    if head_style in (tops[key], bottoms[key])
                    else food_style
                    if food_style in (tops[key], bottoms[key])
                    else body_style
                )
                glyph = _FULL
            elif has_top:
                glyph, style = _HALF_TOP, tops[key]
            else:
                glyph, style = _HALF_BOTTOM, bottoms[key]
            canvas.put(1 + tx, 1 + ty, glyph, style)

        rows = list(canvas.surface())
        if not self.alive:
            rows = self._overlay(rows, width)
        return rows

    def _overlay(self, rows: list[Line], width: int) -> list[Line]:
        """Splice a centred game-over panel over the playfield rows."""
        panel_width = min(34, max(12, width - 4))
        body = Column(
            [
                Text("game over", style=self.theme.status.danger, theme=self.theme),
                Text(f"score {self.score}", theme=self.theme),
                Text(
                    "space restart \u00b7 esc menu",
                    style=self.theme.text.faint,
                    theme=self.theme,
                ),
            ],
            gap=0,
        )
        panel = Panel(body, title="snake", theme=self.theme)
        over = list(panel.render(Constraints(width=panel_width)))
        left = max(0, (width - panel_width) // 2)
        top = max(0, (len(rows) - len(over)) // 2)
        prefix = Line((Segment(" " * left),))
        for index, row in enumerate(over):
            y = top + index
            if 0 <= y < len(rows):
                rows[y] = (prefix + row).clip(_CLIP, width)
        return rows

    def _hud(self, width: int) -> Line:
        """One row: score/length on the left, state on the right."""
        state = (
            "GAME OVER" if not self.alive else "PAUSED" if self.paused else "RUNNING"
        )
        left = f"snake  score {self.score:04d}  length {len(self.snake)}"
        right = state
        right_style = (
            self.theme.status.danger
            if not self.alive
            else self.theme.status.warning
            if self.paused
            else self.theme.text.muted
        )
        return _ends(width, left, right, self.theme.text.muted, right_style)

    def _hint(self, width: int) -> Line:
        """The key hint: one clipped row under the playfield."""
        return Line.from_text(
            "arrows/wasd steer \u00b7 space pause \u00b7 esc menu",
            self.theme.text.faint,
        ).clip(_CLIP, width)

    def __repr__(self) -> str:
        return (
            f"SnakeScene(score={self.score}, length={len(self.snake)}, "
            f"alive={self.alive}, paused={self.paused})"
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
    return line.clip(_CLIP, width)
