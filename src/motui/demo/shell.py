"""The Signal Lab shell: scenes, global themes and deterministic transitions."""

from __future__ import annotations

import random
from collections.abc import Callable

from ..kernel.cell import Line, Segment, Surface, cut_line
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets import Panel, Text
from ..widgets.base import Widget
from .palettes import DEMO_THEMES
from .registry import JUMPABLE, SCENES, SPEC_BY_NAME, build_scenes
from .scene import START_PHASE

__all__ = ["START_PHASE", "Showcase"]

_CLIP = WrapMode.CLIP
_TRANSITION_TICKS = 10
_TRANSITIONS = ("slice", "scan")


class Showcase(Widget):
    focusable = True
    clickable = True

    __slots__ = (
        "_help",
        "_previous",
        "_previous_phase",
        "_rng",
        "_scenes",
        "_seed",
        "_transition",
        "motion",
        "on_quit",
        "phase",
        "scene",
        "status_line",
        "status_note",
        "theme_index",
    )

    on_quit: Callable[[], None] | None

    def __init__(
        self,
        scene: str = "splash",
        theme: Theme | None = None,
        *,
        seed: int | None = 0,
        status_line: bool = False,
        phase: int = START_PHASE,
    ) -> None:
        if scene not in SPEC_BY_NAME:
            raise ValueError(f"unknown scene {scene!r}: expected one of {SCENES}")
        resolved = DEMO_THEMES[0].theme if theme is None else theme
        super().__init__(resolved)
        self._rng = random.Random(seed)
        self._seed = seed
        self.theme_index = 0
        self._scenes = build_scenes(resolved, seed)
        self.scene = scene
        self.phase = phase
        self._previous: str | None = None
        self._previous_phase: int | None = None
        self._transition = "slice"
        self._help = False
        self.motion = True
        self.status_line = status_line
        self.status_note = "--"
        self.on_quit = None
        self._scenes[scene].enter()

    @property
    def spec(self):
        return SPEC_BY_NAME[self.scene]

    @property
    def theme_spec(self):
        return DEMO_THEMES[self.theme_index]

    @property
    def help_open(self) -> bool:
        return self._help

    def toggle_help(self) -> None:
        self._help = not self._help
        self.touch()

    def toggle_motion(self) -> None:
        self.motion = not self.motion
        self.touch()

    def set_theme(self, index: int) -> None:
        menu_index = self._scenes["menu"].index
        self.theme_index = index % len(DEMO_THEMES)
        self.theme = self.theme_spec.theme
        self._scenes = build_scenes(self.theme, self._seed)
        self._scenes["menu"].index = menu_index
        themes = self._scenes.get("themes")
        if themes is not None:
            themes.index = self.theme_index
        self._scenes[self.scene].enter()
        self._previous = None
        self._previous_phase = None
        self.touch()

    def cycle_theme(self, step: int = 1) -> None:
        self.set_theme(self.theme_index + step)

    def switch(self, name: str, *, phase: int = START_PHASE) -> None:
        if name not in SPEC_BY_NAME:
            raise ValueError(f"unknown scene {name!r}: expected one of {SCENES}")
        if name != self.scene and self.motion:
            self._previous = self.scene
            self._previous_phase = self.phase
            self._transition = self._rng.choice(_TRANSITIONS)
        else:
            self._previous = None
            self._previous_phase = None
        self._scenes[name].enter()
        self.scene = name
        self.phase = phase
        self._help = False
        self.touch()

    def seek(self, phase: int) -> None:
        if phase < self.phase:
            self._scenes[self.scene].enter()
            self.phase = START_PHASE
            self._previous = None
            self._previous_phase = None
        self.phase = phase
        self._help = False
        self.touch()

    def tick(self) -> str | None:
        if self._help or not self.motion:
            return None
        self.phase += 1
        if self._previous is not None and self.phase >= _TRANSITION_TICKS:
            self._previous = None
            self._previous_phase = None
        target = self._scenes[self.scene].tick(self.phase)
        if target is not None:
            self._route(target)
        else:
            self.touch()
        return target

    def on_key(self, event: KeyEvent) -> bool:
        key = event.key
        if key in ("f1", "?"):
            self.toggle_help()
            return True
        if key == "f2":
            self.toggle_motion()
            return True
        if key == "ctrl+t":
            self.cycle_theme()
            return True
        if self._help:
            if key == "escape":
                self.toggle_help()
            return True
        target = self._scenes[self.scene].on_key(event)
        self._route(target)
        return True

    def on_click(self, pos: Pos) -> bool:
        if self._help:
            self.toggle_help()
            return True
        target = self._scenes[self.scene].on_click(pos)
        self._route(target)
        return True

    def _route(self, target: str | None) -> None:
        if target is None:
            return
        if target == "quit":
            if self.on_quit is not None:
                self.on_quit()
        elif target == "theme-next":
            self.cycle_theme()
        elif target == "theme-prev":
            self.cycle_theme(-1)
        elif target.startswith("theme:"):
            self.set_theme(int(target.split(":", 1)[1]))
        elif target == "next":
            index = JUMPABLE.index(self.scene)
            self.switch(JUMPABLE[(index + 1) % len(JUMPABLE)])
        else:
            self.switch(target)

    def render(self, c: Constraints) -> Surface:
        surface = self._scenes[self.scene].render(c, self.phase)
        if self._previous is not None and self._previous_phase is not None:
            previous = self._scenes[self._previous].render(c, self._previous_phase)
            rows = self._transition_rows(surface, previous, c.width)
        else:
            rows = list(surface)
        budget = c.max_height
        if budget is not None:
            rows = rows[:budget]
            rows.extend(Line() for _ in range(budget - len(rows)))
        if self.status_line and rows:
            rows[-1] = self._status(c.width)
        if self._help:
            rows = self._help_overlay(rows, c.width)
        return Surface.of(rows, c.width)

    def _transition_rows(
        self, current: Surface, previous: Surface, width: int
    ) -> list[Line]:
        progress = min(1.0, (self.phase + 1) / _TRANSITION_TICKS)
        new_rows = list(current)
        old_rows = list(previous)
        rows: list[Line] = []
        for y, (new, old) in enumerate(zip(new_rows, old_rows, strict=False)):
            if self._transition == "slice":
                offset = (y % 5) * width // 25
                cols = max(0, min(width, round(width * progress) - offset))
                if y % 2:
                    rows.append(cut_line(old, 0, width - cols) + cut_line(new, width - cols, width))
                else:
                    rows.append(cut_line(new, 0, cols) + cut_line(old, cols, width))
            else:
                local = max(0.0, min(1.0, progress * 1.5 - (y % 4) * 0.12))
                cols = round(width * local)
                if y % 2:
                    rows.append(
                        cut_line(old, 0, width - cols)
                        + cut_line(new, width - cols, width)
                    )
                else:
                    rows.append(cut_line(new, 0, cols) + cut_line(old, cols, width))
        return rows

    def _status(self, width: int) -> Line:
        left = f"SIGNAL LAB / {self.spec.title}"
        mode = "LIVE" if self.motion else "CALM"
        right = f"{self.theme_spec.label} · {mode} · {self.status_note}"
        gap = max(1, width - len(left) - len(right) - 2)
        return Line(
            (
                Segment(" "),
                Segment(left, self.theme.content.accent),
                Segment(" " * gap),
                Segment(right, self.theme.text.faint),
                Segment(" "),
            )
        ).clip(_CLIP, width)

    def _help_overlay(self, rows: list[Line], width: int) -> list[Line]:
        spec = self.spec
        lines = [
            f"{spec.title} — {spec.blurb}",
            "",
            "global  F1/? help · F2 calm · ctrl+t theme · ctrl+p commands",
            "        esc back · q quit (outside text fields)",
            "",
        ]
        lines.extend(f"{key:<18} {action}" for key, action in spec.keys)
        panel_w = min(76, max(24, width - 6))
        panel = Panel(
            Text("\n".join(lines), theme=self.theme),
            title="SIGNAL LAB / field manual",
            theme=self.theme,
        )
        panel_rows = list(
            panel.render(Constraints(width=panel_w, max_height=max(1, len(rows) - 2)))
        )
        left = max(0, (width - panel_w) // 2)
        top = max(0, (len(rows) - len(panel_rows)) // 2)
        prefix = Line((Segment(" " * left),))
        for offset, row in enumerate(panel_rows):
            y = top + offset
            if 0 <= y < len(rows):
                rows[y] = (prefix + row).fill(width)
        return rows

    def __repr__(self) -> str:
        return f"Showcase(scene={self.scene!r}, phase={self.phase})"
