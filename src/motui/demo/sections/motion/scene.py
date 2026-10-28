"""The motion section: a pixel rings game and its HUD."""

from __future__ import annotations

from ....kernel.cell import Line, Segment, Surface
from ....kernel.events import KeyEvent
from ....kernel.geom import Pos
from ....kernel.layout import Constraints
from ....kernel.theme import Theme
from ....pixel import PixelPalette
from ....widgets import PixelCanvas
from ...common import ends, fit
from ...scene import TICK_HZ, Scene
from .paint import paint
from .rings import RingsGame

__all__ = ["MotionScene"]

#: The board palette: four ring slots rotating by concurrency order, the
#: judgment colors (white Perfect, pink Good, cold force/miss).
_RING_PALETTE = PixelPalette(
    slots={
        1: ((255, 99, 132), (122, 46, 64)),
        2: ((83, 200, 240), (30, 92, 118)),
        3: ((242, 193, 78), (124, 94, 36)),
        4: ((91, 209, 139), (36, 100, 68)),
        5: ((255, 255, 255), (170, 174, 192)),
        6: ((255, 128, 192), (130, 58, 98)),
        7: ((150, 154, 172), (86, 90, 106)),
    },
)


class MotionScene(Scene):
    """A rhythm game on a sub-cell PixelCanvas.

    Rings are born on a fixed schedule and shrink onto a target disc;
    ``space`` (or a click) judges the nearest unjudged ring against its
    deadline.  The windows and scores are contract: within 0.06 s of the
    deadline is a Perfect (+300), within 0.12 s a Good (+100), within
    0.20 s a force hit (the combo clears); a ring nobody judged dissolves
    cold as a Miss.  Perfect and Good count hits; a force hit and a Miss
    count attempts only.  The clock is the shell's integer phase
    (``phase / 60``): no wall time enters anywhere.
    """

    name = "motion"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._game = RingsGame()
        self._board = PixelCanvas(palette=_RING_PALETTE)
        self._geom = (160, 96)

    def enter(self) -> None:
        super().enter()
        self._game.reset()

    # -- public state ------------------------------------------------------

    @property
    def score(self) -> int:
        return self._game.score

    @property
    def combo(self) -> int:
        return self._game.combo

    @property
    def hits(self) -> int:
        return self._game.hits

    @property
    def attempts(self) -> int:
        return self._game.attempts

    @property
    def rings(self):
        return self._game.rings

    # -- input -------------------------------------------------------------

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "space":
            self._game.judge(self._game.now)
            return None
        if key == "escape":
            return "menu"
        if key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        self._game.judge(self._game.now)
        return None

    def tick(self, phase: int) -> str | None:
        self._game.sync(phase, *self._geom)
        return None

    # -- rendering ---------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        board_h = max(4, height - 2)  # HUD and hint own one row each
        board_w = max(12, min(80, width))
        self._fit_board(board_w, board_h)
        self._game.sync(phase, *self._geom)
        canvas = self._board
        canvas.clear()
        paint(canvas, self._game.rings, phase / TICK_HZ, phase)
        board = list(canvas.render(Constraints(width=board_w)))
        rows: list[Line] = [self._hud(board_w), *board]
        if board_w != width:
            pad = Line((Segment(" " * max(0, (width - board_w) // 2)),))
            rows = [pad + row for row in rows]
        rows.append(self._hint(width))
        rows = rows[:height]
        rows.extend(Line() for _ in range(height - len(rows)))
        return Surface.of(rows, width)

    def _fit_board(self, width: int, height: int) -> None:
        """Sync the board to the pane; a resize starts a fresh game."""
        if (width, height) != (self._board.width, self._board.height):
            self._board.resize(width, height)
            self._game.reset()
        self._geom = (self._board.pixel_width, self._board.pixel_height)

    def _hud(self, width: int) -> Line:
        """One row: rings combo/score/hits on the left, the board on the right."""
        left = (
            f"rings  combo {self.combo:02d}  score {self.score:04d}"
            f"  hits {self.hits}/{self.attempts}"
        )
        return ends(
            width,
            left,
            "pixel board",
            self.theme.text.muted,
            self.theme.content.accent,
        )

    def _hint(self, width: int) -> Line:
        """The key hint of the rings board, one clipped row."""
        return fit(
            Line.from_text(
                "space judge \u00b7 click judge \u00b7 esc menu \u00b7 q quit",
                self.theme.text.faint,
            ),
            width,
        )

    def __repr__(self) -> str:
        return (
            f"MotionScene(score={self.score}, combo={self.combo}, "
            f"rings={len(self._game.rings)})"
        )
