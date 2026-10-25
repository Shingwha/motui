"""Breakout: a deterministic paddle-and-bricks scene painted on a Canvas.

The game owns no clock and no random source: one ``tick`` advances the ball
one integer cell (or a whole level's speed), so a phase replayed headlessly
paints exactly the frame the live showcase paints.  The playfield is boxed
and capped at 80x24, centred in the pane, with one HUD row above it and one
key-hint row below.  The walls, the paddle and the wall of bricks are cells,
so the scene is one Canvas plus three composed rows.

The state is deliberately small and public: score, lives, level, the
paddle/ball coordinates, the brick set and the paused/launched flags.  Tests
can drive the same values a player's keys drive, without reaching into a
private simulation.
"""

from __future__ import annotations

from ..kernel.cell import Line, Segment, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets import Canvas, Column, Panel, Text

__all__ = ["BreakoutScene"]

#: The playfield's ceiling; a wider or taller pane keeps the block centred.
_MAX_WIDTH = 80
_MAX_HEIGHT = 24

#: The brick wall: four rows of two-cell bricks with a one-cell gap.
_BRICK_ROWS = 4
_BRICK_COLUMNS = 12
_BRICK_WIDTH = 2
_BRICK_PITCH = 3
_BRICK_TOP = 1

#: The paddle and the serve.
_PADDLE_WIDTH = 7
_PADDLE_STEP = 4
_START_LIVES = 3
_MAX_SPEED = 3

#: A phase jump replays at most this many ticks (a snapshot never walks forever).
_MAX_SYNC = 4096

_CLIP = WrapMode.CLIP

#: One brick glyph: the lower half block, so a brick reads as a strip.
_BRICK = "\u2584"
_PADDLE = "\u2550"
_BALL = "\u25cf"
_HEART = "\u2665"
_EMPTY_HEART = "\u00b7"


class BreakoutScene:
    """The whole game: state, collision, input and Canvas rendering.

    Coordinates below the HUD are playfield-local: ``(0, 0)`` is the inner
    top-left cell.  The frame's wall box is drawn around them, so a ball at
    ``x == 0`` and a paddle at ``paddle_x == 0`` touch the left wall.
    """

    name = "breakout"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        # The default 80x24 block until the first render says otherwise.
        self._left = 0
        self._top = 0
        self._width = _MAX_WIDTH
        self._height = _MAX_HEIGHT - 2
        self._iw = _MAX_WIDTH - 2
        self._ih = _MAX_HEIGHT - 4
        self._cols = _BRICK_COLUMNS
        self._brick_x = max(
            0, (self._iw - (_BRICK_COLUMNS * _BRICK_PITCH - 1)) // 2
        )
        self.paddle_x = 0
        self.ball_x = 0
        self.ball_y = 0
        self.dx = 1
        self.dy = -1
        self.bricks: set[tuple[int, int]] = set()
        self.score = 0
        self.level = 1
        self.lives = _START_LIVES
        self.speed = 1
        self.paused = False
        self.launched = True
        self.game_over = False
        self._reset()

    # -- layout ------------------------------------------------------------

    @property
    def paddle_y(self) -> int:
        """The paddle's playfield row (one row above the bottom wall)."""
        return max(1, self._ih - 2)

    def _place(self, width: int, height: int) -> None:
        """Fit the capped block into the pane and re-clamp both sprites."""
        block_w = max(4, min(width, _MAX_WIDTH))
        block_h = max(4, min(height, _MAX_HEIGHT))
        self._left = max(0, (width - block_w) // 2)
        self._top = max(0, (height - block_h) // 2)
        self._width = block_w
        self._height = max(1, block_h - 2)
        self._iw = max(1, block_w - 2)
        self._ih = max(1, self._height - 2)
        self._cols = max(1, min(_BRICK_COLUMNS, (self._iw + 1) // _BRICK_PITCH))
        span = self._cols * _BRICK_PITCH - 1
        self._brick_x = max(0, (self._iw - span) // 2)
        self.paddle_x = max(0, min(self.paddle_x, self._iw - _PADDLE_WIDTH))
        self.ball_x = max(0, min(self.ball_x, self._iw - 1))
        self.ball_y = max(0, min(self.ball_y, max(0, self._ih - 1)))

    # -- state -------------------------------------------------------------

    def _reset(self) -> None:
        """A new game: score zero, three lives, level one, ball in play."""
        self.score = 0
        self.level = 1
        self.lives = _START_LIVES
        self.speed = 1
        self.paused = False
        self.launched = True
        self.game_over = False
        self.dx, self.dy = 1, -1
        self._fill_bricks()
        self.paddle_x = max(0, (self._iw - _PADDLE_WIDTH) // 2)
        self._park_ball()

    def _fill_bricks(self) -> None:
        """Lay a deterministic wall: the level rotates a fixed hole pattern."""
        level = self.level
        self.bricks = {
            (row, col)
            for row in range(_BRICK_ROWS)
            for col in range(_BRICK_COLUMNS)
            if (row * 3 + col * 5 + level * 7) % 13 != 0
        }

    def _park_ball(self) -> None:
        """Rest the ball on the paddle, ready for the next serve."""
        self.ball_x = self.paddle_x + _PADDLE_WIDTH // 2
        self.ball_y = self.paddle_y - 1

    def _serve(self) -> None:
        """Launch the parked ball with a level-dependent opening angle."""
        self.launched = True
        self.dx = 1 if self.level % 2 else -1
        self.dy = -1

    def _move_paddle(self, delta: int) -> None:
        """Shift the paddle, carrying the parked ball when it has not served."""
        self.paddle_x = max(
            0, min(self._iw - _PADDLE_WIDTH, self.paddle_x + delta)
        )
        if not self.launched:
            self._park_ball()

    def _space(self) -> None:
        """Space is serve, pause, resume and restart, in that order."""
        if self.game_over:
            self._reset()
        elif not self.launched:
            self._serve()
        elif self.paused:
            self.paused = False
        else:
            self.paused = True

    # -- simulation --------------------------------------------------------

    def _sync(self, phase: int) -> None:
        """Advance the state to ``phase``; a backwards jump starts a new game."""
        if phase < self._phase:
            self._reset()
            self._phase = 0
        steps = min(max(0, phase - self._phase), _MAX_SYNC)
        for _ in range(steps):
            self._advance()
        self._phase = phase

    def _advance(self) -> None:
        """One animation tick: serve, pause or move the ball ``speed`` cells."""
        if self.game_over or self.paused:
            return
        if not self.launched:
            self._park_ball()
            return
        for _ in range(self.speed):
            self._step_ball()
            if self.game_over or not self.launched:
                return

    def _step_ball(self) -> None:
        """Move one cell on each axis, bouncing off walls, bricks and paddle."""
        # Horizontal: wall, then a brick side.
        nx = self.ball_x + self.dx
        if nx < 0 or nx >= self._iw:
            self.dx = -self.dx
            nx = self.ball_x + self.dx
        hit = self._brick_at(nx, self.ball_y)
        if hit is not None:
            self._break_brick(hit)
            self.dx = -self.dx
            nx = self.ball_x + self.dx
        self.ball_x = max(0, min(self._iw - 1, nx))

        # Vertical: ceiling, then a brick face.
        ny = self.ball_y + self.dy
        if ny < 0:
            self.dy = -self.dy
            ny = self.ball_y + self.dy
        hit = self._brick_at(self.ball_x, ny)
        if hit is not None:
            self._break_brick(hit)
            self.dy = -self.dy
            ny = self.ball_y + self.dy

        # The paddle: a hit sends the ball back up with a steering angle.
        if (
            self.dy > 0
            and ny >= self.paddle_y
            and self.paddle_x <= self.ball_x < self.paddle_x + _PADDLE_WIDTH
        ):
            self.dy = -1
            ny = self.paddle_y - 1
            third = (self.ball_x - self.paddle_x) * 3 // _PADDLE_WIDTH
            self.dx = (-1, self.dx, 1)[min(2, max(0, third))]

        if ny >= self._ih:
            self._lose_ball()
            return
        self.ball_y = max(0, ny)
        if not self.bricks:
            self._next_level()

    def _brick_at(self, x: int, y: int) -> tuple[int, int] | None:
        """The brick key covering playfield cell ``(x, y)``, if any."""
        row = y - _BRICK_TOP
        if not 0 <= row < _BRICK_ROWS or x < self._brick_x:
            return None
        offset = x - self._brick_x
        col = offset // _BRICK_PITCH
        if col >= self._cols or offset % _BRICK_PITCH >= _BRICK_WIDTH:
            return None
        key = (row, col)
        return key if key in self.bricks else None

    def _break_brick(self, key: tuple[int, int]) -> None:
        """Remove one brick and score it."""
        if key in self.bricks:
            self.bricks.discard(key)
            self.score += 10

    def _lose_ball(self) -> None:
        """Spend a life; the third miss is game over."""
        self.lives -= 1
        self.launched = False
        self.paused = False
        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
        else:
            self._park_ball()

    def _next_level(self) -> None:
        """Refill the wall, quicken the ball and wait for the next serve."""
        self.level += 1
        self.speed = min(_MAX_SPEED, 1 + (self.level - 1) // 2)
        self.launched = False
        self.paused = False
        self.dy = -1
        self._fill_bricks()
        self._park_ball()

    # -- input -------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        """Advance one tick; the game itself never leaves the scene."""
        self._sync(phase)
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        """Paddle, serve/pause, or back to the menu."""
        key = event.key
        if key in ("left", "h"):
            self._move_paddle(-_PADDLE_STEP)
        elif key in ("right", "l"):
            self._move_paddle(_PADDLE_STEP)
        elif key == "space":
            self._space()
        elif key == "enter" and self.game_over:
            self._reset()
        elif key in ("escape", "q"):
            return "menu"
        return None

    def on_click(self, pos: Pos) -> str | None:
        """A click on a game-over board restarts; other clicks are inert."""
        if self.game_over:
            self._reset()
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
        """The boxed Canvas: bricks, paddle, ball and the game-over overlay."""
        canvas = Canvas(width, height, theme=self.theme)
        if width >= 4 and height >= 3:
            canvas.box(0, 0, width, height, style=self.theme.borders.base)

        brick_styles = (
            self.theme.status.danger,
            self.theme.status.warning,
            self.theme.status.success,
            self.theme.content.accent,
        )
        for row, col in sorted(self.bricks):
            if col >= self._cols:
                continue
            x = 1 + self._brick_x + col * _BRICK_PITCH
            y = 1 + _BRICK_TOP + row
            style = brick_styles[row % len(brick_styles)]
            canvas.put(x, y, _BRICK, style)
            canvas.put(x + 1, y, _BRICK, style)

        paddle_style = self.theme.content.accent.merge(Style(bold=True))
        canvas.hline(
            1 + self.paddle_x,
            1 + self.paddle_y,
            _PADDLE_WIDTH,
            _PADDLE,
            paddle_style,
        )
        ball_style = self.theme.status.warning.merge(Style(bold=True))
        canvas.put(1 + self.ball_x, 1 + self.ball_y, _BALL, ball_style)

        rows = list(canvas.surface())
        if self.game_over:
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
        panel = Panel(body, title="breakout", theme=self.theme)
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
        """One row: score/level on the left, lives/state on the right."""
        state = (
            "GAME OVER"
            if self.game_over
            else "PAUSED"
            if self.paused
            else "SERVE"
            if not self.launched
            else "RUNNING"
        )
        hearts = _HEART * self.lives + _EMPTY_HEART * (_START_LIVES - self.lives)
        left = f"breakout  score {self.score:04d}  level {self.level}"
        right = f"{hearts}  {state}"
        right_style = (
            self.theme.status.danger
            if self.game_over
            else self.theme.status.warning
            if self.paused
            else self.theme.text.muted
        )
        return _ends(width, left, right, self.theme.text.muted, right_style)

    def _hint(self, width: int) -> Line:
        """The key hint: one clipped row under the playfield."""
        return Line.from_text(
            "\u2190/\u2192 or h/l paddle \u00b7 space serve/pause \u00b7 esc menu",
            self.theme.text.faint,
        ).clip(_CLIP, width)

    def __repr__(self) -> str:
        return (
            f"BreakoutScene(score={self.score}, lives={self.lives}, "
            f"level={self.level}, bricks={len(self.bricks)})"
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
