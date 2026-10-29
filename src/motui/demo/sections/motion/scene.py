"""Pulse: a keyboard- and mouse-playable sub-cell rhythm instrument."""

from __future__ import annotations

from ....kernel.cell import Line, Segment, Surface
from ....kernel.events import KeyEvent
from ....kernel.geom import Pos
from ....kernel.layout import Constraints
from ....kernel.theme import Theme
from ....widgets import PixelCanvas
from ...common import ends, fit
from ...palettes import pixel_palette
from ...scene import TICK_HZ, Scene
from .paint import paint
from .rings import POINTS, Ring, RingsGame

__all__ = ["MotionScene"]


class MotionScene(Scene):
    name = "motion"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._game = RingsGame()
        self._board = PixelCanvas(palette=pixel_palette(theme))
        self._geom = (160, 96)
        self._paused = False
        self._pause_at = 0
        self._offset = 0
        self._feedback: tuple[Ring, int] | None = None

    def enter(self) -> None:
        super().enter()
        self._game.reset()
        self._paused = False
        self._pause_at = 0
        self._offset = 0
        self._feedback = None

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

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def verdict(self) -> str | None:
        if self._feedback is None:
            return None
        return self._feedback[0].verdict

    def _judge(self) -> None:
        if self._paused:
            return
        ring = self._game.judge(self._game.now)
        if ring is not None:
            self._feedback = (ring, self._game.phase)

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "space":
            self._judge()
        elif key == "p":
            if self._paused:
                self._offset += self._phase - self._pause_at
            else:
                self._pause_at = self._phase
            self._paused = not self._paused
        elif key == "r":
            self._offset = self._phase
            self._pause_at = self._phase
            self._game.reset()
            self._feedback = None
        elif key == "escape":
            return "menu"
        elif key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        self._judge()
        return None

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        if not self._paused:
            self._game.sync(phase - self._offset, *self._geom)
        return None

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        board_h = max(4, height - 2)
        board_w = max(12, min(88, width))
        self._fit_board(board_w, board_h)
        effective = self._pause_at if self._paused else phase
        effective -= self._offset
        self._game.sync(effective, *self._geom)
        canvas = self._board
        canvas.clear()
        paint(canvas, self._game.rings, effective / TICK_HZ, effective)
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
        if (width, height) != (self._board.width, self._board.height):
            self._board.resize(width, height)
            self._game.reset()
            self._feedback = None
        self._geom = (self._board.pixel_width, self._board.pixel_height)

    def _hud(self, width: int) -> Line:
        left = (
            f"PULSE  combo {self.combo:02d}  score {self.score:04d}"
            f"  hits {self.hits}/{self.attempts}"
        )
        right = "PAUSED" if self._paused else "SUB-CELL / BRAILLE"
        style = self.theme.content.accent
        if not self._paused:
            stage = self._game.stage
            if stage == "close":
                right = "READY"
            elif stage == "good":
                right = "HIT"
            elif stage == "perfect":
                right, style = "PERFECT", self.theme.status.success
        if self._feedback is not None:
            ring, at = self._feedback
            if self._game.phase - at <= 60 and ring.verdict is not None:
                label = "CLOSE" if ring.verdict == "force" else ring.verdict.upper()
                right = f"{label} +{POINTS[ring.verdict]}"
                style = (
                    self.theme.status.warning
                    if ring.verdict == "force"
                    else self.theme.status.success
                )
        return ends(width, left, right, self.theme.text.muted, style)

    def _hint(self, width: int) -> Line:
        return fit(
            Line.from_text(
                "space judge · p pause · r reset · click judge · esc lab · q quit",
                self.theme.text.faint,
            ),
            width,
        )

    def __repr__(self) -> str:
        return f"MotionScene(score={self.score}, combo={self.combo}, rings={len(self.rings)})"
