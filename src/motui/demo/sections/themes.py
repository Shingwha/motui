"""Skin Lab: switch the palette of the entire showcase, not a local sample."""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.style import Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Button, Checkbox, Column, Input, Panel, RadioGroup, Row, Slider, Tabs
from ..common import LinesView, pad_rows
from ..palettes import DEMO_THEMES
from ..scene import Scene

__all__ = ["ThemesScene"]

_CLIP = WrapMode.CLIP


def _role(label: str, sample: str, style: Style, faint: Style) -> Line:
    return Line((Segment(f"{label:<10}", faint), Segment(sample, style)))


def _roles(theme: Theme) -> list[Line]:
    return [
        _role("base", "signal text", theme.text.base, theme.text.faint),
        _role("muted", "telemetry annotation", theme.text.muted, theme.text.faint),
        _role("accent", "active experiment", theme.content.accent, theme.text.faint),
        _role("secondary", "inline code", theme.content.inline_code, theme.text.faint),
        _role("success", "✓ link acquired", theme.status.success, theme.text.faint),
        _role("warning", "! interference", theme.status.warning, theme.text.faint),
        _role("danger", "x signal lost", theme.status.danger, theme.text.faint),
    ]


class ThemesScene(Scene):
    name = "themes"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self.index = 0
        self.compare = False
        self.tabs = Tabs([item.name for item in DEMO_THEMES], theme=theme)
        self.input = Input("DSN-07", placeholder="callsign", theme=theme)
        self.checkbox = Checkbox("lock uplink", checked=True, theme=theme)
        self.radio = RadioGroup(["low", "mid", "high"], index=1, theme=theme)
        self.slider = Slider(7, maximum=10, theme=theme)
        self.button = Button("acquire signal", theme=theme)
        self._focus = 0
        self._targets = (self.input, self.checkbox, self.radio, self.slider, self.button)
        self._set_focus(0)
        self._roles = LinesView(theme, _roles(theme))
        controls = Column(self._targets, gap=1)
        self._body = Row(
            [
                Panel(self._roles, title="SEMANTIC ROLES", theme=theme),
                Panel(controls, title="LIVE CONTROLS", theme=theme),
            ],
            widths=[44, None],
            gap=1,
        )

    def enter(self) -> None:
        super().enter()
        self.compare = False
        self._focus = 0
        self._set_focus(0)

    def _set_focus(self, index: int) -> None:
        self._focus = index % len(self._targets)
        for position, target in enumerate(self._targets):
            target.focused = position == self._focus

    def _compare_rows(self, width: int) -> list[Line]:
        panels = []
        for item in DEMO_THEMES:
            view = LinesView(item.theme, _roles(item.theme)[:5])
            panels.append(Panel(view, title=item.name, theme=item.theme))
        each = max(12, (width - 4) // len(panels))
        row = Row(panels, widths=[each] * len(panels), gap=1)
        return list(row.render(Constraints(width=width)))

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width, height = c.width, c.max_height or 24
        self.tabs.select(self.index)
        strip = next(iter(self.tabs.render(Constraints(width=width))))
        spec = DEMO_THEMES[self.index]
        body_h = max(8, height - 7)
        if self.compare:
            body = self._compare_rows(width)
        else:
            self._body.widths = [min(44, max(28, width * 44 // 100)), None]
            body = list(self._body.render(Constraints(width=width)))
        rows = [
            Line.from_text("SKIN LAB / GLOBAL THEME", self.theme.content.accent),
            Line.from_text(
                "Applied to every scene, every control and every pixel layer.",
                self.theme.text.faint,
            ),
            strip.clip(_CLIP, width),
            *body[:body_h],
            Line(),
            Line.from_text(f"{spec.label} · {spec.note}", self.theme.text.muted),
            Line.from_text(
                "1-5 apply · arrows/tab cycle · c compare · ctrl+t anywhere · esc lab",
                self.theme.text.faint,
            ),
        ]
        return Surface.of([row.clip(_CLIP, width) for row in pad_rows(rows, height)], width)

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "escape":
            return "menu"
        if key == "q":
            return "quit"
        if key == "c":
            self.compare = not self.compare
        elif key == "left":
            return "theme-prev"
        elif key in ("right", "tab"):
            return "theme-next"
        elif key in ("1", "2", "3", "4", "5"):
            return f"theme:{int(key) - 1}"
        elif key in ("down", "up", "s-tab", "backtab"):
            step = -1 if key in ("up", "s-tab", "backtab") else 1
            self._set_focus(self._focus + step)
        else:
            self._targets[self._focus].on_key(event)
        return None

    def on_click(self, pos: Pos) -> str | None:
        if pos.y == 2 and self.tabs.on_click(Pos(x=pos.x, y=0)):
            return f"theme:{self.tabs.index}"
        return None
