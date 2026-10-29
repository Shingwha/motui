"""The Signal Lab opening on one continuous visual timeline."""

from __future__ import annotations

import math
import random

from ....kernel.cell import Line, Segment, Surface
from ....kernel.events import KeyEvent
from ....kernel.geom import Pos
from ....kernel.layout import Constraints
from ....kernel.text import WrapMode
from ....pixel import PixelPalette
from ....widgets import PixelCanvas
from ...common import center
from ...palettes import style_rgb
from ...scene import Scene
from ...version import DEMO_VERSION
from .effects import (
    ACT_TICKS,
    EFFECTS,
    blend,
    paint_background,
    paint_wordmark,
)
from .wordmark import pick_scale

__all__ = ["SplashScene"]


def _mix(
    first: tuple[int, int, int], second: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    return tuple(
        round(a + (b - a) * amount) for a, b in zip(first, second, strict=True)
    )


class SplashScene(Scene):
    name = "splash"

    def __init__(self, theme, *, seed: int | None = 0) -> None:
        super().__init__(theme)
        self._seed = seed
        self._epoch = 0 if seed is None else seed
        self._remix = 0
        self._pending_remix = 0
        self._remix_at: int | None = None
        self._remix_applied: int | None = None
        self._remix_previous: tuple[str, ...] | None = None
        self._accent = style_rgb(theme.content.accent, (77, 232, 210))
        self._secondary = style_rgb(theme.content.inline_code, (183, 160, 255))
        self._success = style_rgb(theme.status.success, (139, 234, 154))
        self._danger = style_rgb(theme.status.danger, (255, 107, 139))
        self._muted = style_rgb(theme.text.muted, (138, 168, 181))
        self._faint = style_rgb(theme.text.faint, (82, 108, 124))
        self._canvas = PixelCanvas(palette=self._palette("deep", "deep", 0, 1.0))

    def enter(self) -> None:
        super().enter()
        self._epoch = random.Random().randrange(2**32) if self._seed is None else self._seed
        self._remix = 0
        self._pending_remix = 0
        self._remix_at = None
        self._remix_applied = None
        self._remix_previous = None

    def _bag(self, cycle: int) -> list[str]:
        rng = random.Random(self._epoch + self._remix * 1009 + cycle * 97)
        bag = list(EFFECTS)
        rng.shuffle(bag)
        if cycle == 0 and self._remix == 0:
            bag.remove("deep")
            bag.insert(0, "deep")
        if cycle > 0:
            previous = self._bag(cycle - 1)
            if bag[0] == previous[-1]:
                bag[0], bag[1] = bag[1], bag[0]
        return bag

    def effects(self, phase: int) -> tuple[str, ...]:
        act = max(0, phase) // ACT_TICKS
        cycle, position = divmod(act, len(EFFECTS))
        main = self._bag(cycle)[position]
        rng = random.Random((self._epoch ^ (act * 0x9E3779B1)) + self._remix * 557)
        choices = {
            "deep": ("wave", "comet"),
            "ion": ("wave", "comet"),
            "phosphor": ("scan", "wave"),
            "gravity": ("wave", "comet"),
            "warp": ("wave", "comet"),
        }
        return main, rng.choice(choices[main])

    def previous_effects(self, phase: int) -> tuple[str, ...]:
        act = max(0, phase) // ACT_TICKS
        if self._remix_previous is not None and act == self._remix_applied // ACT_TICKS:
            return self._remix_previous
        if act == 0:
            return self.effects(phase)
        return self.effects((act - 1) * ACT_TICKS)

    def style_name(self, phase: int) -> str:
        main, auxiliary = self.effects(phase)
        names = {"deep": "DEEP FIELD", "ion": "ION CURRENT", "phosphor": "PHOSPHOR"}
        label = names.get(main, main.upper())
        return f"{label} + {auxiliary.upper()} / 86 STARS"

    def remix(self) -> None:
        self._pending_remix += 1
        if self._remix_at is None:
            self._remix_at = (max(0, self._phase) // ACT_TICKS + 1) * ACT_TICKS

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        if self._remix_at is not None and phase >= self._remix_at:
            self._remix_previous = self.effects(self._remix_at - 1)
            self._remix += self._pending_remix
            self._pending_remix = 0
            self._remix_applied = self._remix_at
            self._remix_at = None
        if self._remix_applied is not None and phase >= self._remix_applied + ACT_TICKS:
            self._remix_previous = None
            self._remix_applied = None
        return None

    def _ramp(self, main: str, phase: int):
        if main == "ion":
            amount = 0.5 + 0.5 * math.sin(phase * 0.012)
            return (
                _mix(self._accent, self._secondary, amount),
                _mix(self._secondary, self._accent, amount),
            )
        if main == "phosphor":
            return self._success, self._accent
        if main == "gravity":
            return self._secondary, self._success
        if main == "warp":
            return self._secondary, self._accent
        return self._accent, self._secondary

    def _palette(
        self, main: str, previous: str, phase: int, weight: float
    ) -> PixelPalette:
        old_start, old_end = self._ramp(previous, phase)
        new_start, new_end = self._ramp(main, phase)
        start = _mix(old_start, new_start, weight)
        end = _mix(old_end, new_end, weight)
        return PixelPalette(
            slots={
                **{
                    index + 1: (
                        _mix(start, end, index / 11),
                        _mix(start, end, index / 11 * 0.35),
                    )
                    for index in range(12)
                },
                13: ((240, 253, 255), (120, 140, 155)),
                14: (self._danger, tuple(round(value * 0.4) for value in self._danger)),
                15: (self._success, tuple(round(value * 0.4) for value in self._success)),
                16: (self._muted, self._faint),
            }
        )

    def _header(self, width: int, phase: int) -> Line:
        left = "MOTUI // SIGNAL LAB"
        right = f"ACT {max(0, phase) // ACT_TICKS + 1:02d} · {DEMO_VERSION}"
        gap = max(1, width - len(left) - len(right) - 2)
        return Line(
            (
                Segment(" "),
                Segment(left, self.theme.content.accent),
                Segment(" " * gap),
                Segment(right, self.theme.text.faint),
                Segment(" "),
            )
        ).clip(WrapMode.CLIP, width)

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        canvas_w = max(12, min(88, width - 2))
        canvas_h = max(5, height - 8)
        sx, sy = pick_scale(canvas_w * 2, canvas_h * 4)
        self._canvas.resize(canvas_w, canvas_h)
        self._canvas.clear()
        act = max(0, phase) // ACT_TICKS
        local = max(0, phase) % ACT_TICKS
        effects = self.effects(phase)
        previous = self.previous_effects(phase)
        weight = blend(local) if act else 1.0
        self._canvas.palette = self._palette(effects[0], previous[0], phase, weight)
        paint_background(self._canvas, effects, previous, phase, local, sx, sy)
        paint_wordmark(self._canvas, phase, sx, sy, effects[0], previous[0], act)
        pad = max(0, (width - canvas_w) // 2)
        prefix = Line((Segment(" " * pad),)) if pad else Line()
        mark = [
            prefix + row
            for row in self._canvas.render(Constraints(width=canvas_w, max_height=canvas_h))
        ]
        tagline = "GIVE THE TERMINAL A PULSE" if phase >= 90 else "ASSEMBLING THE SIGNAL"
        effect_line = self.style_name(phase)
        if self._pending_remix:
            effect_line = "REMIX QUEUED / NEXT CONTINUOUS TRANSITION"
        content = [
            self._header(width, phase),
            *mark,
            Line(),
            *center(width, [Line.from_text(tagline, self.theme.text.muted)]),
            Line(),
            *center(width, [Line.from_text(effect_line, self.theme.content.accent)]),
            Line(),
            *center(
                width,
                [
                    Line.from_text(
                        "enter launch · space remix · any other key skip",
                        self.theme.text.faint,
                    )
                ],
            ),
        ]
        top = max(0, (height - len(content)) // 2)
        rows = [Line() for _ in range(top)] + content
        return Surface.of(rows[:height], width)

    def on_key(self, event: KeyEvent) -> str | None:
        if event.key == "space":
            self.remix()
            return None
        if event.key == "q":
            return "quit"
        return "menu"

    def on_click(self, pos: Pos) -> str | None:
        return "menu"
