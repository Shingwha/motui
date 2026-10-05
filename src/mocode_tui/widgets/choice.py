"""Choice components: :class:`Option`, :class:`Select` and :class:`Confirm`.

``Select`` is a keyboard-driven (by the W4 driver) vertical list: it owns an
``index`` and renders the current row with a ``"\\u276e "`` marker inside one
continuous styled band, hints trailing in a dim style.  ``Confirm`` is the
Yes/No specialization used for destructive confirmations.  Only the kernel is
imported; no key is read here -- the editing entry points are plain methods
that the driver calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.lines import Line, Segment
from ..core.style import DIM, ERROR, NONE, SELECTION, Style

__all__ = ["Confirm", "Option", "Select"]


@dataclass(frozen=True)
class Option:
    """One selectable entry: a label, a payload, and an optional hint."""

    label: str
    value: object = None
    hint: str = ""


class Select:
    """A vertical list of :class:`Option` values with a moving cursor.

    ``index`` clamps inside ``0..len(options)-1`` (``move`` never wraps), and
    ``selected`` is the option under it (``None`` when the list is empty).
    Rendering yields an optional title row plus one row per option; the
    selected row starts with ``"\\u276e "`` and forms a single segment in
    ``selected_style`` (marker, label and hint together), while the other
    rows carry their label in ``label_style`` (``NONE`` by default) with
    ``hint`` trailing in ``hint_style``.
    """

    __slots__ = (
        "hint_style",
        "index",
        "label_style",
        "options",
        "selected_style",
        "title",
        "title_style",
    )

    def __init__(
        self,
        options: list[Option],
        *,
        title: str = "",
        label_style: Style = NONE,
        selected_style: Style = SELECTION,
        hint_style: Style = DIM,
        title_style: Style = NONE,
    ) -> None:
        self.options = list(options)
        self.title = title
        self.label_style = label_style
        self.selected_style = selected_style
        self.hint_style = hint_style
        self.title_style = title_style
        self.index = 0

    def move(self, delta: int) -> bool:
        """Move the cursor by ``delta`` rows, clamped; True when it moved."""
        if not self.options:
            return False
        target = min(max(self.index + delta, 0), len(self.options) - 1)
        moved = target != self.index
        self.index = target
        return moved

    @property
    def selected(self) -> Option | None:
        """The option under the cursor, or ``None`` for an empty list."""
        if not self.options:
            return None
        return self.options[self.index]

    def render(self, width: int) -> list[Line]:
        out: list[Line] = []
        if self.title:
            out.append(Line.from_text(self.title, self.title_style).fit(width))
        for i, option in enumerate(self.options):
            out.append(self._option_row(i, option).fit(width))
        return out

    def _option_row(self, index: int, option: Option) -> Line:
        if index == self.index:
            row = "\u276e " + option.label
            if option.hint:
                row += "  " + option.hint
            return Line((Segment(row, self.selected_style),))
        segments = [Segment("  " + option.label, self.label_style)]
        if option.hint:
            segments.append(Segment("  " + option.hint, self.hint_style))
        return Line(segments)

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self.index})"


class Confirm:
    """A Yes/No :class:`Select` specialization for confirmations.

    The options are ``Option("Yes", True)`` and ``Option("No", False)``; with
    ``danger=True`` the message renders as the title in
    :data:`~mocode_tui.core.style.ERROR` style.  ``index``/``selected``/``move``
    forward to the inner select.
    """

    __slots__ = ("_select", "danger", "message")

    def __init__(self, message: str, *, danger: bool = False) -> None:
        self.message = message
        self.danger = danger
        self._select = Select(
            [Option("Yes", True), Option("No", False)],
            title=message,
            title_style=ERROR if danger else NONE,
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

    def render(self, width: int) -> list[Line]:
        return self._select.render(width)

    def __repr__(self) -> str:
        return f"Confirm({self.message!r}, danger={self.danger})"
