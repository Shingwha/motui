"""Dialog: the modal's pure component -- a title, a body and a row of buttons.

A :class:`Dialog` is everything a modal box *is* and nothing about where it
goes: a single-line frame around a body component, a row of
:class:`~motui.widgets.action.Button` values built from :class:`ButtonSpec`
descriptions, a button cursor, and the small keyboard state machine those
buttons answer to -- ``enter`` takes the focused button's value, ``escape``
cancels, ``tab`` / ``shift+tab`` / ``left`` / ``right`` walk the row.  It
reads no keys of its own and paints nothing outside its own rows: the host
(interaction's ``Modal``) decides where the box sits, what the scrim behind
it looks like, and which keys reach the body first.  This module imports the
kernel and :class:`~motui.widgets.action.Button` -- no app, no screen, no
frame.

The button row's order is the caller's, and it **is** the keyboard order:
``enter`` takes the focused button, ``escape`` is always the cancel
(nothing pending), and a ``danger`` dialog opens on its last non-dangerous
button -- the GNOME rule that a destructive action is never the one a stray
return lands on.  The dangerous button is not disabled: it still takes
``enter`` when the user focuses it (D3).  A taken button's
:attr:`ButtonSpec.value` is the dialog's one-shot result, read once through
:meth:`Dialog.take_result` -- and a click inside the box presses the button
under the pointer, the one gesture a pointer has in a modal.  The dialog is
a :class:`~motui.core.block.Container`: :meth:`Dialog.child_at` maps body
cells to the body component and button cells to the corresponding
:class:`~motui.widgets.action.Button`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from ..core.block import Component, Revisioned
from ..core.events import Event, KeyEvent
from ..core.glyphs import GLYPHS, Border, Glyphs
from ..core.lines import Line, Segment, Text
from ..core.style import Style
from ..core.text import ellipsize_tail, visible_width
from ..core.theme import DEFAULT_THEME, Styles, Theme
from ..core.widget import Widget
from .action import Button
from .textfield import Input

__all__ = ["ButtonSpec", "Dialog", "confirm_dialog", "prompt_dialog"]

#: "No decision yet" inside the dialog: a legal result may be ``None`` (a
#: cancel button), so the absence of a result needs its own value.
_NO_RESULT = object()


@dataclass(frozen=True)
class ButtonSpec:
    """One dialog button: a label, the value it returns, and its styles.

    ``label`` is the button's text and ``value`` what
    :meth:`Dialog.take_result` answers when the button is taken.  ``styles``
    overrides whole role groups on the rendered
    :class:`~motui.widgets.action.Button` (the migrated widget convention:
    ``controls.base`` is the base band, ``surfaces.hover`` the hover band and
    ``controls.focus`` the focus band); ``danger`` says the button is the
    destructive one -- its base band defaults to the theme's ``status.danger``
    when no ``styles`` is given, and a ``danger``
    dialog will not focus it on open (D3).
    """

    label: str
    value: object = None
    styles: Styles | None = None
    danger: bool = False


class Dialog(Widget):
    """A titled box with a body component and a row of buttons.

    The box is drawn inside the width the render is handed: ``width`` when
    the constructor pins one, else ``3/5`` of the painting width, never
    below 24 nor above 72 columns -- and never wider than the pane, however
    small it is.  The top edge embeds the title (``\u250c\u2500 title
    \u2500\u2500\u2510``; an over-wide title is ellipsized, an empty one
    leaves the bare rule), the body renders one column in from each side
    (``\u2502 body \u2502``), the button row is the buttons joined by single
    spaces and aligned ``"center"`` (the default) or ``"right"`` inside the
    same interior, and every box row is padded solid while ``shade`` is
    ``True``.  ``border`` swaps the whole frame vocabulary (a
    :class:`~motui.core.glyphs.Border`, ``glyphs.box`` by default),
    the border color defaults to ``borders.base`` -- ``status.danger`` while
    ``danger`` -- and the title to ``content.headings[1]`` (D5); both are
    resolved at render time from ``styles`` (when given) or the theme.

    **``frame=False`` drops the box and keeps the dialog.**  No frame rows
    are drawn and no title with them -- there is no edge to embed it in, so
    the host composes its own heading -- while the rest of the geometry
    holds: the body renders inset one column per side (at ``box - 2``), the
    button row keeps its ``align`` and its cursor, and a click still lands
    the button under the cell (the hit columns shift with the missing
    border).  ``border`` and the border styles are accepted and unused: no
    frame is drawn, and no ground is invented in its place -- the dialog's
    own cells stay plain -- and the ``danger`` cue rides the dangerous
    button's own ``status.danger`` band, which :meth:`_new_button` gives
    every style-less danger spec.  ``frame`` is a plain mutable attribute
    like ``shade``.

    ``index`` is the button cursor: assigning clamps into range (a
    buttonless dialog keeps ``0``) and drives the buttons' own ``focused``
    flags, so :attr:`focused_button` -- the button the keys act on, ``None``
    when there is none -- always agrees with the cursor.  It is deliberately
    not called ``focused``: the dialog itself is not a focus target, and
    :class:`~motui.app.focus.FocusManager` must not mistake it for one.

    :meth:`handle` is the dialog's whole keyboard surface: ``escape``
    cancels, ``enter`` takes the focused button's value, the tab/arrow pair
    walks the cursor, everything else is declined (``False``) for the host
    -- which routes the body's keys first.  :meth:`click` presses the button
    under a rendered cell and declines every other cell.  Both leave the
    taken button's :attr:`ButtonSpec.value` pending -- the one-shot result
    the host reads once through :meth:`take_result`; ``escape`` leaves a
    pending ``None``, the cancel.  A press goes through the button's own
    :meth:`~motui.widgets.action.Button.activate` /
    :meth:`~motui.widgets.action.Button.take_result`, so the button and the
    dialog share one activation rule.  :meth:`render`
    remembered nothing itself: its rows are a pure function of the body's
    rows and the frame's parameters, and :meth:`revision` is the value
    snapshot the block's row cache keys on.
    """

    __slots__ = (
        "_body_inner",
        "_body_lead",
        "_body_rows",
        "_body_start",
        "_border",
        "_buttons",
        "_hit",
        "_index",
        "_pending",
        "_specs",
        "align",
        "body",
        "danger",
        "frame",
        "shade",
        "title",
        "width",
    )

    def __init__(
        self,
        title: str,
        body,
        buttons: Sequence[ButtonSpec | tuple | str],
        *,
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
        # The body rows of the last render: kept so ``revision`` can name
        # their identity (the Panel precedent -- a body whose rows are
        # remembered answers the same objects) and ``child_at`` can map a
        # body cell back to the body component.
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
        #: The pending result: the taken button's value (``None`` is legal --
        #: a cancel button) or ``escaped`` (see ``_NO_RESULT``).
        self._pending: object = _NO_RESULT
        # The cursor opens where D3 says: the last non-dangerous button of a
        # dangerous dialog (its cancel, usually), the first button otherwise.
        self._index = self._default_index()
        self._sync_focus()

    # -- the buttons ------------------------------------------------------------

    @staticmethod
    def _spec(button: ButtonSpec | tuple | str) -> ButtonSpec:
        """One button argument as a :class:`ButtonSpec`.

        A plain string is a label; a tuple is ``(label, value)`` or
        ``(label, value, styles)``; a spec is itself.
        """
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
        """The :class:`Button` one spec renders as (groups resolve in Button).

        ``spec.styles`` is the override the button receives verbatim.  A
        spec without one that is ``danger`` gets ``controls.base`` re-aimed
        at this dialog's ``status.danger`` -- the old ``style`` default --
        so the danger band matches the border cue and every other band keeps
        its theme value.
        """
        styles = spec.styles
        if styles is None and spec.danger:
            theme = self._theme
            styles = Styles(controls=replace(theme.controls, base=theme.status.danger))
        return Button(spec.label, styles=styles, theme=self.theme)

    def _default_index(self) -> int:
        """The button the dialog opens focused on (D3).

        ``danger=True`` focuses the **last non-dangerous** button -- a
        confirm dialog therefore opens on its cancel -- and a dialog
        without the flag focuses the first button.
        """
        if self.danger:
            for index in range(len(self._specs) - 1, -1, -1):
                if not self._specs[index].danger:
                    return index
        return 0

    def _sync_focus(self) -> None:
        """Drive the buttons' own ``focused`` flags from the cursor."""
        for position, button in enumerate(self._buttons):
            button.focused = position == self._index

    @property
    def index(self) -> int:
        """The button cursor (``0`` for a buttonless dialog)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = min(max(value, 0), len(self._specs) - 1) if self._specs else 0
        self._sync_focus()

    @property
    def focused_button(self) -> Button | None:
        """The button the keys act on, or ``None`` for a buttonless dialog.

        The cursor's own view: ``index`` names it and this hands the
        :class:`Button` itself out, so a host can read the label of the
        button a stray return would take without re-building the row.  The
        name keeps the dialog outside :class:`~motui.core.block.Focusable`
        -- a focus ring must not register a modal box as a target.
        """
        return self._buttons[self._index] if self._buttons else None

    # -- the keyboard and the pointer -------------------------------------------

    def handle(self, event: Event) -> bool:
        """Consume the dialog's own keys; ``True`` when one is taken.

        ``escape`` is the cancel: it leaves a pending ``None`` and answers
        ``True``.  ``enter`` takes the focused button's
        ``value`` (a dangerous button included -- the keyboard rule is "not
        the default focus", never "disabled").  ``tab`` / ``right`` step
        the cursor on and ``s-tab`` / ``left`` step it back, clamped and
        never wrapping -- in a two-button dialog that is the left/right
        swap.  Every other key answers ``False``: the body's keys are the
        host's to route (W3's ``Modal`` hands the body the keyboard first).
        A non-key event (the modal may hand a bodyless panel a paste) is
        declined.
        """
        if not isinstance(event, KeyEvent):
            return False
        name = event.key
        if name == "escape":
            self._pending = None
            return True
        if not self._buttons:
            return False
        if name == "enter":
            self._take_button(self._index)
            return True
        if name in ("tab", "right"):
            self.index = self._index + 1
            return True
        if name in ("s-tab", "left"):
            self.index = self._index - 1
            return True
        return False

    def focus_at(self, row: int, col: int) -> bool:
        """Move the button cursor onto the button under a cell; ``True`` on a hit.

        The focus half of a click: the leaf button still takes its own
        action, while the dialog updates :attr:`index` and the button flags.
        This is what the focus tier calls when a click bubbles through the
        dialog; :meth:`click` remains the direct one-gesture door for a
        modal that routes its own pointer.
        """
        hit = self._button_at(row, col)
        if hit is None:
            return False
        self.index = hit
        return True

    def click(self, row: int, col: int) -> bool:
        """Press the button under a cell; ``True`` on a hit.

        ``row``/``col`` are a 0-based cell of this component's own render,
        resolved against the **last render's** button row (the ``Tabs``
        precedent): a cell on a button takes that button's value (a click
        presses it: in a modal the pointer has one gesture, not the
        focus-then-activate pair a ring gives) and moves the cursor onto it;
        every other cell (the title, the body, the border) answers ``False``
        and consumes nothing.
        """
        hit = self._button_at(row, col)
        if hit is None:
            return False
        self.index = hit
        self._take_button(hit)
        return True

    def _take_button(self, index: int) -> None:
        """Activate one button and carry its spec's value into the result.

        The dialog's one activation rule, shared by ``enter`` and a click:
        the button's own :meth:`~motui.widgets.action.Button.activate` lands
        its pending flag, :meth:`~motui.widgets.action.Button.take_result`
        clears it, and the dialog stores the :class:`ButtonSpec.value` the
        button stands for -- so the component and its button never drift.
        """
        button = self._buttons[index]
        button.activate()
        button.take_result()
        self._pending = self._specs[index].value

    def take_result(self) -> object | None:
        """Read the pending result once and clear it (the ``Resultful`` door).

        ``None`` means "no decision yet"; a cancel (``escape`` or a
        ``None``-valued button) is a taken decision whose value is ``None``
        and is told apart only by the take itself.
        """
        value = self._pending
        self._pending = _NO_RESULT
        return None if value is _NO_RESULT else value

    def _arm_result(self) -> None:
        """Discard any pending result (the modal's arm step, before routing)."""
        self._pending = _NO_RESULT

    def _take_decision(self) -> tuple[bool, object]:
        """Read the routing's decision as ``(made, value)``; clear it.

        The distinction ``take_result`` cannot carry -- a decision whose
        value is ``None`` versus no decision at all -- for a routing layer
        that must know whether to close.  Internal: hosts use
        :meth:`take_result`.
        """
        value = self._pending
        self._pending = _NO_RESULT
        return (False, None) if value is _NO_RESULT else (True, value)

    def _button_at(self, row: int, col: int) -> int | None:
        """The button index a rendered cell lands on, or ``None``.

        The geometry comes from the last :meth:`render`: the button row's
        index and each button's ``[start, stop)`` columns inside the box.
        """
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

        The geometry is the last :meth:`render`'s: body rows are the body
        component's own rows (top edge and one pad column in, when framed)
        and the button row's spans are the buttons' own cells.  The frame
        cells, the pad columns, the join spaces and every row outside the
        box answer ``None`` -- the dialog owns those.
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

    def render(self, width: int) -> list[Line]:
        """The box: the title edge, the body, the button row, the bottom edge.

        The box's width is ``width`` when the constructor pinned one, else
        ``3/5`` of the painted width, floored at 24 and capped at 72 -- and
        the pane's own width always wins, so no row ever exceeds it.  The
        body renders one pad column in from each edge (at ``box - 4``
        columns framed, ``box - 2`` with ``frame=False``); every row is
        closed with :meth:`~motui.core.lines.Line.fit` so a squeezed box
        truncates instead of overflowing.  Borderless, the frame rows and
        the title are gone and the body is the box's first row.
        """
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
            return [Line()]
        lead = 2 if self.frame else 1  # the border and one pad column, or the pad alone
        inner = max(0, box - 2 * lead)  # the text's cells
        self._body_rows = list(self.body.render(inner))
        self._body_start = 1 if self.frame else 0
        self._body_lead = lead
        self._body_inner = inner
        out: list[Line] = []
        if self.frame:
            out.append(self._top_row(box, border_style, title_style))
        for row in self._body_rows:
            out.append(self._interior_row(row.fit(inner), box, lead, border_style))
        button_row = len(out)
        if self._buttons:
            out.append(self._button_row(box, inner, button_row, lead, border_style))
        if self.frame:
            out.append(self._bottom_row(box, border_style))
        return [row.fit(width) for row in out]

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
        """``\u2502 content \u2502``: one pad column each side of ``content``.

        ``shade=True`` fills the gap between the content and the closing
        edge (so every row is exactly ``box`` columns wide and the box is a
        solid rectangle); ``shade=False`` leaves the row ending right after
        its content plus the two pads, the closing pad travelling with it
        (the closing border, framed).  Borderless (``lead == 1``) the same
        row loses the border cells and keeps the pads: two plain columns
        where the framed row carries ``border_style``.
        """
        fill = max(0, box - 2 * lead - content.width) if self.shade else 0
        if self.frame:
            head = Segment(f"{self._border.left} ", border_style)
            tail = Segment(f" {self._border.right}", border_style)
        else:
            head = tail = Segment(" ")
        segments = [head, *content.segments]
        if fill:
            segments.append(Segment(" " * fill))
        segments.append(tail)
        return Line(segments)

    def _button_row(
        self, box: int, inner: int, row_index: int, lead: int, border_style: Style
    ) -> Line:
        """The buttons joined by single spaces, aligned inside the interior.

        Each button renders at its own natural width (``label`` plus its two
        padding cells), the row is placed ``center`` or ``right`` in the
        interior, and the columns it lands on -- ``lead`` cells in from the
        box's left edge -- are remembered for :meth:`click`.
        """
        lines = [
            button.render(visible_width(button.label) + 2)[0] for button in self._buttons
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
            [(lead + left + offset, line.width) for offset, line in zip(offsets, lines)],
        )
        return self._interior_row(content, box, lead, border_style)

    def revision(self) -> object:
        """The row cache's snapshot: every input the box's rows read.

        In order, the values are:

        * ``title`` -- embedded in the top rule (or gone with the frame);
        * ``width`` -- pins the box (`None`: the width-derived default);
        * ``frame`` -- whether the edge, the title and the bottom rule exist;
        * ``shade`` -- whether an interior row is filled solid to the edge;
        * ``align`` -- where the button row sits in the interior;
        * ``danger`` plus the ``theme``/``styles`` pair -- together they
          resolve the border and title bands at render time;
        * the border tuple -- it paints every frame cell;
        * every button's own :meth:`~motui.widgets.action.Button.revision`
          (label, ``focused`` -- which mirrors the cursor -- and its three
          bands): the button row is those rows joined and placed;
        * the body's snapshot: when the body is
          :class:`~motui.core.block.Revisioned` and answers one, its
          ``revision()`` **is** the body's contribution -- a value that
          moves with a streamed ``text =`` assignment on the first frame,
          not after a render.  Only a body outside the protocol (or one
          that switched its snapshot off with ``None``) falls back to the
          identity of the rows the last render answered (the ``Panel``
          precedent); such a body either answers the same row objects and
          compares stable, or rebuilds them every call and simply misses.

        The button cursor itself is covered by the buttons' ``focused``
        flags (``_sync_focus`` keeps them in step), and the pending result /
        ``_hit`` are not row inputs.  The snapshot is plain values (no live
        lists), so it costs far less than one render.
        """
        body = self.body
        if isinstance(body, Revisioned):
            body_revision = body.revision()
        else:
            body_revision = None
        if body_revision is None:
            body_snapshot = ("rows", tuple(map(id, self._body_rows)))
        else:
            body_snapshot = ("revision", body_revision)
        return (
            self.title,
            self.width,
            self.frame,
            self.shade,
            self.align,
            self.danger,
            self._border,
            self.theme,
            self.styles,
            tuple(button.revision() for button in self._buttons),
            body_snapshot,
        )

    def __repr__(self) -> str:
        return f"Dialog({self.title!r}, index={self._index}, danger={self.danger})"


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
    """The Yes/No confirmation: a plain message and two buttons (thin builder).

    Always the same shape -- an untitled box, a :class:`~motui.core.lines.Text`
    body, the confirm button first and the cancel second (D3: the main
    action on the left, the cancel on the right).  With ``danger`` the
    **confirm** button takes the theme's ``error`` band, the cancel never
    does, and the dialog opens focused on the cancel -- the last
    non-dangerous button -- so a stray return never lands the destructive
    action.  Both labels are text a host can rewrite; they default to the
    classic ``"Yes"``/``"No"`` pair.  ``frame=False`` forwards the dialog's
    own borderless mode: the message and the row, no box around them (the
    danger band on the confirm button is then the whole cue).
    """
    return Dialog(
        title="",
        body=Text(message),
        buttons=[
            ButtonSpec(confirm_text, True, danger=danger),
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
    """The one-line prompt: a field body and the OK / Cancel row (thin builder).

    The prompt is a :class:`Dialog` whose body is a single-line
    :class:`~motui.widgets.textfield.Input`: ``title`` heads the box,
    ``placeholder`` is the field's empty-state hint and ``mask`` its
    display-only mask -- both forwarded verbatim, so the buffer's text stays
    plain however it renders.  ``confirm_text`` / ``cancel_text`` are the two
    buttons' labels (D3: the main action on the left, the cancel on the
    right), and ``styles`` are the **field's** group overrides, resolved through
    the component charter -- ``styles`` > ``theme`` field > :data:`DEFAULT_THEME
    <motui.core.theme.DEFAULT_THEME>` -- while the buttons keep their own
    (the focused button's accent band, from ``theme``).  ``danger=True``
    marks the box -- the error border -- and opens focused on the **cancel**:
    a stray return never lands a destructive edit, the same GNOME rule
    :func:`confirm_dialog` keeps.  ``frame=False`` forwards the dialog's own
    borderless mode -- the field and the button row, no box -- and the title
    goes with the frame: there is no edge to embed it in, so the host
    composes its own heading (the danger cue is then the confirm button's
    ``error`` band).

    **Enter reaches the dialog's buttons, not the field.**  The field's
    keymap binds no ``enter`` at all, so when a
    :class:`~motui.app.modal.Modal` routes the keyboard body-first
    the key falls through to the button row and activates the focused button
    -- the modal's contract working exactly as intended.  The host reads the
    outcome the usual way: ``dialog.take_result()`` is ``"ok"`` when the
    confirm button was taken -- read the payload off the field,
    ``dialog.body.text`` -- and ``None`` for the cancel, an ``escape`` or a
    click outside.  There is deliberately no extra value on the prompt: the
    field is the payload, and the text is the host's to read and clear.
    """
    return Dialog(
        title=title,
        body=Input(
            placeholder=placeholder,
            mask=mask,
            styles=styles,
            glyphs=glyphs,
            theme=theme,
        ),
        buttons=[
            ButtonSpec(confirm_text, "ok"),
            ButtonSpec(cancel_text, None),
        ],
        danger=danger,
        frame=frame,
        glyphs=glyphs,
        theme=theme,
    )
