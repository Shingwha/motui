"""The components section: live widgets beside the code that draws them.

One tab strip groups the console into ``console``, ``probes`` and ``actions``
pages, and every page splits in two: real controls on the left,
the highlighted Python that built them on the right.  The snippet is a live
echo, not a picture: the ``Input`` line re-renders with the text actually
typed, the ``RadioGroup`` and ``Slider`` lines re-render with the values
actually picked, and the focused control's lines are emphasised -- the point
being "this is all the code".

Buttons land toasts (a level glyph with a countdown, counted from the phase
the toast was issued at), the confirm button opens a real :class:`Dialog` as
a centred overlay, and the table sorts under the ``s`` key.  ``tab`` cycles
the focus across the page's controls, ``escape`` closes the modal or returns
to the menu, ``q`` quits -- except while the text field owns the focus.
"""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface, cut_line
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.glyphs import GLYPHS, seat
from ...kernel.layout import Constraints
from ...kernel.style import Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import (
    Button,
    Checkbox,
    Column,
    Dialog,
    Input,
    Panel,
    RadioGroup,
    Row,
    Slider,
    Table,
    Tabs,
    Text,
    Widget,
)
from ...widgets.syntax import RegexHighlighter
from ..common import LinesView
from ..scene import Scene

__all__ = ["ComponentsScene"]

_CLIP = WrapMode.CLIP

#: The emphasis merged onto the focused control's snippet lines.
_HOT = Style(bold=True)

#: Toasts remain readable for three seconds at the shell's 60 Hz.
_TOAST_TICKS = 180

_PAGES = ("console", "probes", "actions")

_PROBES: tuple[tuple[str, str, str], ...] = (
    ("andromeda", "42 ms", "0.99"),
    ("borealis", "68 ms", "0.94"),
    ("cygnus", "31 ms", "0.97"),
    ("draco", "91 ms", "0.88"),
    ("europa", "55 ms", "0.96"),
)


class ComponentsScene(Scene):
    """The components playground: controls on the left, their code on the right.

    The tab strip, every control of the active page and the modal dialog are
    real widgets; the scene only routes.  ``tab``/``s-tab`` cycles the focus
    across the active page's controls (the strip is target 0, so the arrows
    reach it there), ``enter``/``space`` activates buttons, checkboxes and
    table rows, ``s`` cycles the table's sort column, ``escape`` closes the
    modal or returns to the menu and ``q`` quits -- except while the text
    field owns the focus, where ``q`` types.
    """

    name = "components"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._tab = 0
        self._focus = 0  # index into the active page's targets; 0 is the strip
        self._sort_col = -1  # no column sorted yet
        self._modal = False
        self._toast: tuple[str, int, str] | None = None  # (text, phase, level)
        #: The open dialog's rectangle from the last render, for clicks.
        self._dialog_rect = (0, 0, 0, 0)  # (row, col, height, width)

        # -- the controls (one instance each, shared by every page) --------
        self.tabs = Tabs(list(_PAGES), theme=theme)
        self.input = Input("DSN-07", placeholder="callsign\u2026", theme=theme)
        self.radio = RadioGroup(["low", "mid", "high"], index=1, theme=theme)
        self.checkbox = Checkbox("lock uplink", theme=theme)
        self.slider = Slider(6, maximum=10, theme=theme)
        self.table = Table(
            [list(row) for row in _PROBES], headers=["probe", "ping", "lock"],
            theme=theme,
        )
        self.save = Button("save preset", theme=theme)
        self.confirm = Button("arm uplink\u2026", theme=theme)
        self.dialog = Dialog(
            "arm the uplink?",
            Text("route DSN-07 through relay-04?", theme=theme),
            [("arm signal", "ok"), ("cancel", None)],
            theme=theme,
        )

        # -- focus targets per page (index 0 is always the tab strip) -------
        self._targets: tuple[tuple[Widget, ...], ...] = (
            (self.tabs, self.input, self.radio, self.checkbox, self.slider),
            (self.tabs, self.table),
            (self.tabs, self.save, self.confirm),
        )

        # -- the frame: the strip, both panels, then toast and hint rows ----
        self._code = LinesView(theme)
        self._highlighter = RegexHighlighter(theme=theme)
        self._left_col = Column([], gap=1)
        self._left = Panel(self._left_col, title="widgets", theme=theme)
        self._right = Panel(self._code, title="the whole story", theme=theme)
        self._body = Row([self._left, self._right], widths=[44, None], gap=1)
        self._set_focus(0)
        self._mount()

    def enter(self) -> None:
        super().enter()
        self._tab = 0
        self._focus = 0
        self._sort_col = -1
        self._modal = False
        self._toast = None
        self._dialog_rect = (0, 0, 0, 0)
        self.tabs.select(0)
        self.input.text = "DSN-07"
        self.radio.index = 1
        self.checkbox.checked = False
        self.slider.value = 6
        self.table.rows = [list(row) for row in _PROBES]
        self._set_focus(0)
        self._mount()

    # -- public state ----------------------------------------------------------

    @property
    def modal(self) -> bool:
        return self._modal

    @property
    def sort_column(self) -> int:
        return self._sort_col

    @property
    def page(self) -> int:
        return self._tab

    @property
    def toast_state(self) -> tuple[str, int, str] | None:
        return self._toast

    # -- state ------------------------------------------------------------------

    def _set_focus(self, index: int) -> None:
        """Point the page's one focus at ``index`` and sync the widgets' flags."""
        targets = self._targets[self._tab]
        self._focus = index % len(targets)
        for position, target in enumerate(targets):
            target.focused = position == self._focus

    def _enter_tab(self, index: int) -> None:
        """Switch pages, drop the focus back onto the strip, remount."""
        self.tabs.select(index)
        self._tab = self.tabs.index
        self._set_focus(0)
        self._mount()

    def _label(self, text: str) -> Text:
        """One faint field label above a control."""
        return Text(text, style=self.theme.text.muted, theme=self.theme)

    def _mount(self) -> None:
        """Point the left panel's column at the active page's controls."""
        if self._tab == 0:
            self._left_col.children = [
                self._label("callsign"),
                self.input,
                self._label("band"),
                self.radio,
                self._label("link"),
                self.checkbox,
                self._label("gain"),
                self.slider,
            ]
        elif self._tab == 1:
            self._left_col.children = [
                self._label("s sorts \u00b7 enter picks"),
                self.table,
            ]
        else:
            self._left_col.children = [
                self._label("actions"),
                self.save,
                self.confirm,
            ]

    def toast(self, text: str, level: str = "success") -> None:
        """Land a toast at the current phase; it fades over _TOAST_TICKS."""
        self._toast = (text, self._phase, level)

    # -- the code panel ----------------------------------------------------------

    def _snippet(self) -> list[tuple[str, int]]:
        """The active page's snippet as ``(code, focus group)`` pairs.

        The group maps a line onto the control that drew it (the strip is
        group 0), so the render can emphasise the focused control's lines;
        the text re-reads the controls' live state every frame.
        """
        if self._tab == 0:
            return [
                (f"callsign = Input({self.input.text!r})", 1),
                ("band = RadioGroup(['low', 'mid', 'high'],", 2),
                (f"                 index={self.radio.index})", 2),
                ("lock = Checkbox('lock uplink',", 3),
                (f"          checked={self.checkbox.checked})", 3),
                (f"gain = Slider({self.slider.value}, maximum=10)", 4),
            ]
        if self._tab == 1:
            plain = ("probes = Table(['probe', 'ping', 'lock'], rows)", 1)
            if self._sort_col < 0:
                return [plain, ("# 5 live probes \u00b7 not sorted yet (s sorts)", 1)]
            column = self.table.headers[self._sort_col]
            return [
                plain,
                (f"probes.sort_by({self._sort_col})  # by {column} asc", 1),
            ]
        return [
            ("save = Button('save preset')", 1),
            ("save.take()   # -> a toast", 1),
            ("ask = Dialog('arm the uplink?', body,", 2),
            ("             [('arm signal', 'ok'), ('cancel', None)])", 2),
            ("ask.take()     # -> a toast", 2),
        ]

    def _refresh_code(self) -> None:
        """Re-highlight the snippet, emphasising the focused control's lines."""
        focused = self._targets[self._tab][self._focus]
        group = 0 if focused is self.tabs else self._focus
        lines: list[Line] = []
        for text, owner in self._snippet():
            highlighted = self._highlighter.highlight(text, "python")
            line = highlighted[0] if highlighted else Line.from_text(text)
            if owner == group:
                line = Line(
                    segment.with_style(segment.style.merge(_HOT))
                    for segment in line.segments
                )
            lines.append(line)
        self._code.lines = lines

    # -- rendering ---------------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        self._refresh_code()
        self._body.widths = [min(44, max(30, width * 45 // 100)), None]
        body_rows = list(self._body.render(Constraints(width=width)))
        body_h = max(4, height - 4)
        rows: list[Line] = [
            self._heading_line(),
            self._strip_line(width),
            *body_rows[:body_h],
        ]
        rows.extend(
            Line() for _ in range(body_h - min(len(body_rows), body_h))
        )
        rows.append(self._toast_line(width))
        rows.append(self._hint_line())
        rows = [row.clip(_CLIP, width) for row in rows[:height]]
        if self._modal:
            rows = self._overlay(rows, width, height)
        return Surface.of(rows, width)

    def _heading_line(self) -> Line:
        """The one-row title: the section's name and its one-line pitch."""
        return Line(
            (
                Segment("CONSOLE FOUNDRY", self.theme.content.accent),
                Segment(" \u00b7 real controls beside their live source", self.theme.text.faint),
            )
        )

    def _strip_line(self, width: int) -> Line:
        """The tab strip's one fitted row, painted at the full width."""
        strip = self.tabs.render(Constraints(width=width))
        return next(iter(strip)).clip(_CLIP, width)

    def _toast_line(self, width: int) -> Line:
        """The action row: the live toast with its countdown, or a placeholder."""
        placeholder = Line((Segment("actions land here", self.theme.text.faint),))
        if self._toast is None:
            return placeholder
        text, issued, level = self._toast
        remaining = _TOAST_TICKS - (self._phase - issued)
        if remaining <= 0:
            return placeholder
        if level == "success":
            glyph, style = GLYPHS.notice_success, self.theme.status.success
        elif level == "warn":
            glyph, style = GLYPHS.notice_warn, self.theme.status.warning
        else:
            glyph, style = GLYPHS.notice_info, self.theme.status.info
        filled = max(1, min(5, remaining * 5 // _TOAST_TICKS))
        dots = "\u25cf" * filled + "\u25cb" * (5 - filled)
        return Line(
            (
                Segment(seat(glyph), style),
                Segment(f" {text} ", self.theme.text.base),
                Segment(dots, self.theme.text.faint),
            )
        )

    def _hint_line(self) -> Line:
        """The one-row key hint bar."""
        faint = self.theme.text.faint
        return Line(
            (
                Segment("tab focus \u00b7 enter activate \u00b7 s sort", faint),
                Segment(" \u00b7 esc menu \u00b7 q quit", faint),
            )
        )

    def _dialog_frame(self, width: int) -> tuple[list[Line], int, int]:
        """The dialog's rows centred in ``width``, as ``(rows, dx, dy)``."""
        dialog_rows = list(
            self.dialog.render(Constraints(width=min(56, max(24, width - 4))))
        )
        dw = max((row.width for row in dialog_rows), default=0)
        dh = len(dialog_rows)
        return dialog_rows, max(0, (width - dw) // 2), dh

    def _overlay(self, rows: list[Line], width: int, height: int) -> list[Line]:
        """The modal dialog centred over the frame, the frame row cut around it."""
        dialog_rows, dx, dh = self._dialog_frame(width)
        if not dialog_rows:
            return rows
        dw = max(row.width for row in dialog_rows)
        dialog_rows = [row.fill(dw) for row in dialog_rows]
        dy = max(0, (height - dh) // 2)
        self._dialog_rect = (dy, dx, dh, dw)
        # The ground must carry real segments to the full width: a cut into a
        # bare blank Line answers nothing, and the dialog would lose its pad.
        ground = [row.fill(width) for row in rows[:height]]
        ground.extend(Line((Segment(" " * width),)) for _ in range(height - len(ground)))
        out: list[Line] = []
        for row in range(height):
            if dy <= row < dy + dh:
                line = dialog_rows[row - dy]
                out.append(
                    (
                        cut_line(ground[row], 0, dx)
                        + line
                        + cut_line(ground[row], dx + dw, width)
                    ).clip(_CLIP, width)
                )
            else:
                out.append(ground[row])
        return out

    # -- behaviour ---------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if self._modal:
            return self._modal_key(event)
        if key == "escape":
            return "menu"
        if key in ("tab", "s-tab", "backtab"):
            step = -1 if key in ("s-tab", "backtab") else 1
            self._set_focus(self._focus + step)
            return None
        target = self._targets[self._tab][self._focus]
        if key == "q" and not isinstance(target, Input):
            return "quit"
        if target is self.tabs:
            return self._strip_key(event)
        if key in ("enter", "space") and isinstance(target, (Button, Checkbox)):
            return self._activate(target)
        if target is self.table and key == "s":
            self._sort()
            return None
        if target is self.table and key == "enter":
            target.on_key(event)
            self._pick()
            return None
        target.on_key(event)
        return None

    def _strip_key(self, event: KeyEvent) -> str | None:
        """The arrows move the tab strip while it owns the focus."""
        self.tabs.on_key(event)
        if self.tabs.index != self._tab:
            self._enter_tab(self.tabs.index)
        return None

    def _activate(self, target: Button | Checkbox) -> str | None:
        """Activate a button or toggle a checkbox; buttons land their toasts."""
        target.on_action("activate")
        taken = target.take()
        if taken is None:
            return None
        if target is self.save:
            self.toast("preset saved")
        elif target is self.confirm:
            self._modal = True
        return None

    def _sort(self) -> None:
        """Cycle the table's sort: each column ascending, then back to none."""
        self._sort_col += 1
        if self._sort_col >= len(self.table.headers):
            self._sort_col = -1
            return
        self.table.sort_by(self._sort_col)

    def _pick(self) -> None:
        """Toast the row the table's cursor just activated."""
        pick = self.table.take()
        if pick is not None:
            self.toast(f"picked {self.table.rows[pick][0]}", "info")

    def _modal_key(self, event: KeyEvent) -> str | None:
        """Route a key into the open dialog and resolve it when it answers."""
        key = event.key
        self.dialog.on_key(event)
        value = self.dialog.take()
        if key in ("escape", "enter") or value is not None:
            self._resolve(value)
        return None

    def _resolve(self, value: object) -> None:
        """Close the modal and toast the dialog's answer."""
        self._modal = False
        if value == "ok":
            self.toast("uplink armed")
        else:
            self.toast("uplink remains safe", "info")

    def on_click(self, pos: Pos) -> str | None:
        if self._modal:
            dy, dx, dh, dw = self._dialog_rect
            if (
                dx <= pos.x < dx + dw
                and dy <= pos.y < dy + dh
                and self.dialog.on_click(Pos(x=pos.x - dx, y=pos.y - dy))
            ):
                self._resolve(self.dialog.take())
            return None
        if pos.y == 1:  # the strip's own row
            self.tabs.on_click(Pos(x=pos.x, y=0))
            if self.tabs.index != self._tab:
                self._enter_tab(self.tabs.index)
            return None
        if pos.y < 2:
            return None
        # Walk the container tree from the body (the panels start at row 2).
        current: object = self._body
        r, col = pos.y - 2, pos.x
        for _ in range(16):
            child_at = getattr(current, "child_at", None)
            if child_at is None:
                break
            found = child_at(r, col)
            if found is None:
                break
            current, r, col = found
        for index, target in enumerate(self._targets[self._tab]):
            if current is not target:
                continue
            self._set_focus(index)
            local = Pos(x=col, y=r)
            if isinstance(target, (Button, Checkbox)):
                self._activate(target)
            elif target is self.table:
                if target.on_click(local):
                    target.on_action("activate")
                    self._pick()
            elif hasattr(target, "on_click"):
                target.on_click(local)
            break
        return None
