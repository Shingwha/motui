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
(``chosen`` stays ``None``), and a ``danger`` dialog opens on its last
non-dangerous button -- the GNOME rule that a destructive action is never
the one a stray return lands on.  The dangerous button is not disabled: it
still takes ``enter`` when the user focuses it (D3).  :attr:`Dialog.chosen`
is the same one-shot value every component's ``chosen`` is: the host reads
it once and resets it to ``None`` -- and a click inside the box presses the
button under the pointer, the one gesture a pointer has in a modal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..kernel.block import Revisioned
from ..kernel.events import Key
from ..kernel.lines import Line, Segment, Text
from ..kernel.style import Style
from ..kernel.text import ellipsize_tail, visible_width
from ..kernel.theme import Theme, Themed
from .action import Button
from .textfield import Input

__all__ = ["ButtonSpec", "Dialog", "confirm_dialog", "prompt_dialog"]

#: The box's frame characters: top-left, top-right, bottom-left,
#: bottom-right, the rule and the side -- the single-line vocabulary
#: :class:`~motui.widgets.decor.Panel` draws with.
BORDER = ("\u250c", "\u2510", "\u2514", "\u2518", "\u2500", "\u2502")


@dataclass(frozen=True)
class ButtonSpec:
    """One dialog button: a label, the value it returns, and its styles.

    ``label`` is the button's text and ``value`` what :attr:`Dialog.chosen`
    receives when the button is taken.  The three style fields follow the
    :class:`~motui.widgets.action.Button` convention (explicit > theme field
    > ``DEFAULT_THEME``); ``danger`` says the button is the destructive one
    -- its base band defaults to the theme's ``error`` and a ``danger``
    dialog will not focus it on open (D3).
    """

    label: str
    value: object = None
    style: Style | None = None
    hover_style: Style | None = None
    focus_style: Style | None = None
    danger: bool = False


class Dialog(Themed):
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
    ``True``.  ``border`` swaps the six frame characters, ``border_style``
    defaults to the theme's ``border`` -- the theme's ``error`` while
    ``danger`` -- and ``title_style`` to the theme's ``heading`` (D5).

    **``frame=False`` drops the box and keeps the dialog.**  No frame rows
    are drawn and no title with them -- there is no edge to embed it in, so
    the host composes its own heading -- while the rest of the geometry
    holds: the body renders inset one column per side (at ``box - 2``), the
    button row keeps its ``align`` and its cursor, and a click still lands
    the button under the cell (the hit columns shift with the missing
    border).  ``border`` and ``border_style`` are accepted and unused: no
    frame is drawn, and no ground is invented in its place -- the dialog's
    own cells stay plain -- and the ``danger`` cue rides the dangerous
    button's own ``error`` band, which :meth:`_new_button` gives every
    style-less danger spec.  ``frame`` is a plain mutable attribute like
    ``shade``.

    ``index`` is the button cursor: assigning clamps into range (a
    buttonless dialog keeps ``0``) and drives the buttons' own ``focused``
    flags, so :attr:`focused` -- the button the keys act on, ``None`` when
    there is none -- always agrees with the cursor.

    :meth:`handle` is the dialog's whole keyboard surface: ``escape``
    cancels, ``enter`` takes the focused button's value, the tab/arrow pair
    walks the cursor, everything else is declined (``False``) for the host
    -- which routes the body's keys first.  :meth:`click` presses the button
    under a rendered cell and declines every other cell.  Both write
    :attr:`chosen`: the value of the button taken, or ``None`` for a cancel
    -- the one-shot result the host reads once and resets.  :meth:`render`
    remembered nothing itself: its rows are a pure function of the body's
    rows and the frame's parameters, and :meth:`revision` is the value
    snapshot the block's row cache keys on.
    """

    __slots__ = (
        "_body_rows",
        "_border",
        "_border_style",
        "_buttons",
        "_hit",
        "_index",
        "_specs",
        "_title_style",
        "align",
        "body",
        "chosen",
        "danger",
        "frame",
        "shade",
        "theme",
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
        border: tuple[str, str, str, str, str, str] | None = None,
        border_style: Style | None = None,
        title_style: Style | None = None,
        shade: bool = True,
        frame: bool = True,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.title = title
        self.body = body
        self.danger = danger
        self.width = width
        if align not in ("center", "right"):
            raise ValueError(f"align must be 'center' or 'right', got {align!r}")
        self.align = align
        self.shade = shade
        self.frame = frame
        self._border = BORDER if border is None else tuple(border)
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._border_style = self._pick(border_style, "error" if danger else "border")
        self._title_style = self._pick(title_style, "heading")
        self._specs = [self._spec(button) for button in buttons]
        self._buttons = [self._new_button(spec) for spec in self._specs]
        # The body rows of the last render: kept so ``revision`` can name
        # their identity (the Panel precedent -- a body whose rows are
        # remembered answers the same objects).
        self._body_rows: list[Line] = []
        # The button row of the last render: ``(row index, [(start, width)])``,
        # what ``click`` resolves a cell against.  ``None`` until the first
        # render, so no click lands before the geometry exists.
        self._hit: tuple[int, list[tuple[int, int]]] | None = None
        #: The pending result: written by ``handle`` / ``click`` (the button
        #: taken), or ``None`` for a cancel; read once by the host, which
        #: resets it to ``None``.
        self.chosen: object | None = None
        # The cursor opens where D3 says: the last non-dangerous button of a
        # dangerous dialog (its cancel, usually), the first button otherwise.
        self._index = self._default_index()
        self._sync_focus()

    # -- the buttons ------------------------------------------------------------

    @staticmethod
    def _spec(button: ButtonSpec | tuple | str) -> ButtonSpec:
        """One button argument as a :class:`ButtonSpec`.

        A plain string is a label; a tuple is ``(label, value)`` or
        ``(label, value, style)``; a spec is itself.
        """
        if isinstance(button, ButtonSpec):
            return button
        if isinstance(button, tuple):
            if len(button) == 2:
                return ButtonSpec(button[0], button[1])
            if len(button) == 3:
                return ButtonSpec(button[0], button[1], button[2])
            raise ValueError(
                f"a button tuple is (label, value) or (label, value, style), got {button!r}"
            )
        return ButtonSpec(str(button))

    def _new_button(self, spec: ButtonSpec) -> Button:
        """The :class:`Button` one spec renders as (styles resolve in Button)."""
        style = spec.style
        if style is None and spec.danger:
            style = self._theme.error
        return Button(
            spec.label,
            style=style,
            hover_style=spec.hover_style,
            focus_style=spec.focus_style,
            theme=self.theme,
        )

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
    def focused(self) -> Button | None:
        """The button the keys act on, or ``None`` for a buttonless dialog.

        The cursor's own view: ``index`` names it and this hands the
        :class:`Button` itself out, so a host can read the label of the
        button a stray return would take without re-building the row.
        """
        return self._buttons[self._index] if self._buttons else None

    # -- the keyboard and the pointer -------------------------------------------

    def handle(self, event: Key) -> bool:
        """Consume the dialog's own keys; ``True`` when one is taken.

        ``escape`` is the cancel: it writes ``None`` into :attr:`chosen`
        and answers ``True``.  ``enter`` takes the focused button's
        ``value`` (a dangerous button included -- the keyboard rule is "not
        the default focus", never "disabled").  ``tab`` / ``right`` step
        the cursor on and ``s-tab`` / ``left`` step it back, clamped and
        never wrapping -- in a two-button dialog that is the left/right
        swap.  Every other key answers ``False``: the body's keys are the
        host's to route (W3's ``Modal`` hands the body the keyboard first).
        """
        name = event.name
        if name == "escape":
            self.chosen = None
            return True
        if not self._buttons:
            return False
        if name == "enter":
            self.chosen = self._specs[self._index].value
            return True
        if name in ("tab", "right"):
            self.index = self._index + 1
            return True
        if name in ("s-tab", "left"):
            self.index = self._index - 1
            return True
        return False

    def click(self, row: int, col: int) -> bool:
        """Press the button under a cell; ``True`` on a hit.

        ``row``/``col`` are a 0-based cell of this component's own render,
        resolved against the **last render's** button row (the ``Tabs``
        precedent): a cell on a button lands that button in :attr:`chosen`
        -- a click presses it: in a modal the pointer has one gesture, not
        the focus-then-activate pair a ring gives -- and moves the cursor
        onto it; every other cell (the title, the body, the border) answers
        ``False`` and consumes nothing.
        """
        hit = self._button_at(row, col)
        if hit is None:
            return False
        self.index = hit
        self.chosen = self._specs[hit].value
        return True

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

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        """The box: the title edge, the body, the button row, the bottom edge.

        The box's width is ``width`` when the constructor pinned one, else
        ``3/5`` of the painted width, floored at 24 and capped at 72 -- and
        the pane's own width always wins, so no row ever exceeds it.  The
        body renders one pad column in from each edge (at ``box - 4``
        columns framed, ``box - 2`` with ``frame=False``); every row is
        closed with :meth:`~motui.kernel.lines.Line.fit` so a squeezed box
        truncates instead of overflowing.  Borderless, the frame rows and
        the title are gone and the body is the box's first row.
        """
        box = self.width if self.width is not None else min(72, max(24, width * 3 // 5))
        box = max(0, min(box, width))
        self._hit = None
        if box <= 0:
            return [Line()]
        lead = 2 if self.frame else 1  # the border and one pad column, or the pad alone
        inner = max(0, box - 2 * lead)  # the text's cells
        self._body_rows = list(self.body.render(inner))
        out: list[Line] = []
        if self.frame:
            out.append(self._top_row(box))
        for row in self._body_rows:
            out.append(self._interior_row(row.fit(inner), box, lead))
        button_row = len(out)
        if self._buttons:
            out.append(self._button_row(box, inner, button_row, lead))
        if self.frame:
            out.append(self._bottom_row(box))
        return [row.fit(width) for row in out]

    def _top_row(self, box: int) -> Line:
        """``\u250c\u2500 title \u2500\u2500\u2510``: the title embedded in the rule."""
        left, right, _bl, _br, rule, _side = self._border
        inner = max(0, box - 2)
        if self.title and box >= 6:
            label = ellipsize_tail(self.title, box - 5)
            if label:
                fill = max(0, inner - (1 + 2 + visible_width(label)))
                segments = [
                    Segment(left, self._border_style),
                    Segment(rule, self._border_style),
                    Segment(" ", self._border_style),
                    Segment(label, self._title_style),
                    Segment(" ", self._border_style),
                ]
                if fill:
                    segments.append(Segment(rule * fill, self._border_style))
                segments.append(Segment(right, self._border_style))
                return Line(segments)
        return Line.from_text(f"{left}{rule * inner}{right}", self._border_style)

    def _bottom_row(self, box: int) -> Line:
        """``\u2514\u2500\u2500\u2518``: the closing rule, corner to corner."""
        _left, _right, bottom_left, bottom_right, rule, _side = self._border
        return Line.from_text(
            f"{bottom_left}{rule * max(0, box - 2)}{bottom_right}", self._border_style
        )

    def _interior_row(self, content: Line, box: int, lead: int) -> Line:
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
            side = self._border[5]
            head = Segment(f"{side} ", self._border_style)
            tail = Segment(f" {side}", self._border_style)
        else:
            head = tail = Segment(" ")
        segments = [head, *content.segments]
        if fill:
            segments.append(Segment(" " * fill))
        segments.append(tail)
        return Line(segments)

    def _button_row(self, box: int, inner: int, row_index: int, lead: int) -> Line:
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
        return self._interior_row(content, box, lead)

    def revision(self) -> object:
        """The row cache's snapshot: every input the box's rows read.

        In order, the values are:

        * ``title`` -- embedded in the top rule (or gone with the frame);
        * ``width`` -- pins the box (`None`: the width-derived default);
        * ``frame`` -- whether the edge, the title and the bottom rule exist;
        * ``shade`` -- whether an interior row is filled solid to the edge;
        * ``align`` -- where the button row sits in the interior;
        * the border tuple and the two resolved bands (``_border_style`` /
          ``_title_style``) -- they paint every frame cell and the title;
        * every button's own :meth:`~motui.widgets.action.Button.revision`
          (label, ``focused`` -- which mirrors the cursor -- and its three
          bands): the button row is those rows joined and placed;
        * the body's snapshot: when the body is
          :class:`~motui.kernel.block.Revisioned` and answers one, its
          ``revision()`` **is** the body's contribution -- a value that
          moves with a streamed ``text =`` assignment on the first frame,
          not after a render.  Only a body outside the protocol (or one
          that switched its snapshot off with ``None``) falls back to the
          identity of the rows the last render answered (the ``Panel``
          precedent); such a body either answers the same row objects and
          compares stable, or rebuilds them every call and simply misses.

        The button cursor itself is covered by the buttons' ``focused``
        flags (``_sync_focus`` keeps them in step), and ``chosen`` /
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
            self._border,
            self._border_style,
            self._title_style,
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
    theme: Theme | None = None,
) -> Dialog:
    """The Yes/No confirmation: a plain message and two buttons (thin builder).

    Always the same shape -- an untitled box, a :class:`~motui.kernel.lines.Text`
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
        theme=theme,
    )


def prompt_dialog(
    title: str,
    *,
    placeholder: str = "",
    mask: str = "",
    confirm_text: str = "OK",
    cancel_text: str = "Cancel",
    style: Style | None = None,
    danger: bool = False,
    frame: bool = True,
    theme: Theme | None = None,
) -> Dialog:
    """The one-line prompt: a field body and the OK / Cancel row (thin builder).

    The prompt is a :class:`Dialog` whose body is a single-line
    :class:`~motui.widgets.textfield.Input`: ``title`` heads the box,
    ``placeholder`` is the field's empty-state hint and ``mask`` its
    display-only mask -- both forwarded verbatim, so the buffer's text stays
    plain however it renders.  ``confirm_text`` / ``cancel_text`` are the two
    buttons' labels (D3: the main action on the left, the cancel on the
    right), and ``style`` is the **field's** explicit band, resolved through
    the component charter -- explicit > ``theme`` field > :data:`DEFAULT_THEME
    <motui.kernel.theme.DEFAULT_THEME>` -- while the buttons keep their own
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
    :class:`~motui.interaction.modal.Modal` routes the keyboard body-first
    the key falls through to the button row and activates the focused button
    -- the modal's contract working exactly as intended.  The host reads the
    outcome the usual way: :attr:`Dialog.chosen` is ``"ok"`` when the confirm
    button was taken -- read the payload off the field,
    ``dialog.body.text`` -- and ``None`` for the cancel, an ``escape`` or a
    click outside.  There is deliberately no extra value on the prompt: the
    field is the payload, and the text is the host's to read and clear.
    """
    return Dialog(
        title=title,
        body=Input(placeholder=placeholder, mask=mask, style=style, theme=theme),
        buttons=[
            ButtonSpec(confirm_text, "ok"),
            ButtonSpec(cancel_text, None),
        ],
        danger=danger,
        frame=frame,
        theme=theme,
    )
