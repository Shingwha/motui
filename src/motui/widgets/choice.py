"""Choice components: :class:`Option`, :class:`Select` and its variants.

``Select`` renders one :class:`Option` per row with a cursor, a scrolling
window and a counter; ``MultiSelect`` adds marks, and the form presets
``RadioGroup``/``CheckboxGroup`` render labels only.  Only the kernel is
imported; rendering resolves styles from the theme at call time.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from ..widgets.mark import MarkSet
from .strip import Keymap

__all__ = ["CheckboxGroup", "MultiSelect", "Option", "RadioGroup", "Select"]

#: Columns between the widest label and its description's column.
GAP = 2


@dataclass(frozen=True)
class Option:
    """One selectable entry: a label, a payload, and an optional description."""

    label: str
    value: object = None
    description: str = ""


def _option_value(option: Option) -> object:
    """The value a marked or chosen row carries: the payload, or its label."""
    return option.value if option.value is not None else option.label


def _options(labels: Sequence[str | Option]) -> list[Option]:
    """A label sequence as :class:`Option` values; a ``None`` payload falls back to the label."""
    return [
        Option(item.label, item.value if item.value is not None else item.label)
        if isinstance(item, Option)
        else Option(str(item), str(item))
        for item in labels
    ]


def _reject_descriptions(labels: Sequence[str | Option], group: str) -> None:
    """Refuse an :class:`Option` with a description: groups render labels only."""
    for item in labels:
        if isinstance(item, Option) and item.description:
            raise ValueError(
                f"{group} does not render Option.description, got "
                f"{item.description!r} for {item.label!r}"
            )


class Select(CursorWidget):
    """A vertical :class:`Option` list with a cursor, a window and a counter.

    ``index`` is the cursor row; ``max_rows`` caps the window and ``window``
    picks top-stick (default) or centred.  ``wrap`` cycles the ends; the
    data views clamp.  ``glyphs.cursor`` leads the cursor row and indents the
    others.  Activation leaves the chosen value pending for :meth:`take`,
    cleared by every cursor verb.  ``disabled``/``disabled_items`` gate
    gestures and render faint.  An unfocused cursor row dims its label and
    rides ``rows.inactive``; hover wins over cursor (D3).
    """

    __slots__ = (
        "_hover_row",
        "disabled",
        "disabled_items",
        "glyphs",
        "max_rows",
        "options",
        "title",
        "window",
        "wrap",
    )

    #: The class-level multi-selection switch: only :class:`MultiSelect` sets it.
    _multi = False

    #: The menu family owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The family's cursor table (a per-instance copy backs ``self.keymap``).
    keymap = Keymap(CURSOR_KEYMAP)

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int | None = 8,
        wrap: bool = True,
        window: bool = False,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.options = list(options)
        self.title = title
        self.max_rows = max_rows
        self.wrap = wrap
        self.window = window
        self.glyphs = glyphs
        #: The whole control refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The data rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)
        #: The focus flag the focus tier sets; the default matches the old
        #: constructor default so an unwired list keeps its cursor band.
        self.focused = True
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`on_hover`).
        self.hover = False
        # The option row the pointer is on (its data-row index), or ``None``;
        # written by ``on_hover``, read by ``render``.  ``None`` renders
        # byte-for-byte what the list always did.
        self._hover_row: int | None = None

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self._rows())

    def _entry_at(self, index: int) -> object | None:
        return self._rows()[index]

    def _cursor_disabled(self) -> Iterable[int]:
        return self.disabled_items

    def _cursor_wraps(self) -> bool:
        """``wrap=True`` cycles the ends; the data-view presets clamp."""
        return self.wrap

    def _cursor_enabled(self) -> bool:
        return not self.disabled

    def _page_size(self, size: int) -> int:
        """A page is the visible window (the whole list when uncapped)."""
        if self.max_rows is None or self.max_rows <= 0:
            return size
        return min(size, self.max_rows)

    def on_click(self, pos: Pos) -> bool:
        """Place the cursor on rendered row ``pos.y``; ``True`` on a hit.

        Title and counter rows carry no option; ``pos.x`` is ignored.
        Disabled controls and rows refuse.
        """
        if self.disabled:
            return False
        target = self._option_at(pos.y)
        if target is None or self._is_disabled(target):
            return False
        self.select(target)
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the option row under the pointer; True when the marking changed.

        Resolved like :meth:`on_click`; ``None`` clears it.
        """
        target = None if pos is None else self._option_at(pos.y)
        changed = target != self._hover_row
        if changed:
            self._hover_row = target
            self.touch()
        return changed

    # -- the verbs ---------------------------------------------------------------

    def activate(self) -> bool:
        """Take the row under the cursor (or toggle it on a multi-selection).

        Disabled controls, empty lists and disabled rows answer ``False``.
        """
        if not self._cursor_enabled():
            return False
        if self._multi:
            return self.toggle()
        selected = self.selected
        if selected is None or self._is_disabled(self.index):
            return False
        self._emit(self._chosen_of(selected))
        return True

    def toggle(self) -> bool:
        """Flip the cursor row's mark; a plain single-choice list cannot."""
        return False

    def _is_disabled(self, index: int) -> bool:
        return self.disabled or index in self.disabled_items

    # -- the rows ---------------------------------------------------------------

    def _rows(self) -> Sequence[Option]:
        """The rows the cursor walks and the window renders."""
        return self.options

    def _option_at(self, row: int) -> int | None:
        """The data-row index a rendered row carries, or ``None``.

        The shared mapping for clicks and hover: the optional title is row 0
        and the counter sits below the window; neither carries an option.
        """
        index = row - (1 if self.title else 0)
        if index < 0:
            return None
        start, stop = self._visible_range()
        target = start + index
        return target if start <= target < stop else None

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` rows rendered, at most ``max_rows``.

        Top-stick by default or centred with ``window=True``; the cursor row
        is always inside.
        """
        self._sync_cursor()
        cursor = self._cursor
        size = cursor.count if self.max_rows is None else self.max_rows
        return cursor.window(size, anchor="center" if self.window else "top")

    def _mark_width(self) -> int:
        """The mark column width: the pair's wider seat, or ``0`` when single-choice."""
        if not self._multi:
            return 0
        marked_glyph, unmarked_glyph = self._mark_pair()
        return max(
            seat_width(marked_glyph), seat_width(unmarked_glyph)
        )

    def _mark_pair(self) -> tuple[str, str]:
        return self.glyphs.check_on, self.glyphs.check_off

    def _chosen_of(self, option: Option) -> object:
        return _option_value(option)

    def _description_column(self) -> int:
        """The column every description starts at (``0`` when none is set).

        Measured over all options -- not the window -- so it holds still
        while scrolling; the mark column is part of the lead.
        """
        if not any(option.description for option in self.options):
            return 0
        widest = max(visible_width(option.label) for option in self.options)
        return seat_width(self.glyphs.cursor) + self._mark_width() + widest + GAP

    def _row(
        self,
        option: Option,
        current: bool,
        column: int,
        hovered: bool = False,
        marked: bool = False,
        disabled: bool = False,
    ) -> Line:
        """One row: marker, optional mark, label, description.

        Segments carry text styles only; the band is applied by the caller.
        An unfocused cursor label dims only when neither it nor its band has
        a background.
        """
        text = self.group("text")
        lead = seat_width(self.glyphs.cursor)
        if disabled:
            style = text.faint
        else:
            style = self.group("content").accent if current else text.base
            if current and not self.focused:
                band = self._band(current=True, hovered=hovered)
                if style.bg is None and band.bg is None:
                    style = style.merge(text.faint)  # unfocused: lose the weight
        segments = [
            Segment(seat(self.glyphs.cursor) if current else " " * lead, style),
        ]
        if self._multi:
            marked_glyph, unmarked_glyph = self._mark_pair()
            glyph, other = (
                (marked_glyph, unmarked_glyph)
                if marked
                else (unmarked_glyph, marked_glyph)
            )
            segments.append(Segment(pair_seat(glyph, other), style))
        segments.append(Segment(option.label, style))
        if option.description and column:
            pad = column - lead - self._mark_width() - visible_width(option.label)
            if pad > 0:
                segments.append(Segment(" " * pad))
            description_style = text.faint if disabled else text.muted
            segments.append(Segment(option.description, description_style))
        return Line(tuple(segments))

    def _counter(self) -> str:
        """The ``(i/n)`` row while the window scrolls; empty when it does not."""
        count = len(self._rows())
        cap = self.max_rows
        if cap is None or cap <= 0 or count <= cap:
            return ""
        return f"({self.index + 1}/{count})"

    def render(self, c: Constraints) -> Surface:
        """The window rows, title and counter, each on its resolved band.

        ``max_height`` truncates leading rows; styles are read per call;
        short rows keep their natural width (``Surface.clipped``).
        """
        text = self.group("text")
        rows = self._rows()
        start, stop = self._visible_range()
        cursor_index = self._cursor.index
        column = self._description_column()
        out: list[Line] = []
        if self.title:
            out.append(
                rest(
                    Line.from_text(self.title, text.base),
                    c.width,
                    self._band(False, False),
                )
            )
        for i in range(start, stop):
            current = i == cursor_index
            hovered = i == self._hover_row
            out.append(
                rest(
                    self._row(
                        rows[i],
                        current,
                        column,
                        hovered,
                        i in self.marked if self._multi else False,
                        self._is_disabled(i),
                    ),
                    c.width,
                    self._band(current, hovered),
                )
            )
        counter = self._counter()
        if counter:
            out.append(
                rest(
                    Line.from_text(counter, text.muted),
                    c.width,
                    self._band(False, False),
                )
            )
        if c.max_height is not None:
            out = out[: c.max_height]
        return Surface.clipped(out, c.width)

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        return self.group("rows").band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self.index})"


class MultiSelect(Select):
    """A :class:`Select` whose rows carry marks and whose result is the marked set.

    ``marked`` holds data-row indices; ``toggle`` flips the cursor row's
    mark and activates it.  The pending result is the marked values in row
    order (nothing pending while nothing is marked).
    """

    __slots__ = ("marked",)

    #: This list is a multiple selection.
    _multi = True

    #: The family table plus the marking key.
    keymap = Keymap({**CURSOR_KEYMAP, "space": "toggle"})

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int | None = 8,
        wrap: bool = True,
        glyphs: Glyphs = GLYPHS,
        marked: Iterable[int] = (),
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(
            options,
            title=title,
            max_rows=max_rows,
            wrap=wrap,
            glyphs=glyphs,
            disabled=disabled,
            disabled_items=disabled_items,
            theme=theme,
            styles=styles,
        )
        #: The marked rows (data-row indices) :meth:`toggle` flips.
        self.marked = MarkSet(marked)
        self._sync_result()

    def toggle(self) -> bool:
        """Flip the cursor row's mark; ``True`` when one flipped.

        The mark change recomputes the pending result.  Disabled controls
        and rows refuse.
        """
        if not self._cursor_enabled():
            return False
        if self.selected is None or self._is_disabled(self.index):
            return False
        self.marked.toggle(self.index)
        self._sync_result()
        self.touch()
        return True

    def _sync_result(self) -> None:
        """Recompute the pending result: marked values in row order.

        An empty selection clears the slot rather than emitting ``None``.
        """
        values = [
            _option_value(option)
            for index, option in enumerate(self._rows())
            if index in self.marked
        ]
        if values:
            self._emit(values)
        else:
            self._clear_result()

    def __repr__(self) -> str:
        return f"MultiSelect({self.options!r}, index={self.index})"


class _FormGroup:
    """The form groups' shared half: label rows and the form band rule."""

    __slots__ = ()

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The form band rule: the hover band wins, then the focused selection's."""
        rows = self.group("rows")
        if hovered:
            return rows.hover
        if current and self.focused:
            return rows.active
        return rows.base


class RadioGroup(_FormGroup, Select):
    """The single-choice group: one ``(•)`` marker on one row.

    A ``Select`` preset with ``wrap=False`` and the radio pair; an unfocused
    pick rests on the ground, a focused one on ``rows.active``.
    ``options`` takes strings or :class:`Option`; a description is a
    construction error.  Activation leaves the option's value pending
    (label when the payload is ``None``).
    """

    __slots__ = ()

    def __init__(
        self,
        options: Sequence[str | Option],
        *,
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        _reject_descriptions(options, "RadioGroup")
        super().__init__(
            _options(options),
            max_rows=None,
            wrap=False,
            glyphs=glyphs,
            disabled=disabled,
            disabled_items=disabled_items,
            theme=theme,
            styles=styles,
        )
        # The old constructor default: a form group starts unfocused.
        self.focused = False
        # The constructor's explicit index is clamped **without** the
        # disabled refusal or the pending clear: it is initial state, not a
        # cursor verb.
        self._sync_cursor()
        self._cursor.index = self._cursor.clamp(index)

    def _chosen_of(self, option: Option) -> object:
        return _option_value(option)

    def _row(
        self,
        option: Option,
        current: bool,
        column: int,
        hovered: bool = False,
        marked: bool = False,
        disabled: bool = False,
    ) -> Line:
        """One radio row: the filled or empty marker pair, then the label."""
        text = self.group("text")
        mark_style = text.faint if disabled else (
            self.group("content").accent if current else text.base
        )
        label_style = text.faint if disabled else text.base
        glyph, other = (
            (self.glyphs.radio_on, self.glyphs.radio_off)
            if current
            else (self.glyphs.radio_off, self.glyphs.radio_on)
        )
        mark = pair_seat(glyph, other)
        return Line(
            (Segment(mark, mark_style), Segment(option.label, label_style))
        )

    def __repr__(self) -> str:
        labels = [option.label for option in self.options]
        return f"RadioGroup({labels!r}, index={self.index}, focused={self.focused})"


class CheckboxGroup(_FormGroup, MultiSelect):
    """The multiple-choice group: a ``[x]`` / ``[ ]`` mark on every row.

    A ``MultiSelect`` preset with ``wrap=False`` and the form bands; the
    pending result is the marked rows' values in row order.  ``options``
    takes strings or :class:`Option`; a description is a construction error.
    A click moves the cursor and flips the row's mark.
    """

    __slots__ = ()

    def __init__(
        self,
        options: Sequence[str | Option],
        *,
        marked: Iterable[int] = (),
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        _reject_descriptions(options, "CheckboxGroup")
        super().__init__(
            _options(options),
            max_rows=None,
            wrap=False,
            marked=marked,
            glyphs=glyphs,
            disabled=disabled,
            disabled_items=disabled_items,
            theme=theme,
            styles=styles,
        )
        # The old constructor default: a form group starts unfocused.
        self.focused = False
        # The constructor's explicit index is clamped **without** the
        # disabled refusal or the pending clear: it is initial state, not a
        # cursor verb, and the marked result is already installed above.
        self._sync_cursor()
        self._cursor.index = self._cursor.clamp(index)

    def on_click(self, pos: Pos) -> bool:
        """Move the cursor onto a row and flip its mark; ``True`` on a hit.

        The multi-select pointer gesture; ``pos.x`` is ignored and disabled
        rows or controls miss.
        """
        if self.disabled:
            return False
        target = self._option_at(pos.y)
        if target is None or self._is_disabled(target):
            return False
        self.select(target)
        self.toggle()
        return True

    def _row(
        self,
        option: Option,
        current: bool,
        column: int,
        hovered: bool = False,
        marked: bool = False,
        disabled: bool = False,
    ) -> Line:
        """One check row: the marker seat, the mark, the label."""
        text = self.group("text")
        mark_style = text.faint if disabled else (
            self.group("content").accent if current else text.base
        )
        label_style = text.faint if disabled else text.base
        lead = seat_width(self.glyphs.cursor)
        marked_glyph, unmarked_glyph = self._mark_pair()
        glyph, other = (
            (marked_glyph, unmarked_glyph)
            if marked
            else (unmarked_glyph, marked_glyph)
        )
        segments = [
            Segment(seat(self.glyphs.cursor) if current else " " * lead, mark_style),
            Segment(pair_seat(glyph, other), mark_style),
            Segment(option.label, label_style),
        ]
        return Line(tuple(segments))

    def __repr__(self) -> str:
        labels = [option.label for option in self.options]
        return f"CheckboxGroup({labels!r}, index={self.index})"
