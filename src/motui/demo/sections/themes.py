"""The themes section: one sample layout, re-skinned live.

Every widget resolves its role tokens from its theme at render time, so
the section keeps one sample -- role-token lines beside real controls --
and rebuilds it under whichever theme the picker points at: the whole
frame, chrome included, re-skins in one switch.  Four themes ride the
picker: the two shipped palettes, the flattened dark, and a sepia theme
authored right here through :class:`ColorPalette` to show the derivation
route (``Theme.from_palette`` is a pure function of the creation colors).

The switch is section-local, on purpose and by constraint.  A scene
cannot reach the shell's own chrome (the status line keeps the boot
theme), and a :class:`Theme` is a frozen value with no global registry
behind it -- the run-time mechanism a widget documents ("assign a new
theme, the mounted widget repaints") works per widget, while widgets
like ``Text`` hold explicit style tokens captured from a theme object.
Rebuilding the sample tree under the chosen theme is the one mechanism
with no stale-token corner, so that is the one this section drives.
``c`` answers the same question statically: all four themes' role
tokens, side by side.
"""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.style import Color, Style
from ...kernel.text import WrapMode
from ...kernel.theme import ColorPalette, Theme
from ...widgets import (
    Button,
    Checkbox,
    Column,
    Input,
    Panel,
    RadioGroup,
    Row,
    Slider,
    Tabs,
    Widget,
)

__all__ = ["ThemesScene"]

#: Single-row clip for the composed rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: The sepia creation palette: warm paper tones authored in this file,
#: every field naming its truecolor value and its 16-color fallback.
_SEPIA_PALETTE = ColorPalette(
    ink=Style(fg=Color("#3d2f22")),
    muted=Style(fg=Color("#7d6a52", ansi="bright_black")),
    faint=Style(fg=Color("#a08a6e", ansi="bright_black")),
    line=Style(fg=Color("#c4ad8e", ansi="bright_black")),
    surface_raised=Style(bg=Color("#efe5d0", ansi="bright_white")),
    surface_hover=Style(bg=Color("#e6d9bf", ansi="bright_white")),
    surface_active=Style(bg=Color("#dccbaa", ansi="bright_white")),
    surface_inactive=Style(bg=Color("#f3ecdc", ansi="bright_white")),
    accent=Style(fg=Color("#9a4f1e", ansi="yellow")),
    success=Style(fg=Color("#5f7024", ansi="green")),
    warning=Style(fg=Color("#b07d1e", ansi="bright_yellow")),
    danger=Style(fg=Color("#a13030", ansi="red")),
    heading=Style(fg=Color("#9a4f1e", ansi="yellow")),
    link=Style(fg=Color("#9a4f1e", ansi="yellow"), underline=True),
    inline_code=Style(fg=Color("#6d4b8c", ansi="magenta")),
    marker=Style(fg=Color("#7d6a52", ansi="bright_black")),
)

#: The picker's pages: ``(name, theme, provenance)`` in tour order.
_PAGES: tuple[tuple[str, Theme, str], ...] = (
    ("dark", Theme.dark(), "Theme.dark() \u00b7 the DARK_PALETTE defaults"),
    ("light", Theme.light(), "Theme.light() \u00b7 every LIGHT_PALETTE token"),
    ("flat", Theme.flat(), "Theme.flat() \u00b7 dark, surfaces flattened"),
    (
        "sepia",
        Theme.from_palette(_SEPIA_PALETTE),
        "Theme.from_palette(_SEPIA_PALETTE) \u00b7 authored in this file",
    ),
)


def _role(label: str, sample: str, style: Style, faint: Style, width: int) -> Line:
    """One token line: a faint role name, then the sample wearing the token."""
    return Line((Segment(f"{label:<{width}}", faint), Segment(sample, style)))


def _role_lines(theme: Theme, *, compact: bool) -> list[Line]:
    """The role-token sampler for ``theme``; the compact form fits a quarter pane."""
    faint = theme.text.faint
    label_w = 7 if compact else 8
    if compact:
        marks = Line(
            (
                Segment(f" {mark} ", style)
                for mark, style in (
                    ("\u2713", theme.status.success),
                    ("!", theme.status.warning),
                    ("\u00d7", theme.status.danger),
                    ("i", theme.status.info),
                )
            )
        )
        return [
            _role("base", "the fox", theme.text.base, faint, label_w),
            _role("muted", "quieter", theme.text.muted, faint, label_w),
            _role("faint", "gone", theme.text.faint, faint, label_w),
            Line((Segment("status", faint),)) + marks,
            _role("accent", "accent\u00b7link", theme.content.accent, faint, label_w),
        ]
    return [
        _role("base", "the quick brown fox jumps", theme.text.base, faint, label_w),
        _role("muted", "a quieter annotation", theme.text.muted, faint, label_w),
        _role("faint", "almost gone", theme.text.faint, faint, label_w),
        _role("success", "\u2713 all clear", theme.status.success, faint, label_w),
        _role("warning", "! attention", theme.status.warning, faint, label_w),
        _role("danger", "\u00d7 stop", theme.status.danger, faint, label_w),
        _role("accent", "content.accent", theme.content.accent, faint, label_w),
        _role("link", "a link token", theme.content.link, faint, label_w),
        _role("code", "inline_code token", theme.content.inline_code, faint, label_w),
    ]


class _LinesView(Widget):
    """A render-only block of pre-built lines: the role sampler's panel body."""

    __slots__ = ("lines",)

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme, None)
        self.lines: list[Line] = []

    def render(self, c: Constraints) -> Surface:
        rows = [line.clip(_CLIP, c.width) for line in self.lines]
        return Surface.of(rows, c.width)


class ThemesScene:
    """The themes section: one sample, every control re-skinned by the picker.

    The tab strip at the top is the picker (a real :class:`Tabs`); the
    body is the same sample layout under the selected theme -- the role
    tokens on the left, real controls on the right -- and the provenance
    row names where the theme was derived from.  ``1``-``4`` and the
    arrows switch, ``c`` toggles the four-up compare grid, a click on the
    strip picks too.  Every switch rebuilds the sample tree under the
    chosen theme; between switches the frame is a pure function of the
    state, so a driven replay lands byte for byte.
    """

    name = "themes"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._index = 0
        self._compare = False
        self._mount()

    # -- the sample ---------------------------------------------------------------

    @property
    def _current(self) -> Theme:
        """The theme the picker points at right now."""
        return _PAGES[self._index][1]

    def _mount(self) -> None:
        """Rebuild the whole sample under the selected theme."""
        current = self._current
        self.tabs = Tabs([name for name, _theme, _note in _PAGES], theme=current)
        self.tabs.select(self._index)
        self.input = Input("Ada Lovelace", placeholder="type a name\u2026", theme=current)
        self.checkbox = Checkbox("ship notifications", theme=current)
        self.radio = RadioGroup(["compact", "cozy", "roomy"], index=1, theme=current)
        self.slider = Slider(6, maximum=10, theme=current)
        self.button = Button("save to disk", theme=current)
        controls = Column(
            [self.input, self.checkbox, self.radio, self.slider, self.button],
            gap=1,
        )
        self._roles = _LinesView(current)
        self._roles.lines = _role_lines(current, compact=False)
        self._roles_panel = Panel(self._roles, title="role tokens", theme=current)
        self._controls_panel = Panel(controls, title="controls", theme=current)
        self._body = Row(
            [self._roles_panel, self._controls_panel], widths=[46, None], gap=1
        )

    def _switch(self, index: int) -> None:
        """Point the picker at ``index`` and remount the sample under it."""
        self._index = index % len(_PAGES)
        self._mount()

    # -- rendering ----------------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        """Heading, picker strip, the sample (or the compare grid), provenance."""
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        current = self._current
        strip = self.tabs.render(Constraints(width=width))
        rows: list[Line] = [self._heading(), next(iter(strip)).clip(_CLIP, width)]
        body_h = max(3, height - 4)  # heading, strip, provenance and hint own rows
        if self._compare:
            rows.extend(self._compare_rows(width)[:body_h])
        else:
            self._body.widths = [min(46, max(28, width * 46 // 100)), None]
            body_rows = list(self._body.render(Constraints(width=width)))
            del body_rows[body_h:]
            rows.extend(body_rows)
        rows.append(self._provenance())
        rows.append(self._hint())
        return Surface.of(
            [row.clip(_CLIP, width) for row in rows[:height]], width
        )

    def _compare_rows(self, width: int) -> list[Line]:
        """All four themes' compact samplers, one quarter pane each."""
        panels = []
        for name, theme, _note in _PAGES:
            view = _LinesView(theme)
            view.lines = _role_lines(theme, compact=True)
            panels.append(Panel(view, title=name, theme=theme))
        each = max(8, (width - 3) // 4)
        quad = Row(panels, widths=[each, each, each, each], gap=1)
        return list(quad.render(Constraints(width=width)))

    def _heading(self) -> Line:
        """The one-row title, wearing the selected theme's accent."""
        return Line(
            (
                Segment("Themes", self._current.content.accent),
                Segment(
                    " \u00b7 one sample, re-skinned by the picker",
                    self._current.text.faint,
                ),
            )
        )

    def _provenance(self) -> Line:
        """Where the selected theme came from, under the sample."""
        name, _theme, note = _PAGES[self._index]
        return Line(
            (
                Segment(name, self._current.content.accent),
                Segment(f" \u00b7 {note}", self._current.text.faint),
            )
        )

    def _hint(self) -> Line:
        """The one-row key hint bar."""
        return Line.from_text(
            "1-4 theme \u00b7 \u2190/\u2192 cycle \u00b7 c compare \u00b7 click tabs "
            "\u00b7 esc menu \u00b7 q quit",
            self._current.text.faint,
        )

    # -- behaviour ----------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "escape":
            return "menu"
        if key == "q":
            return "quit"
        if key == "c":
            self._compare = not self._compare
        elif key == "left":
            self._switch(self._index - 1)
        elif key == "right":
            self._switch(self._index + 1)
        elif key in ("1", "2", "3", "4") and int(key) <= len(_PAGES):
            self._switch(int(key) - 1)
        return None

    def on_click(self, pos: Pos) -> str | None:
        """A click on the strip's own row picks the theme under the pointer."""
        if pos.y == 1:
            self.tabs.on_click(Pos(x=pos.x, y=0))
            if self.tabs.index != self._index:
                self._switch(self.tabs.index)
        return None
