"""ComboBox: an editable field over a filtered dropdown.

:class:`ComboBox` is the form's pick-or-type -- the one component of the
family that is a *field* and a *menu* at once: the field is the component's
own :class:`~motui.widgets.textfield.Input` (:attr:`ComboBox.input`) and the
menu is an :class:`~motui.widgets.autocomplete.Autocomplete`
(:attr:`ComboBox.list`) filtered by the field's text.  The component lays the
field's rows out and holds the dropdown's own state (:attr:`ComboBox.is_open`);
where the dropdown goes on screen is the host's business -- the class
docstring's recipe mounts a :class:`~motui.interaction.modal.Modal` over
:attr:`ComboBox.list`, one row under the field.

The combo is a wrapper, so it speaks the whole container vocabulary: a
pointer cell maps to the field through :meth:`ComboBox.child_at`, the focus
flag and the click delegate to the field, and :meth:`ComboBox.revision`
covers every input its rows and its result read.

Only the kernel and this layer are imported: no ``app``, no ``interaction``,
no ``Modal``.  A widget lays out rows; the modal owns the screen.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.block import Component
from ..kernel.events import Event, KeyEvent, MouseEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.lines import Line
from ..kernel.theme import Theme, Themed
from .autocomplete import Autocomplete
from .choice import Option
from .textfield import Input

__all__ = ["ComboBox"]


class ComboBox(Themed):
    """An editable Input over a filtered dropdown -- the form's pick-or-type.

    ``options`` are the candidate :class:`~motui.widgets.choice.Option` rows;
    the field is the component's own
    :class:`~motui.widgets.textfield.Input` (``.input``), and while the
    dropdown is open the ``Autocomplete`` of the field's text (``.list``) is
    painted under the field's row.  ``open()``/``close()``/``is_open`` drive
    it; :meth:`handle` routes: ``down``/``up`` step the list (consumed, the
    cursor wraps like every menu), ``enter`` takes the highlighted option's
    value as the one-shot result, closes and writes the option's label back
    into the field, ``escape`` closes with nothing pending; every
    other event is the field's, and a field change re-filters the list.  A
    pointer report is the one event that is nobody's here: it is declined,
    so the mounted modal keeps the mouse it owns (a ``MouseEvent`` is a
    sibling of ``KeyEvent``, never one, so its button names are not editing
    doors).  A :class:`~motui.kernel.events.PasteEvent` is never read as a
    key: the open dropdown hands it straight to the field (the P0 this wave
    fixed).  The result is read once through :meth:`take_result`.
    ``render(width)`` is the field's rows; the dropdown paints through a
    host-mounted :class:`~motui.interaction.modal.Modal` -- a widget lays
    out rows, the modal owns the screen:

    1. the host mounts it once -- ``drop = Modal(tui, combo.list,
       anchor=(field_row + 1, field_col))`` -- the anchor put one row under
       the field, so the dropdown hangs where a combobox's list belongs;
    2. the host routes ``combo.handle(event)`` **before** ``drop.handle``
       (the combo takes the keyboard while open, the modal keeps everything
       it declines: the mouse, the scrim, the dismissal);
    3. opening and closing stay in step -- the host calls ``drop.open()``
       with ``combo.open()`` and syncs the other way after routing, so a
       click outside the panel (the modal's own dismissal) closes the
       dropdown with it.

    The pending result is the taken option's value (its label when the
    payload is ``None``), or ``None``: an ``escape``, a dismissal, or an
    activation that matched nothing.  ``max_rows`` is the list's own window
    (the family knob -- what a host embedding ``.list`` standalone gets) and
    ``max_drop_rows`` the dropdown's own budget: while the dropdown is open
    the list renders the smaller of the two.  ``text`` seeds the field, and
    the list opens on the matches of it.
    """

    __slots__ = (
        "_last_count",
        "_last_width",
        "_pending",
        "input",
        "is_open",
        "list",
        "max_drop_rows",
        "max_rows",
        "theme",
    )

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        text: str = "",
        max_rows: int | None = 8,
        theme: Theme | None = None,
        max_drop_rows: int | None = 6,
        glyphs: Glyphs = GLYPHS,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.max_rows = max_rows
        self.max_drop_rows = max_drop_rows
        #: The field: the component's own editable row (``.input``).
        self.input = Input(theme=theme, glyphs=glyphs)
        #: The dropdown's menu: the ``Autocomplete`` of the field's text.
        self.list = Autocomplete(
            options=list(options), max_rows=max_rows, theme=theme, glyphs=glyphs
        )
        if text:
            self.input.insert(text)
        self.list.set_query(self.input.text)
        #: The pending pick: the taken option's value, read once through
        #: :meth:`take_result`.
        self._pending: object | None = None
        #: Whether the dropdown is showing (the host's modal mirrors it).
        self.is_open = False
        # The field's last render: its width and row count are the geometry
        # :meth:`child_at` maps a cell through (the Container precedent).
        self._last_width = 0
        self._last_count = 0

    # -- the dropdown's lifecycle -----------------------------------------------

    def open(self) -> None:
        """Show the dropdown: a fresh pick, the list filtered on the field.

        The stale result goes with it, so a fresh visit never inherits an
        earlier pick; the list's window becomes the dropdown's budget (see
        the class docstring) and its matches are recomputed from whatever
        the field holds now.
        """
        self._pending = None
        self.list.max_rows = self._drop_rows()
        self.list.set_query(self.input.text)
        self.is_open = True

    def close(self) -> None:
        """Hide the dropdown; a pick already landed stays pending."""
        self.is_open = False
        self.list.max_rows = self.max_rows

    def _drop_rows(self) -> int | None:
        """The window the dropdown renders: the two budgets' smaller.

        ``max_rows`` is the list's own cap and ``max_drop_rows`` the
        dropdown's; ``None`` on either means "every row", and the smaller of
        the two is what the open dropdown renders -- the list's own cap is
        what a host embedding :attr:`list` standalone keeps.
        """
        if self.max_rows is None:
            return self.max_drop_rows
        if self.max_drop_rows is None:
            return self.max_rows
        return min(self.max_rows, self.max_drop_rows)

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Route one event; ``True`` when it was consumed.

        Open, the dropdown's four keys come first: ``down``/``up`` step the
        list (the menu's own wrap), ``enter`` takes the highlighted option
        (:meth:`_take`: its value pending, its label back into the field,
        the dropdown closed) and ``escape`` closes with nothing pending.
        Everything else is the field's -- a printable, an editing key, a
        :class:`~motui.kernel.events.PasteEvent` -- and a consumed field
        event re-filters the list on the new text, open or closed.  A paste
        is never inspected for a ``key`` (it has none): it goes straight to
        the field.  What the field declines is declined here too, so the
        host's own dispatch still gets its turn; a pointer report is
        declined outright (the host's tiers own the mouse, the mounted modal
        above all).
        """
        if isinstance(event, MouseEvent):
            return False  # the pointer tiers' door, never an editing key
        if self.is_open and isinstance(event, KeyEvent):
            name = event.key
            if name == "down":
                self.list.move(1)
                return True
            if name == "up":
                self.list.move(-1)
                return True
            if name == "enter":
                self._take()
                return True
            if name == "escape":
                self._pending = None
                self.close()
                return True
        if self.input.handle(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def _take(self) -> None:
        """The ``enter``: the highlighted option's value, its label back in the field."""
        if not self.list.activate():
            self._pending = None  # nothing matched: the empty pick
            self.close()
            return
        option = self.list.take_result()  # the menu's one-shot pick is the combo's to carry
        if not isinstance(option, Option):
            self._pending = None
            self.close()
            return
        self._pending = option.value if option.value is not None else option.label
        self.input.clear()
        self.input.insert(option.label)
        self.list.set_query(self.input.text)  # the filter follows the field's new text
        self.close()

    def take_result(self) -> object | None:
        """Read the pending pick once and clear it (the ``Resultful`` door)."""
        value = self._pending
        self._pending = None
        return value

    # -- the container surface ---------------------------------------------------

    @property
    def focused(self) -> bool:
        """The focus flag, delegated to the field (``Focusable``)."""
        return self.input.focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self.input.focused = value

    def click(self, row: int, col: int) -> bool:
        """Place the field's caret at a rendered cell (``Clickable``)."""
        return self.input.click(row, col)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map one of the combo's own cells to the input row it belongs to.

        The combo adds no chrome of its own: its rows **are** the field's
        rows, so every cell of the last render maps to ``(self.input, row,
        col)``.  Like every container the geometry is the last render's --
        before the first render there are no rows and every cell is
        ``None``.
        """
        if 0 <= row < self._last_count:
            return self.input, row, col
        return None

    def revision(self) -> object:
        """The ``Revisioned`` snapshot of every row and result input.

        The field's own snapshot (text, cursor, styles, read-only state and
        policy), the open flag, the pending result, the option universe and
        the two window budgets.  The dropdown's rows are painted by the
        host's modal, but the combo's own render is the field, so this is
        the value a block cache keys on.
        """
        return (
            self.input.revision(),
            self.is_open,
            self._pending,
            tuple(self.list.options),
            self.max_rows,
            self.max_drop_rows,
        )

    # -- the render ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        """The field's rows -- the dropdown paints through the host's modal."""
        self._last_width = width
        rows = self.input.render(width)
        self._last_count = len(rows)
        return rows

    def __repr__(self) -> str:
        return (
            f"ComboBox({len(self.list.options)} options, open={self.is_open}, "
            f"text={self.input.text!r})"
        )
