"""Choice components: :class:`Option`, :class:`Select` and its variants.

``Select`` is the toolkit's one cursor-over-rows component: one
:class:`Option` per row, one cursor, one scroll window.  A row reads
``"\u2192 label"`` under the cursor and ``"  label"`` elsewhere -- the cursor
row in the theme's ``accent``, the others plain -- and every option's
``description`` sits in one column to the right, measured over the whole
option list so the column never jumps while the cursor scrolls or a filter
narrows the rows.  A list longer than ``max_rows`` renders a scrolling window
(the cursor row is always visible) and a ``(i/n)`` counter row beneath it;
the window's arithmetic is :class:`~motui.kernel.cursor.CursorWindow`'s, the
same value ``List`` renders through.  Styles resolve once, at construction,
as explicit > theme field (``accent`` / ``dim`` / ``error``) >
``DEFAULT_THEME``.  Only the kernel is imported; no key is read here -- the
editing entry points are plain methods a host routes to.  ``focused`` is the
focus flag the focus tier sets (an unfocused cursor row renders
``selected_style.merge(theme.dim)``), and ``hover_at`` is the pointer tier's
row marking (the marked row merges the theme's ``hover``).

Five knobs express every variant of the family (D1), so there is one base
class and no second copy of the cursor/window arithmetic:

* ``wrap`` -- a menu cycles its ends (``True``, the default), a data view
  clamps (``False``);
* ``marker`` -- the cursor row's leading glyph;
* ``commit`` -- a form control (``True``) writes the row it landed on into
  ``chosen`` as it moves or is clicked; a menu (``False``, the default) only
  writes on :meth:`Select.activate`;
* ``multi`` -- a multiple-selection list (``True``): the rows carry the
  ``[x] ``/``[ ] `` mark of :class:`~motui.kernel.mark.MarkSet`,
  :meth:`Select.toggle` flips the cursor row's mark, and ``chosen`` is the
  marked values;
* ``window`` -- ``max_rows`` means a top-stick window (``False``, the
  default) or a centred one (``True``, the data view's policy).

:class:`Radio` and :class:`CheckGroup` are the two presets a form is built
from -- single choice with a ``(\u2022)`` marker, multiple choice with the
marks -- and take their labels as plain strings or as :class:`Option`
entries, the same vocabulary the menu family speaks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Sequence

from ..kernel.cursor import CursorWindow
from ..kernel.lines import Line, Segment
from ..kernel.mark import MarkSet, mark_prefix
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed

__all__ = ["CheckGroup", "Option", "Radio", "Select"]

#: The cursor row's leading arrow (the classic menu pointer).
MARKER = "\u2192"

#: Columns between the widest label and its description's column.
GAP = 2

#: The empty radio marker: unselected rows lead with it, four cells wide.
EMPTY_MARK = "( ) "

#: The filled radio marker: the one row that is the group's selection leads with it.
FILLED_MARK = "(\u2022) "


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
    """A label sequence as :class:`Option` values, one per row.

    A plain string is the label *and* the value; an :class:`Option` keeps
    its label and carries its payload as the value -- or its label when the
    payload is ``None``, so ``chosen`` never reads ``None`` for a named row.
    The group presets (:class:`Radio` / :class:`CheckGroup`) render labels
    only, so an option's description is not part of their rows.
    """
    return [
        Option(item.label, item.value if item.value is not None else item.label)
        if isinstance(item, Option)
        else Option(str(item), str(item))
        for item in labels
    ]


class Select(Themed):
    """A vertical :class:`Option` list with a cursor, a window and a counter.

    ``index`` is the cursor's row: reading it is always a row of the current
    rows, and assigning clamps into range (an empty list keeps ``0``).
    :meth:`_rows` is the one subclass seam -- the rows the cursor walks and
    the window renders; :class:`~motui.widgets.autocomplete.Autocomplete`
    overrides it with its filtered matches, everything else is shared.

    ``max_rows`` caps the rendered window (``None`` renders every row; a
    non-positive cap renders none) and ``window`` picks its policy: the
    default window hangs at the top while the cursor sits inside the first
    ``max_rows`` rows, then scrolls one row per step with the cursor row as
    its last -- the selected row is always on screen; ``window=True``
    centres the cursor instead, the data view's policy.  Both are
    :class:`~motui.kernel.cursor.CursorWindow`'s arithmetic.  ``wrap`` makes
    :meth:`move` step from the last row to the first (and back) instead of
    stopping at the ends.  ``marker`` leads the cursor row; the other rows
    are indented by its width.  A counter row ``(i/n)`` (the cursor's
    1-based row over the row count) is rendered only while the window
    actually scrolls, so short lists stay clean.

    :meth:`activate` is the list's activation: it takes the option under
    the cursor into :attr:`chosen` and answers whether there was one to
    take.  A host calls it on the return key, reads ``chosen`` once, then
    resets it to ``None``; :meth:`move` and
    :meth:`~motui.widgets.autocomplete.Autocomplete.set_query` clear
    it, so a stale pick never survives the next keystroke.  Two knobs
    change that contract (D1): ``commit=True`` writes the row the cursor
    landed on as it moves or is clicked (the cursor *is* the choice), and
    ``multi=True`` turns the list into a multiple selection -- the rows
    carry the ``[x] ``/``[ ] `` mark (:attr:`marked`), :meth:`toggle` (and
    an :meth:`activate`, which is the same gesture) flips the cursor row's
    mark, and :attr:`chosen` is recomputed as the marked rows' values, in
    row order (``None`` while nothing is marked).

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.block.Focusable`): while it is ``True`` the
    cursor row renders in ``selected_style``; while it is ``False`` that
    style is merged with the theme's ``dim`` -- the cursor stays legible
    but loses weight, and nothing else on the row changes (the
    description column keeps its own ``dim``).

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`);
    :meth:`hover_at` marks the option row under the pointer -- resolved
    through the same arithmetic :meth:`click` uses -- and the marked row
    renders its existing style merged with the theme's ``hover``.  The
    marking lives in one private row index that starts ``None``, so an
    un-hovered list renders byte-for-byte what it always did.
    """

    __slots__ = (
        "_description_style",
        "_dim",
        "_hover_row",
        "_hover_style",
        "_index",
        "_label_style",
        "_selected_style",
        "_title_style",
        "chosen",
        "commit",
        "focused",
        "hover",
        "marked",
        "max_rows",
        "marker",
        "multi",
        "options",
        "theme",
        "title",
        "window",
        "wrap",
    )

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int | None = 8,
        wrap: bool = True,
        marker: str = MARKER,
        commit: bool = False,
        multi: bool = False,
        marked: Iterable[int] = (),
        window: bool = False,
        focused: bool = True,
        label_style: Style | None = None,
        selected_style: Style | None = None,
        description_style: Style | None = None,
        title_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.options = list(options)
        self.title = title
        self.max_rows = max_rows
        self.wrap = wrap
        self.marker = marker
        self.commit = commit
        self.multi = multi
        self.window = window
        #: The marked rows (data-row indices) the ``multi`` knob reads and
        #: :meth:`toggle` flips; a single-choice list never marks.
        self.marked = MarkSet(marked)
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        # The cursor starts on the first row; ``_index`` is written directly
        # because the setter reads ``_rows()``, which a subclass may not have
        # armed yet at this point.
        self._index = 0
        # The option row the pointer is on (its data-row index), or ``None``;
        # written by ``hover_at``, read by ``render``.  ``None`` renders
        # byte-for-byte what the list always did.
        self._hover_row: int | None = None
        #: The pending activation: written by ``activate`` and, under the
        #: ``commit`` knob, by every move/click that landed on a row; read
        #: once by the host -- and, under ``multi``, the marked values
        #: themselves rather than a pending pick.
        self.chosen: Option | list[object] | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._label_style = label_style if label_style is not None else NONE
        self._selected_style = self._pick(selected_style, "accent")
        self._description_style = self._pick(description_style, "dim")
        self._title_style = title_style if title_style is not None else NONE
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "hover")
        if self.multi:
            self._sync_chosen()

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor's row of :meth:`_rows` (``0`` for an empty list)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = self._cursor().clamp(value)

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` rows; ``True`` when it moved.

        Wrapping (the default) steps off the last row onto the first, and off
        the first onto the last; ``wrap=False`` clamps at the ends instead.
        An empty list moves nowhere.  What the step writes into
        :attr:`chosen` follows the knobs: a menu clears its pending pick (a
        stale activation never survives the next keystroke), a
        ``commit=True`` form control writes the row it landed on, and a
        ``multi=True`` one leaves ``chosen`` to the marks.
        """
        if not (self.commit or self.multi):
            self.chosen = None
        count = len(self._rows())
        if count <= 0:
            return False
        target = self._cursor().move(delta, self.wrap)
        moved = target != self._index
        self._index = target
        if moved and self.commit and not self.multi:
            self._commit()
        return moved

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the rendered row ``row``; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own render -- what
        :meth:`~motui.app.TUI.hit_test` reports -- so the title row
        (when there is one) is row 0, the window's rows follow, and the
        counter row (when there is one) is never an option.  ``col`` is
        ignored: every list row owns the whole width, so the column never
        narrows a hit.  A hit lands the cursor and, for a ``commit=True``
        form control, writes the row into :attr:`chosen` (the click is the
        choice, even on the row the cursor already sat on); a
        ``multi=True`` list leaves ``chosen`` to the marks.
        """
        target = self._option_at(row)
        if target is None:
            return False
        self._index = target
        if self.commit and not self.multi:
            self._commit()
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the option row under a cell; ``True`` when the marking changed.

        The pointer tier's row-level half (D3): ``row`` is a 0-based row of
        this component's own render, resolved through the very arithmetic
        :meth:`click` uses (:meth:`_option_at`) -- the title row above the
        window and the counter row below it carry no option, and a marking
        on them is cleared -- and ``col`` is ignored like ``click``'s.  A
        negative ``row`` clears the marking: the pointer left.  The answer
        is whether the marked row actually changed, so a motion inside one
        row answers ``False`` (nothing to repaint), and
        :meth:`render` merges the theme's ``hover`` over the marked row's
        own style.
        """
        target = None if row < 0 else self._option_at(row)
        changed = target != self._hover_row
        self._hover_row = target
        return changed

    @property
    def selected(self) -> Option | None:
        """The option under the cursor, or ``None`` for an empty list."""
        return self._selected_option()

    def _selected_option(self) -> Option | None:
        """The option under the cursor (the private twin of :attr:`selected`).

        A variant re-aims the public ``selected`` at what its rows carry
        (:class:`Radio` answers the selected label), so the editing paths --
        :meth:`activate`, :meth:`_commit`, :meth:`toggle` -- read the option
        itself through here and never the variant's public view.
        """
        rows = self._rows()
        if not rows:
            return None
        return rows[self._index]

    def activate(self) -> bool:
        """Take the option under the cursor into :attr:`chosen`.

        The list's :class:`~motui.kernel.block.Activable` verb: a host
        routes the return key here, then reads ``chosen`` once -- the
        option that was taken -- and resets it to ``None``.  A ``multi``
        list is a toggle instead: the cursor row's mark flips and
        ``chosen`` becomes the marked values (:meth:`toggle`).  Answers
        whether there was something to take (``False``, and ``chosen``
        stays ``None``, for an empty list).
        """
        if self.multi:
            return self.toggle()
        selected = self._selected_option()
        if selected is None:
            self.chosen = None
            return False
        self.chosen = self._chosen_of(selected)
        return True

    def toggle(self) -> bool:
        """Flip the cursor row's mark; ``True`` when there was one to flip.

        The ``multi`` list's one gesture (D1): the cursor row's mark flips
        and :attr:`chosen` is recomputed from the marks, in row order.  An
        empty list -- or a single-choice one, whose ``chosen`` is the
        cursor's option and not a set of marks -- answers ``False`` and
        changes nothing.
        """
        if not self.multi or self._selected_option() is None:
            return False
        self.marked.toggle(self._index)
        self._sync_chosen()
        return True

    # -- the rows ---------------------------------------------------------------

    def _rows(self) -> Sequence[Option]:
        """The rows the cursor walks and the window renders."""
        return self.options

    def _cursor(self) -> CursorWindow:
        """The cursor-and-window value of the rows the cursor walks.

        ``max_rows`` is its cap and ``window`` its policy switch, so the
        arithmetic of the top-stick menu window and the centred data-view
        window lives in one value (:class:`~motui.kernel.cursor.CursorWindow`)
        rather than twice here.
        """
        return CursorWindow(self._index, len(self._rows()), self.max_rows, self.window)

    def _option_at(self, row: int) -> int | None:
        """The data-row index a rendered row carries, or ``None``.

        The one row arithmetic :meth:`click` and :meth:`hover_at` share: the
        title row (``row 0`` when there is one) sits above the window, the
        counter row below it, and neither carries an option -- as does
        every cell past the window.  Negative rows answer ``None`` too.
        """
        index = row - (1 if self.title else 0)
        if index < 0:
            return None
        start, stop = self._visible_range()
        target = start + index
        return target if start <= target < stop else None

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` slice of rows rendered, at most ``max_rows``.

        :meth:`_cursor` answers it: the window hangs at the top while the
        cursor sits inside the first ``max_rows`` rows, then scrolls one row
        per step with the cursor as its last row -- and a ``window=True``
        list centres the cursor instead.  Either way the selected row is
        always on screen.
        """
        return self._cursor().range()

    def _mark_width(self) -> int:
        """The mark column's width (``multi`` only; ``0`` for a plain list)."""
        return visible_width(mark_prefix(False)) if self.multi else 0

    def _chosen_of(self, option: Option) -> object:
        """What a chosen row lands in ``chosen``: the :class:`Option` itself.

        The seam :meth:`_commit` and :meth:`activate` write through: a menu
        carries the whole option, and a variant that speaks values narrows it
        (:class:`Radio`).
        """
        return option

    def _commit(self) -> None:
        """Write the row under the cursor into ``chosen`` (the ``commit`` knob)."""
        selected = self._selected_option()
        self.chosen = None if selected is None else self._chosen_of(selected)

    def _sync_chosen(self) -> None:
        """Recompute ``chosen`` from the marks: the marked values, in row order.

        The ``multi`` knob's invariant -- ``chosen`` *is* the marks, ``None``
        while none is set.  The values are the payloads (an option's label
        when its payload is ``None``), in data-row order, so a host reads the
        whole selection the way the rows show it.
        """
        values = [
            _option_value(option)
            for index, option in enumerate(self._rows())
            if index in self.marked
        ]
        self.chosen = values or None

    def _description_column(self) -> int:
        """The column every description starts at (0 when none is set).

        Measured over **every** option -- not the window or the current
        matches -- so the column holds still while the cursor scrolls and a
        filter narrows the rows.  A ``multi`` list keeps the mark column in
        the same place on every row, so its width is part of the lead.
        """
        if not any(option.description for option in self.options):
            return 0
        widest = max(visible_width(option.label) for option in self.options)
        return visible_width(self.marker) + 1 + self._mark_width() + widest + GAP

    def _row(self, option: Option, current: bool, column: int, hovered: bool = False, marked: bool = False) -> Line:
        """One row: the marker, the mark (``multi``), the label, the description.

        The cursor row's style is the focus rule in one line: unfocused, the
        marker and the label render in ``selected_style.merge(dim)`` (the
        description keeps its own ``dim``).  A hovered row merges the theme's
        ``hover`` on top of whatever its own style resolved to (the cursor
        row's included) -- marker, mark and label only, the description
        column keeping its own style exactly as the focus rule leaves it.
        """
        lead = visible_width(self.marker) + 1
        style = self._selected_style if current else self._label_style
        if current and not self.focused:
            style = style.merge(self._dim)  # unfocused: keep the hue, lose the weight
        if hovered:
            style = style.merge(self._hover_style)
        segments = [
            Segment(f"{self.marker} " if current else " " * lead, style),
        ]
        if self.multi:
            segments.append(Segment(mark_prefix(marked), style))
        segments.append(Segment(option.label, style))
        if option.description and column:
            pad = column - lead - self._mark_width() - visible_width(option.label)
            if pad > 0:
                segments.append(Segment(" " * pad))
            segments.append(Segment(option.description, self._description_style))
        return Line(tuple(segments))

    def _counter(self) -> str:
        """The ``(i/n)`` row while the window scrolls; empty when it does not."""
        count = len(self._rows())
        cap = self.max_rows
        if cap is None or cap <= 0 or count <= cap:
            return ""
        return f"({self._index + 1}/{count})"

    def _revision(self) -> object:
        """The value snapshot of everything the list's rows are made of.

        The rows themselves (``tuple(_rows())`` -- the subclass seam, so an
        ``Autocomplete`` snapshots its current matches), the whole option
        universe (the description column is measured over *it*, never the
        window or the filter), the title, the marker, the window cap and
        policy, the ``multi`` flag with a copy of the marks, the cursor, the
        pointer's mark, the focus flag and the six resolved styles -- all
        plain values, so the tuple is a copy by construction.  A pending
        :attr:`chosen` is deliberately out: no row reads it.
        """
        return (
            tuple(self._rows()),
            tuple(self.options),
            self.title,
            self.marker,
            self.max_rows,
            self.window,
            self.multi,
            tuple(self.marked),
            self._index,
            self._hover_row,
            self.focused,
            self._label_style,
            self._selected_style,
            self._description_style,
            self._title_style,
            self._dim,
            self._hover_style,
        )

    def revision(self) -> object:
        """The :class:`~motui.kernel.block.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this list
        keys its own row cache on the same value, so a moved cursor, a
        re-filter, a flipped mark or a hover invalidates the block's copy --
        and a **sealed** list's cursor band finally reaches the screen (D4).
        """
        return self._revision()

    def render(self, width: int) -> list[Line]:
        rows = self._rows()
        start, stop = self._visible_range()
        column = self._description_column()
        out: list[Line] = []
        if self.title:
            out.append(Line.from_text(self.title, self._title_style).fit(width))
        for i in range(start, stop):
            out.append(
                self._row(
                    rows[i], i == self._index, column, i == self._hover_row, i in self.marked
                ).fit(width)
            )
        counter = self._counter()
        if counter:
            out.append(Line.from_text(counter, self._description_style).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self._index})"


class Radio(Select):
    """The single-choice group: one ``(\u2022)`` marker on one row.

    A :class:`Select` preset -- ``wrap=False`` (a step clamps, it never
    cycles), ``commit=True`` (the cursor *is* the selection: a step, a click
    and an activation all write it) and the ``(\u2022)`` marker -- with two
    traits of its own: the rows lead with ``(\u2022) `` on the selected row
    and ``( ) `` on every other (not with the menu's arrow and indent), and
    the selected row's band is the form rule -- unfocused it renders
    ``selected_style`` as it is (a group does not dim its pick), focused it
    merges ``focus_style`` (the theme's ``cursor``).

    ``labels`` takes plain strings (the label is the value) or
    :class:`Option` entries (a label with its own payload), the same option
    vocabulary the menu family speaks; :attr:`chosen` is the selected
    entry's value -- its label when a plain string was given or the option
    carries no payload.  Rows step with :meth:`~Select.move` like a data
    view -- **clamped** at the ends, never wrapping -- and ``hover_at`` is
    the pointer tier's row marking (the marked row merges the theme's
    ``hover``), resolved the same way :meth:`~Select.click` resolves a
    cell, so the two can never disagree.
    """

    __slots__ = ("_focus_style",)

    def __init__(
        self,
        labels: Sequence[str | Option],
        *,
        index: int = 0,
        label_style: Style | None = None,
        selected_style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(
            _options(labels),
            max_rows=None,
            wrap=False,
            marker=FILLED_MARK.rstrip(),  # the arrow seat: the row renders its own mark
            commit=True,
            focused=focused,
            label_style=label_style,
            selected_style=selected_style,
            theme=theme,
        )
        # The form bands: explicit > theme field > DEFAULT_THEME, resolved
        # after the base's own picks (``hover_style`` replaces the base's).
        self._hover_style = self._pick(hover_style, "hover")
        self._focus_style = self._pick(focus_style, "cursor")
        # The setter reads ``options``, which is armed by now.
        self.index = index

    # -- the selection ---------------------------------------------------------

    @property
    def labels(self) -> list[str]:
        """The display labels, in row order (a fresh list per read)."""
        return [option.label for option in self.options]

    @property
    def selected(self) -> str | None:
        """The label of the selected row, or ``None`` for an empty group."""
        option = super().selected
        return None if option is None else option.label

    def _chosen_of(self, option: Option) -> object:
        """The value a chosen row carries: the payload, or the label itself."""
        return _option_value(option)

    def _row(self, option: Option, current: bool, column: int, hovered: bool = False, marked: bool = False) -> Line:
        """One radio row: the filled or empty marker, then the label.

        The form band rule, in the order the bands stack: the selected row's
        ``selected_style`` (an unselected row is plain), the pointer's
        ``hover_style`` while the row is marked, then ``focus_style`` while
        the row is both selected and focused.
        """
        style = self._selected_style if current else self._label_style
        if hovered:
            style = style.merge(self._hover_style)
        if current and self.focused:
            style = style.merge(self._focus_style)
        mark = FILLED_MARK if current else EMPTY_MARK
        return Line((Segment(mark, style), Segment(option.label, style)))

    def _revision(self) -> object:
        """The base snapshot plus the variant's own focus band.

        A radio renders by ``focus_style`` on top of everything the base
        tracks, so the band is a row input like the other styles and the
        snapshot carries it (the protocol's promise: equal snapshots answer
        equal rows at one width).
        """
        return (*super()._revision(), self._focus_style)

    def __repr__(self) -> str:
        return f"Radio({self.labels!r}, index={self._index}, focused={self.focused})"


class CheckGroup(Select):
    """The multiple-choice group: a ``[x]`` / ``[ ]`` mark on every row.

    A :class:`Select` preset -- ``multi=True`` (the marks are the
    selection), ``wrap=False`` (a step clamps) and ``commit=False`` (only
    :meth:`~Select.toggle`, which an activation is, moves ``chosen``) --
    with the form bands :class:`Radio` takes: ``hover_style`` for the row
    under the pointer and ``focus_style`` (the theme's ``cursor``) merged
    over the cursor row while ``focused``, the pick never dimmed.  A row
    reads ``"\u2192 [x] label"`` under the cursor and ``"  [ ] label"``
    elsewhere: the menu's marker seat, then the mark column
    (:func:`~motui.kernel.mark.mark_prefix`), then the label.

    ``labels`` takes plain strings (the label is the value) or
    :class:`Option` entries, like :class:`Radio`; :attr:`chosen
    <Select.chosen>` is the marked rows' values in row order -- ``None``
    while nothing is marked.
    """

    __slots__ = ("_focus_style",)

    def __init__(
        self,
        labels: Sequence[str | Option],
        *,
        marked: Iterable[int] = (),
        index: int = 0,
        label_style: Style | None = None,
        selected_style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(
            _options(labels),
            max_rows=None,
            wrap=False,
            commit=False,
            multi=True,
            marked=marked,
            focused=focused,
            label_style=label_style,
            selected_style=selected_style,
            theme=theme,
        )
        # The form bands: explicit > theme field > DEFAULT_THEME (see Radio).
        self._hover_style = self._pick(hover_style, "hover")
        self._focus_style = self._pick(focus_style, "cursor")
        # The setter reads ``options``, which is armed by now.
        self.index = index

    @property
    def labels(self) -> list[str]:
        """The display labels, in row order (a fresh list per read)."""
        return [option.label for option in self.options]

    def _row(self, option: Option, current: bool, column: int, hovered: bool = False, marked: bool = False) -> Line:
        """One check row: the marker seat, the mark, the label.

        The same band rule :class:`Radio` renders by -- hover, then focus on
        the cursor row, no dim -- over the menu's marker seat
        (``"\u2192 "`` / its indent) and the ``[x] ``/``[ ] `` mark.
        """
        style = self._selected_style if current else self._label_style
        if hovered:
            style = style.merge(self._hover_style)
        if current and self.focused:
            style = style.merge(self._focus_style)
        lead = visible_width(self.marker) + 1
        segments = [
            Segment(f"{self.marker} " if current else " " * lead, style),
            Segment(mark_prefix(marked), style),
            Segment(option.label, style),
        ]
        return Line(tuple(segments))

    def _revision(self) -> object:
        """The base snapshot plus the variant's own focus band (see ``Radio``)."""
        return (*super()._revision(), self._focus_style)

    def __repr__(self) -> str:
        return f"CheckGroup({self.labels!r}, index={self._index})"
