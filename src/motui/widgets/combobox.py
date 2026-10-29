"""ComboBox: an editable field over a filtered dropdown.

Wraps an :class:`Input` (``.input``) and an :class:`Autocomplete`
(``.list``) filtered by the field's text; ``open`` holds the dropdown state
and rendering is the field's rows.  Where the dropdown paints is the host's
business -- only kernel and widget layers are imported.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.cell import Surface
from ..kernel.document import Component
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.theme import Styles, Theme
from ..widgets.base import ResultWidget
from .autocomplete import Autocomplete
from .choice import Option
from .textfield import Input

__all__ = ["ComboBox"]


class ComboBox(ResultWidget):
    """An editable Input over a filtered dropdown -- the form's pick-or-type.

    Open, ``down``/``up`` step the list, ``enter`` takes the highlighted
    option's value (and writes its label into the field), ``escape`` closes
    empty; every other event belongs to the field.  ``render`` paints the
    field only -- the host mounts ``.list`` in a modal.  ``max_rows`` caps
    the list, ``max_drop_rows`` the open dropdown (the smaller wins).
    Pointer reports are declined.
    """

    #: The combo routes the field's keys through its own ``on_key``; the
    #: App registers the combo, not the internal Input/Autocomplete, as the
    #: target -- focus routing stays inside its subtree.
    #: The combo takes the focus ring, a pointer click (which docks the
    #: field's caret), and the activation verb (which takes the highlighted
    #: option while the dropdown is open).
    focusable = True
    clickable = True
    activatable = True
    focus_scope = True

    __slots__ = (
        "_last_count",
        "_last_width",
        "_open",
        "_skin_styles",
        "_skin_theme",
        "input",
        "list",
        "max_drop_rows",
        "max_rows",
    )

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        text: str = "",
        max_rows: int | None = 8,
        max_drop_rows: int | None = 6,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        self.max_rows = max_rows
        self.max_drop_rows = max_drop_rows
        #: The field: the component's own editable row (``.input``).
        self.input = Input(theme=theme, styles=styles, glyphs=glyphs)
        #: The dropdown's menu: the ``Autocomplete`` of the field's text.
        self.list = Autocomplete(
            options=list(options),
            max_rows=max_rows,
            theme=theme,
            styles=styles,
            glyphs=glyphs,
        )
        # ``Widget.__init__`` writes ``focused`` through this class's
        # delegating property, so the field must exist before it runs.
        super().__init__(theme, styles)
        # The explicit tree: the field and the dropdown are this wrapper's
        # children, so ``walk()`` covers the editable and the menu half.
        self.children = [self.input, self.list]
        # The old constructor default: the field starts focused.
        self.focused = True
        # The skin last forwarded to the children; a later assignment to
        # ``theme``/``styles`` on the combo re-skins them.
        self._skin_theme = theme
        self._skin_styles = styles
        if text:
            self.input.insert(text)
        self.list.set_query(self.input.text)
        #: Whether the dropdown is showing (the host's modal mirrors it).
        #: Assignment drives the open/close policy through the property.
        self._open = False
        # The field's last render: its width and row count are the geometry
        # :meth:`child_at` maps a cell through (the Container precedent).
        self._last_width = 0
        self._last_count = 0

    # -- the dropdown's lifecycle -----------------------------------------------

    @property
    def open(self) -> bool:
        """Whether the dropdown is showing (assignable state, no methods)."""
        return self._open

    @open.setter
    def open(self, value: bool) -> None:
        """Show or hide the dropdown.

        Opening clears stale results, applies the dropdown budget and
        re-filters; closing only hides, so a landed pick stays pending.
        """
        opened = bool(value)
        if opened:
            self._clear_result()
            self.list.max_rows = self._drop_rows()
            self.list.set_query(self.input.text)
        else:
            self.list.max_rows = self.max_rows
        self._open = opened
        self.touch()

    def toggle(self) -> bool:
        """Flip the dropdown's open state; ``True`` (the state always moves)."""
        self.open = not self.open
        return True

    def _drop_rows(self) -> int | None:
        """The open dropdown's window: the smaller of ``max_rows``/``max_drop_rows``."""
        if self.max_rows is None:
            return self.max_drop_rows
        if self.max_drop_rows is None:
            return self.max_rows
        return min(self.max_rows, self.max_drop_rows)

    # -- the event contract -----------------------------------------------------

    def on_key(self, event: Event) -> bool:
        """Route one event; ``True`` when consumed.

        Open, the four dropdown keys win; everything else is the field's,
        and a consumed field event re-filters the list.  Mouse reports are
        declined (the host's pointer tiers own them).
        """
        if isinstance(event, MouseEvent):
            return False  # the pointer tiers' door, never an editing key
        if self.open and isinstance(event, KeyEvent):
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
                self._clear_result()
                self.open = False
                return True
        if self.input.on_key(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def on_paste(self, event: PasteEvent) -> bool:
        """Feed one paste to the field; a consumed paste re-filters the list."""
        if self.input.on_paste(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def _take(self) -> None:
        """The ``enter``: the highlighted option's value, its label back in the field."""
        option = self.list.selected
        if option is None or not self.list.on_action("activate"):
            self._clear_result()  # nothing matched: the empty pick
            self.open = False
            return
        self._emit(self.list.take())
        self.input.clear()
        self.input.insert(option.label)
        self.list.set_query(self.input.text)  # the filter follows the field's new text
        self.open = False

    # -- the container surface ---------------------------------------------------

    @property
    def focused(self) -> bool:
        """The focus flag, delegated to the field ."""
        return self.input.focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self.input.focused = value

    def on_click(self, pos: Pos) -> bool:
        """Place the field's caret at a rendered cell (the click door)."""
        return self.input.on_click(pos)

    def activate(self) -> bool:
        """Open a closed dropdown, or take the open one's highlighted option."""
        if not self.open:
            self.open = True
            return True
        self._take()
        return True

    def on_action(self, name: str) -> bool:
        """``activate`` opens or takes the dropdown; other names belong to the field."""
        if name == "activate":
            return self.activate()
        return self.input.on_action(name)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a rendered cell to the field row it belongs to; pre-render cells answer ``None``."""
        if 0 <= row < self._last_count:
            return self.input, row, col
        return None

    def _skin(self) -> None:
        """Forward a theme/``Styles`` assigned on the combo to both children.

        Only acts when the combo's own skin moved, so direct child overrides
        keep working until then.
        """
        if (self.theme, self.styles) != (self._skin_theme, self._skin_styles):
            self.input.theme = self.theme
            self.input.styles = self.styles
            self.list.theme = self.theme
            self.list.styles = self.styles
            self._skin_theme = self.theme
            self._skin_styles = self.styles

    # -- the render ---------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """The field's rows; the untruncated count feeds ``child_at``."""
        self._skin()
        self._last_width = c.width
        rows = list(self.input.render(Constraints(width=c.width)))
        self._last_count = len(rows)
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"ComboBox({len(self.list.options)} options, open={self.open}, "
            f"text={self.input.text!r})"
        )
