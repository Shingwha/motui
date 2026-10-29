"""Dialog: the modal's pure component -- a title, a body and a row of buttons.

A framed body with a button row, button cursor and keyboard state machine
(``enter`` takes, ``escape`` cancels, tab/arrows walk).  The host decides
placement, scrim and key routing; this module imports only the kernel and
:class:`Button`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..kernel.cell import Line, Segment, Surface
from ..kernel.document import Component
from ..kernel.events import Event, KeyEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Border, Glyphs
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode, ellipsize_tail, visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import _MISSING, CursorWidget
from ..widgets.text import Text
from .action import Button, ButtonKind
from .textfield import Input

__all__ = ["ButtonSpec", "Dialog", "confirm_dialog", "prompt_dialog"]


@dataclass(frozen=True)
class ButtonSpec:
    """One dialog button: a label, the value it returns, and its role.

    ``kind=DANGER`` is the destructive role; a ``danger`` dialog opens on
    the last non-dangerous button.
    """

    label: str
    value: object = None
    styles: Styles | None = None
    kind: ButtonKind = ButtonKind.NEUTRAL


class Dialog(CursorWidget):
    """A titled box with a body component and a row of buttons.

    The box is ``width`` when pinned, else 3/5 of the painting width clamped
    to 24..72 and never wider than the pane; the title is embedded in its
    top rule.  The body renders inset one column per side; buttons are
    joined by spaces and aligned ``center``/``right``.  ``frame=False``
    drops the box and title but keeps the body/button geometry.
    ``index`` is the button cursor (never the dialog's own focus flag) and
    drives each button's ``focused``.  ``enter``/clicks leave the chosen
    :attr:`ButtonSpec.value` pending for :meth:`take`; ``escape`` leaves a
    pending ``None``.  A danger dialog opens on its last non-dangerous
    button.  ``child_at`` maps body and button cells.
    """

    __slots__ = (
        "_body_inner",
        "_body_lead",
        "_body_rows",
        "_body_start",
        "_border",
        "_buttons",
        "_hit",
        "_specs",
        "align",
        "body",
        "danger",
        "frame",
        "shade",
        "title",
        "width",
    )

    #: The dialog routes its own subtree's focus (its body and its button
    #: row); it is deliberately not itself a focus-ring target.
    focus_scope = True

    def __init__(
        self,
        body,
        *,
        title: str = "",
        buttons: Sequence[ButtonSpec | tuple | str] = (),
        danger: bool = False,
        width: int | None = None,
        align: str = "center",
        border: Border | None = None,
        shade: bool = True,
        frame: bool = True,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.title = title
        self.body = body
        self.danger = danger
        self.width = width
        if align not in ("center", "right"):
            raise ValueError(f"align must be 'center' or 'right', got {align!r}")
        self.align = align
        self.shade = shade
        self.frame = frame
        self._border = glyphs.box if border is None else border
        self._specs = [self._spec(button) for button in buttons]
        self._buttons = [self._new_button(spec) for spec in self._specs]
        # The body rows of the last render: kept for ``child_at`` (a body
        # cell maps back to the body component) and as the hover/paint
        # geometry of the most recent render.
        self._body_rows: list[Line] = []
        # The body's geometry in the last render: its first row, the pad
        # columns before it, and the width it was rendered at.  ``child_at``
        # reads the same numbers ``render`` wrote, so a hit and a paint can
        # never disagree.
        self._body_start = 0
        self._body_lead = 0
        self._body_inner = 0
        # The button row of the last render: ``(row index, [(start, width)])``,
        # what ``click`` resolves a cell against.  ``None`` until the first
        # render, so no click lands before the geometry exists.
        self._hit: tuple[int, list[tuple[int, int]]] | None = None
        # The cursor opens where D3 says: the last non-dangerous button of a
        # dangerous dialog (its cancel, usually), the first button otherwise.
        # Installed directly (construction moves nothing and writes no
        # result), with the button flags driven from it.
        self._sync_cursor()
        self._cursor.index = self._default_index()
        self._sync_focus()
        # The explicit tree: the body and every button are the dialog's
        # children, so ``walk()`` covers the whole box without guessing.
        self.children = [self.body, *self._buttons]

    # -- cursor hooks ------------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self._buttons)

    def _entry_at(self, index: int) -> object | None:
        return self._buttons[index]

    def _cursor_enabled(self) -> bool:
        return True

    def _cursor_wraps(self) -> bool:
        return False

    # -- the buttons ------------------------------------------------------------

    @staticmethod
    def _spec(button: ButtonSpec | tuple | str) -> ButtonSpec:
        """One button argument as a spec: a label, ``(label, value)`` or the spec itself."""
        if isinstance(button, ButtonSpec):
            return button
        if isinstance(button, tuple):
            if len(button) == 2:
                return ButtonSpec(button[0], button[1])
            if len(button) == 3:
                return ButtonSpec(button[0], button[1], button[2])
            raise ValueError(
                f"a button tuple is (label, value) or (label, value, styles), got {button!r}"
            )
        return ButtonSpec(str(button))

    def _new_button(self, spec: ButtonSpec) -> Button:
        """The :class:`Button` one spec renders as; styles and kind pass through."""
        return Button(
            spec.label, kind=spec.kind, styles=spec.styles, theme=self.theme
        )

    def _default_index(self) -> int:
        """The initial cursor: the last non-dangerous button on a danger dialog, else 0."""
        if self.danger:
            for index in range(len(self._specs) - 1, -1, -1):
                if self._specs[index].kind is not ButtonKind.DANGER:
                    return index
        return 0

    def _sync_focus(self) -> None:
        current = self.index
        for position, button in enumerate(self._buttons):
            button.focused = position == current

    def select(self, index: int) -> bool:
        """Place the button cursor on ``index`` and mirror the focus flags."""
        changed = super().select(index)
        self._sync_focus()
        return changed

    def move(self, delta: int) -> bool:
        """Move the button cursor ``delta`` places and mirror the focus flags."""
        changed = super().move(delta)
        self._sync_focus()
        return changed

    @property
    def focused_button(self) -> Button | None:
        """The button the keys act on, or ``None`` for a buttonless dialog.

        The dialog is deliberately not a focus-ring target itself.
        """
        button = self.selected
        return button if isinstance(button, Button) else None

    # -- the keyboard and the pointer -------------------------------------------

    def on_key(self, event: Event) -> bool:
        """Consume the dialog's keys: ``escape`` cancels, ``enter`` activates, tab/arrows move.

        Every other key, and non-key events, answer ``False`` so the host
        keeps routing to the body.
        """
        if not isinstance(event, KeyEvent):
            return False
        name = event.key
        if name == "escape":
            self._emit(None)
            return True
        if not self._buttons:
            return False
        if name == "enter":
            return self.activate()
        if name in ("tab", "right"):
            return self.move(1)
        if name in ("s-tab", "left"):
            return self.move(-1)
        return False

    def activate(self) -> bool:
        """Take the focused button's value as the dialog's result; ``False`` without buttons."""
        if not self._buttons:
            return False
        self._take_button(self.index)
        return True

    def focus_at(self, row: int, col: int) -> bool:
        """Move the button cursor onto the button under a cell; ``True`` on a hit.

        The focus tier's half of a click; the leaf button still runs its own
        action.
        """
        hit = self._button_at(row, col)
        if hit is None:
            return False
        self.select(hit)
        return True

    def on_click(self, pos: Pos) -> bool:
        """Press the button under a cell; ``True`` on a hit.

        A modal click is one gesture: it moves the cursor and takes the
        button.  Any other cell declines.
        """
        hit = self._button_at(pos.y, pos.x)
        if hit is None:
            return False
        self.select(hit)
        self._take_button(hit)
        return True

    def _take_button(self, index: int) -> None:
        """Activate one button and emit its spec's value (the one activation rule).

        The button's own ``on_action("activate")`` + ``take()`` keep the
        component and its button in step.
        """
        button = self._buttons[index]
        button.on_action("activate")
        button.take()
        self._emit(self._specs[index].value)

    def _arm_result(self) -> None:
        self._clear_result()

    def _take_decision(self) -> tuple[bool, object]:
        """Read the routing's decision as ``(made, value)`` and clear it.

        Distinguishes a made decision carrying ``None`` from no decision.
        """
        value = self._result
        object.__setattr__(self, "_result", _MISSING)
        return (False, None) if value is _MISSING else (True, value)

    def _button_at(self, row: int, col: int) -> int | None:
        """The button index a rendered cell lands on, from the last render's geometry."""
        if self._hit is None:
            return None
        hit_row, spans = self._hit
        if row != hit_row:
            return None
        for index, (start, width) in enumerate(spans):
            if start <= col < start + width:
                return index
        return None

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a rendered cell to the dialog child that owns it.

        Body cells map to the body component, button cells to their button;
        frame, pads and gaps answer ``None`` (the dialog owns them).
        """
        body_row = row - self._body_start
        if 0 <= body_row < len(self._body_rows):
            if self._body_lead <= col < self._body_lead + self._body_inner:
                return self.body, body_row, col - self._body_lead
            return None
        hit = self._button_at(row, col)
        if hit is None:
            return None
        hit_row, spans = self._hit  # type: ignore[misc]
        start, _width = spans[hit]
        return self._buttons[hit], row - hit_row, col - start

    # -- rendering ---------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """The box: top edge with title, inset body, button row, bottom edge.

        The width is pinned/3-5ths clamped to the pane; every row is
        ellipsized to it.  ``max_height`` truncates the painted rows, while
        the body/button hit geometry stays untruncated for :meth:`child_at`.
        """
        width = c.width
        box = self.width if self.width is not None else min(72, max(24, width * 3 // 5))
        box = max(0, min(box, width))
        self._hit = None
        # The two frame bands resolve here, once per render: the danger cue
        # replaces the border band outright, and the title sits one level
        # down the heading scale.
        border_style = (
            self.group("status").danger if self.danger else self.group("borders").base
        )
        title_style = self.group("content").headings[1]
        if box <= 0:
            self._body_rows = []
            self._body_start = self._body_lead = self._body_inner = 0
            rows = [Line()]
            if c.max_height is not None:
                rows = rows[: c.max_height]
            return Surface.clipped(rows, c.width)
        lead = 2 if self.frame else 1  # the border and one pad column, or the pad alone
        inner = max(0, box - 2 * lead)  # the text's cells
        self._body_rows = list(self.body.render(Constraints(width=inner)))
        self._body_start = 1 if self.frame else 0
        self._body_lead = lead
        self._body_inner = inner
        out: list[Line] = []
        if self.frame:
            out.append(self._top_row(box, border_style, title_style))
        for row in self._body_rows:
            out.append(
                self._interior_row(
                    row.clip(WrapMode.ELLIPSIS, inner), box, lead, border_style
                )
            )
        button_row = len(out)
        if self._buttons:
            out.append(self._button_row(box, inner, button_row, lead, border_style))
        if self.frame:
            out.append(self._bottom_row(box, border_style))
        rows = [row.clip(WrapMode.ELLIPSIS, width) for row in out]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def _top_row(self, box: int, border_style: Style, title_style: Style) -> Line:
        """``\u250c\u2500 title \u2500\u2500\u2510``: the title embedded in the rule."""
        border = self._border
        inner = max(0, box - 2)
        if self.title and box >= 6:
            label = ellipsize_tail(self.title, box - 5)
            if label:
                fill = max(0, inner - (1 + 2 + visible_width(label)))
                segments = [
                    Segment(border.top_left, border_style),
                    Segment(border.top, border_style),
                    Segment(" ", border_style),
                    Segment(label, title_style),
                    Segment(" ", border_style),
                ]
                if fill:
                    segments.append(Segment(border.top * fill, border_style))
                segments.append(Segment(border.top_right, border_style))
                return Line(segments)
        return Line.from_text(
            f"{border.top_left}{border.top * inner}{border.top_right}",
            border_style,
        )

    def _bottom_row(self, box: int, border_style: Style) -> Line:
        """``\u2514\u2500\u2500\u2518``: the closing rule, corner to corner."""
        border = self._border
        return Line.from_text(
            f"{border.bottom_left}{border.bottom * max(0, box - 2)}"
            f"{border.bottom_right}",
            border_style,
        )

    def _interior_row(
        self, content: Line, box: int, lead: int, border_style: Style
    ) -> Line:
        """``│ content │``: one pad column each side.

        ``shade=True`` fills to the closing edge so every row is exactly
        ``box`` wide; borderless keeps the pads only.  Interior cells rest
        on ``surfaces.raised`` under their own styles.
        """
        raised = self.group("surfaces").raised
        fill = max(0, box - 2 * lead - content.width) if self.shade else 0
        if self.frame:
            head = [
                Segment(self._border.left, border_style),
                Segment(" ", raised),
            ]
            tail = [
                Segment(" ", raised),
                Segment(self._border.right, border_style),
            ]
        else:
            head = tail = [Segment(" ", raised)]
        segments = [
            *head,
            *(
                segment.with_style(raised.merge(segment.style))
                for segment in content.segments
            ),
        ]
        if fill:
            segments.append(Segment(" " * fill, raised))
        segments.extend(tail)
        return Line(segments)

    def _button_row(
        self, box: int, inner: int, row_index: int, lead: int, border_style: Style
    ) -> Line:
        """The buttons joined by single spaces, aligned inside the interior.

        Each button renders at its natural width; the landing columns are
        remembered for :meth:`on_click`.
        """
        lines = [
            button.render(Constraints(width=visible_width(button.label) + 2))[0]
            for button in self._buttons
        ]
        content = Line()
        offsets: list[int] = []
        for index, line in enumerate(lines):
            if index:
                content = content + Line.from_text(" ")  # the join between two buttons
            offsets.append(content.width)
            content = content + line
        free = max(0, inner - content.width)
        left = free // 2 if self.align == "center" else free
        content = Line.filled(left) + content
        self._hit = (
            row_index,
            [
                (lead + left + offset, line.width)
                for offset, line in zip(offsets, lines, strict=True)
            ],
        )
        return self._interior_row(content, box, lead, border_style)

    def __repr__(self) -> str:
        return f"Dialog({self.title!r}, index={self.index}, danger={self.danger})"


def confirm_dialog(
    message: str,
    *,
    danger: bool = False,
    confirm_text: str = "Yes",
    cancel_text: str = "No",
    frame: bool = True,
    glyphs: Glyphs = GLYPHS,
    theme: Theme | None = None,
) -> Dialog:
    """The Yes/No confirmation: a plain message and two buttons.

    Confirm is first, cancel second; ``danger`` makes the confirm button
    DANGER and opens the cursor on the cancel.  ``frame=False`` drops the
    box.
    """
    return Dialog(
        Text(message),
        buttons=[
            ButtonSpec(
                confirm_text,
                True,
                kind=ButtonKind.DANGER if danger else ButtonKind.NEUTRAL,
            ),
            ButtonSpec(cancel_text, False),
        ],
        danger=danger,
        frame=frame,
        glyphs=glyphs,
        theme=theme,
    )


def prompt_dialog(
    title: str,
    *,
    placeholder: str = "",
    mask: str = "",
    confirm_text: str = "OK",
    cancel_text: str = "Cancel",
    styles: Styles | None = None,
    danger: bool = False,
    frame: bool = True,
    glyphs: Glyphs = GLYPHS,
    theme: Theme | None = None,
) -> Dialog:
    """The one-line prompt: an :class:`Input` body and the OK / Cancel row.

    ``placeholder``/``mask`` pass to the field; ``styles`` are the field's
    overrides.  ``danger`` marks the box and opens on the cancel.
    ``frame=False`` drops the box and the title.  The field binds no
    ``enter``, so it falls through to activate the focused button;
    ``take()`` is ``"ok"`` on confirm, else ``None``.  The payload is
    ``dialog.body.text``.
    """
    return Dialog(
        Input(
            placeholder=placeholder,
            mask=mask,
            styles=styles,
            glyphs=glyphs,
            theme=theme,
        ),
        title=title,
        buttons=[
            ButtonSpec(confirm_text, "ok"),
            ButtonSpec(cancel_text, None),
        ],
        danger=danger,
        frame=frame,
        glyphs=glyphs,
        theme=theme,
    )
