"""Choice components: :class:`Option`, :class:`Select` and :class:`Confirm`.

``Select`` is a keyboard-driven (by the W4 driver) vertical list: it owns an
``index`` and renders the current row with a ``"\\u276e "`` marker inside one
continuous styled band, hints trailing in a dim style.  ``Confirm`` is the
Yes/No specialization used for destructive confirmations.  Only the kernel is
imported; no key is read here -- the editing entry points are plain methods
that the driver calls.  The row styles fall back to the theme's
``selection``/``dim`` (and ``error`` for a dangerous ``Confirm``) when not
given explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["Confirm", "Option", "Select"]


@dataclass(frozen=True)
class Option:
    """One selectable entry: a label, a payload, and an optional hint."""

    label: str
    value: object = None
    hint: str = ""


def _option_row(
    option: Option,
    current: bool,
    label_style: Style,
    selected_style: Style,
    hint_style: Style,
) -> Line:
    """One option row: ``"\\u276e " + label`` under the cursor, ``"  "`` body elsewhere.

    The selected row forms one continuous segment in ``selected_style``
    (marker, label and hint together); the other rows carry their label in
    ``label_style`` with ``hint`` trailing in ``hint_style``.  Shared by
    :class:`Select` and :class:`~mocode_tui.widgets.autocomplete.Autocomplete`.
    """
    if current:
        row = "\u276e " + option.label
        if option.hint:
            row += "  " + option.hint
        return Line((Segment(row, selected_style),))
    segments = [Segment("  " + option.label, label_style)]
    if option.hint:
        segments.append(Segment("  " + option.hint, hint_style))
    return Line(segments)


def _clamped_move(index: int, count: int, delta: int) -> tuple[int, bool]:
    """Move a cursor ``delta`` rows inside ``count`` options, clamped.

    Never wraps; an empty list (``count <= 0``) moves nowhere.  Returns the
    new index and whether it changed.
    """
    if count <= 0:
        return index, False
    target = min(max(index + delta, 0), count - 1)
    return target, target != index


class Select:
    """A vertical list of :class:`Option` values with a moving cursor.

    ``index`` clamps inside ``0..len(options)-1`` (``move`` never wraps), and
    ``selected`` is the option under it (``None`` when the list is empty).
    Rendering yields an optional title row plus one row per option; the
    selected row starts with ``"\\u276e "`` and forms a single segment in
    ``selected_style`` (marker, label and hint together), while the other
    rows carry their label in ``label_style`` (``NONE`` by default) with
    ``hint`` trailing in ``hint_style``.  ``selected_style``/``hint_style``
    fall back to the theme's ``selection``/``dim``.  A click (:meth:`click`)
    places the cursor on the option under a rendered row.
    """

    __slots__ = (
        "hint_style",
        "index",
        "label_style",
        "options",
        "selected_style",
        "theme",
        "title",
        "title_style",
    )

    def __init__(
        self,
        options: list[Option],
        *,
        title: str = "",
        label_style: Style | None = None,
        selected_style: Style | None = None,
        hint_style: Style | None = None,
        title_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        self.options = list(options)
        self.title = title
        self.label_style = label_style
        self.selected_style = selected_style
        self.hint_style = hint_style
        self.title_style = title_style
        self.theme = theme
        self.index = 0

    def move(self, delta: int) -> bool:
        """Move the cursor by ``delta`` rows, clamped; True when it moved."""
        self.index, moved = _clamped_move(self.index, len(self.options), delta)
        return moved

    def click(self, row: int) -> bool:
        """Place the cursor on the option at block row ``row``; True on a hit.

        ``row`` is a 0-based row of this component's own render -- what
        :meth:`~mocode_tui.app.TUI.hit_test` reports -- so the title
        row (when there is one) is row 0 and option ``i`` sits at row
        ``i + (1 if self.title else 0)``.  A row that is an option answers
        ``True`` and moves the cursor there (even when it already was);
        the title row and any row past the last option answer ``False``
        and leave the cursor alone.
        """
        index = row - (1 if self.title else 0)
        if not 0 <= index < len(self.options):
            return False
        self.index = index
        return True

    @property
    def selected(self) -> Option | None:
        """The option under the cursor, or ``None`` for an empty list."""
        if not self.options:
            return None
        return self.options[self.index]

    def render(self, width: int) -> list[Line]:
        theme = self.theme or DEFAULT_THEME
        title_style = self.title_style if self.title_style is not None else NONE
        label_style = self.label_style if self.label_style is not None else NONE
        selected_style = (
            self.selected_style if self.selected_style is not None else theme.selection
        )
        hint_style = self.hint_style if self.hint_style is not None else theme.dim
        out: list[Line] = []
        if self.title:
            out.append(Line.from_text(self.title, title_style).fit(width))
        for i, option in enumerate(self.options):
            row = _option_row(option, i == self.index, label_style, selected_style, hint_style)
            out.append(row.fit(width))
        return out

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self.index})"


class Confirm:
    """A Yes/No :class:`Select` specialization for confirmations.

    The options are ``Option("Yes", True)`` and ``Option("No", False)``; with
    ``danger=True`` the message renders as the title in the theme's ``error``
    style.  ``index``/``selected``/``move``/``click`` forward to the inner
    select.
    """

    __slots__ = ("_select", "danger", "message", "theme")

    def __init__(self, message: str, *, danger: bool = False, theme: Theme | None = None) -> None:
        self.message = message
        self.danger = danger
        self.theme = theme
        base = theme or DEFAULT_THEME
        self._select = Select(
            [Option("Yes", True), Option("No", False)],
            title=message,
            title_style=base.error if danger else None,
            theme=theme,
        )

    @property
    def index(self) -> int:
        return self._select.index

    @property
    def selected(self) -> Option | None:
        return self._select.selected

    def move(self, delta: int) -> bool:
        """Move between Yes/No, clamped (never wraps)."""
        return self._select.move(delta)

    def click(self, row: int) -> bool:
        """Select Yes/No at block row ``row``; the message row is not an option."""
        return self._select.click(row)

    def render(self, width: int) -> list[Line]:
        return self._select.render(width)

    def __repr__(self) -> str:
        return f"Confirm({self.message!r}, danger={self.danger})"
