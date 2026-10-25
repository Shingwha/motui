"""Choice components: :class:`Option`, :class:`Select` and its variants.

``Select`` is the toolkit's one cursor-over-rows component: one
:class:`Option` per row, one cursor, one scroll window.  A row reads
``"\u2192 label"`` under the cursor and ``"  label"`` elsewhere -- the cursor
row in the theme's ``accent``, the others plain -- and every option's
``description`` sits in one column to the right, measured over the whole
option list so the column never jumps while the cursor scrolls or a filter
narrows the rows.  A list longer than ``max_rows`` renders a scrolling window
(the cursor row is always visible) and a ``(i/n)`` counter row beneath it;
the window's arithmetic is :class:`~motui.widgets.cursor.Cursor`'s, the
same value ``List`` renders through.  Styles resolve at render time from the
widget's theme (``content.accent`` / ``text.muted`` / ``text.faint``), with
whole role groups overridable through ``styles=Styles(...)``.  Only the core
layer is imported; no key is read here -- the editing entry points are plain
methods a host routes to.
``focused`` is the focus flag the focus tier sets (an unfocused cursor row
first merges the dim attribute from ``text.faint`` onto its cursor-text
style -- but only when the style and the band it will ride both carry no
background: dim is a foreground attribute, so on a background it would dim
the text into the surface instead -- and the band itself becomes
``rows.inactive``), and ``hover_at`` is the pointer tier's row marking (the
marked row rests on ``rows.hover``).

**The row-band contract.**  Every row resolves its bands through the
theme's :class:`~motui.kernel.theme.RowStyles`: ``base`` is the resting
surface, ``active`` the cursor row's band and ``hover`` the pointer's, and a
``Styles(rows=...)`` override replaces the group wholesale.  A row is its
text-styled segments -- the marker seat, the
mark, the label and the description in their own styles -- then
``.fit(width).fill(fitted.width, band)``: the W1 primitive, the band
underneath, the text styles on top.  The band merges under the row's own
cells -- a pill behind the text, never a ribbon across the pane; a
full-surface band is the host's container's job
(``Padding(fill_style=...)`` / ``Panel(frame=False, style=...)``, which
fill every row to the width they are handed).  Resting rows, the title
row and the ``(i/n)`` counter row rest on the ground; only the engaged
row swaps the band, and the hovered row's band wins outright over the
cursor's (D3).

Four knobs express every variant of the family (D1), so there is one base
class and no second copy of the cursor/window arithmetic:

* ``wrap`` -- a menu cycles its ends (``True``, the default), a data view
  clamps (``False``);
* ``glyphs.cursor`` -- the cursor row's leading glyph;
* ``commit`` -- a form control (``True``) leaves the row it landed on
  pending as it moves or is clicked; a menu (``False``, the default) only
  writes on :meth:`Select.activate`;
* ``window`` -- ``max_rows`` means a top-stick window (``False``, the
  default) or a centred one (``True``, the data view's policy).

The multiple-selection variant is the :class:`MultiSelect` subclass: its
rows carry the ``[x] ``/``[ ] `` mark of
:class:`~motui.widgets.mark.MarkSet`, :meth:`MultiSelect.toggle` flips the
cursor row's mark, and the pending result is the marked values.

The rows' glyphs are content, not style: ``Select`` leads with the
``glyphs`` vocabulary's ``cursor`` and ``MultiSelect`` draws its marks from
``check_on`` / ``check_off``; ``RadioGroup`` uses ``radio_on`` /
``radio_off``.  The vocabulary is one keyword-only constructor parameter.
Each seat is measured through :func:`~motui.kernel.glyphs.seat_width`
(``visible_width``, never ``len``), a state pair is padded through
:func:`~motui.kernel.glyphs.pair_seat` so both states share one column,
and an empty string disables the glyph and its whole seat -- ``cursor=""``
starts every label at column 0, with no dangling separator.

:class:`RadioGroup` and :class:`CheckboxGroup` are the two presets a form is
built from -- single choice with a ``(\u2022)`` marker, multiple choice with
the marks -- and take their labels as plain strings or as :class:`Option`
entries, the same vocabulary the menu family speaks.  Neither renders a
description, so a non-empty ``Option.description`` is a construction error
rather than silently dropped text.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Sequence

from ..widgets.cursor import Cursor
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat, seat_width
from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.layout import Constraints
from ..widgets.mark import MarkSet
from ..kernel.style import Style
from ..kernel.text import visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

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
    """A label sequence as :class:`Option` values, one per row.

    A plain string is the label *and* the value; an :class:`Option` keeps
    its label and carries its payload as the value -- or its label when the
    payload is ``None``, so a result never reads ``None`` for a named row.
    The group presets (:class:`RadioGroup` / :class:`CheckboxGroup`) render
    labels only, so an option's description is not part of their rows.
    """
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


class Select(Widget):
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
    :class:`~motui.widgets.cursor.Cursor`'s arithmetic.  ``wrap`` makes
    :meth:`move` step from the last row to the first (and back) instead of
    stopping at the ends.  ``glyphs.cursor`` leads the cursor row; the other rows
    are indented by its seat width (``0`` when it is ``""`` -- no dangling
    separator).  A counter row ``(i/n)`` (the cursor's
    1-based row over the row count) is rendered only while the window
    actually scrolls, so short lists stay clean.

    :meth:`activate` is the list's activation: it leaves the option under
    the cursor pending and answers whether there was one to take.  The host
    reads it once through :meth:`take_result`, which clears it; :meth:`move`
    and :meth:`~motui.widgets.autocomplete.Autocomplete.set_query` clear the
    pending value, so a stale pick never survives the next keystroke.
    ``commit=True`` leaves the row the cursor landed on pending as it moves
    or is clicked (the cursor *is* the choice).  The multiple-selection
    variant is :class:`MultiSelect`; a plain ``Select`` is single-choice.

    ``select(index)`` places the cursor on an enabled row and answers
    whether it moved; ``home()``/``end()`` are its two edges, skipping
    disabled rows.  ``disabled`` refuses every cursor gesture for the whole
    control, ``disabled_items`` marks individual data rows: :meth:`move`
    steps over them, :meth:`click`/:meth:`activate` reject them, and they
    render ``text.faint``.

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.document.Focusable`): while it is ``True`` the
    cursor row's label renders in ``content.accent``; while it is ``False``
    the dim attribute of ``text.faint`` is merged onto that style -- the
    cursor stays legible but loses weight, and nothing else on the row
    changes (the description column keeps its own ``text.muted``).  The
    merge is skipped when the style carries an explicit background, where
    dim would dim the text into the surface instead of weakening it.  The
    cursor row's *band* is ``rows.active`` while focused and
    ``rows.inactive`` while not, resting underneath the label; the same
    background rule applies to it.  Resting rows, the title row and the
    counter row rest on ``rows.base``.

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.document.Hoverable`);
    :meth:`hover_at` marks the option row under the pointer -- resolved
    through the same arithmetic :meth:`click` uses -- and the marked row
    rests on ``rows.hover``, whatever row it is on (D3: the
    hover wins outright over the cursor's).  The marking lives in one
    private row index that starts ``None``, so an un-hovered list renders
    byte-for-byte what it always did.
    """

    __slots__ = (
        "_hover_row",
        "_index",
        "_pending",
        "commit",
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

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int | None = 8,
        wrap: bool = True,
        glyphs: Glyphs = GLYPHS,
        commit: bool = False,
        window: bool = False,
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
        self.glyphs = glyphs
        self.commit = commit
        self.window = window
        #: The whole control refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The data rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)
        #: The focus flag the focus tier sets; the default matches the old
        #: constructor default so an unwired list keeps its cursor band.
        self.focused = True
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
        #: The pending one-shot result: written by ``activate`` and, under
        #: the ``commit`` knob, by every move/click that landed on a row;
        #: read once by :meth:`take_result` (a :class:`MultiSelect` keeps the
        #: marked values themselves rather than a pending pick).
        self._pending: Option | list[object] | None = None

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor's row of :meth:`_rows` (``0`` for an empty list)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = self._cursor().clamp(value)

    def _cursor(self) -> Cursor:
        """The cursor value of the rows the cursor walks.

        ``max_rows`` caps the window and ``window`` picks its policy, so the
        arithmetic of the top-stick menu window, the centred data-view
        window and the disabled-aware stepping is
        :class:`~motui.widgets.cursor.Cursor`'s rather than a loop here.
        """
        return Cursor(
            len(self._rows()),
            index=self._index,
            disabled=self.disabled_items,
            wrap=self.wrap,
        )

    def select(self, index: int) -> bool:
        """Place the cursor on the row ``index`` (clamped); ``True`` when it moved.

        A disabled row is refused, like every other cursor gesture; an empty
        list has nothing to select.  Under ``commit=True`` the landed row is
        left pending (the cursor is the choice).
        """
        if self.disabled:
            return False
        cursor = self._cursor()
        moved = cursor.select(index)
        self._index = cursor.index
        if moved and self.commit and not self._multi:
            self._commit()
        return moved

    def home(self) -> bool:
        """Place the cursor on the first enabled row; ``True`` when it moved."""
        return self._edge("home")

    def end(self) -> bool:
        """Place the cursor on the last enabled row; ``True`` when it moved."""
        return self._edge("end")

    def _edge(self, which: str) -> bool:
        """Jump to ``which`` edge through the cursor, committing on a move."""
        if self.disabled:
            return False
        cursor = self._cursor()
        moved = cursor.home() if which == "home" else cursor.end()
        if moved:
            self._index = cursor.index
            if self.commit and not self._multi:
                self._commit()
        return moved

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` enabled rows; ``True`` when it moved.

        Wrapping (the default) steps off the last row onto the first, and off
        the first onto the last; ``wrap=False`` clamps at the ends instead.
        An empty list, a disabled control, or a direction with no enabled
        landing moves nowhere.  What the step leaves pending follows the
        knobs: a menu clears its pending pick (a stale activation never
        survives the next keystroke), a ``commit=True`` form control leaves
        the row it landed on, and a :class:`MultiSelect` leaves the result
        to the marks.
        """
        if self.disabled or delta == 0:
            return False
        cursor = self._cursor()
        moved = cursor.move(delta)
        if not moved:
            return False
        self._index = cursor.index
        if not (self.commit or self._multi):
            self._pending = None
        if self.commit and not self._multi:
            self._commit()
        return True

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the rendered row ``row``; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own render -- what
        :meth:`~motui.app.TUI.hit` reports -- so the title row
        (when there is one) is row 0, the window's rows follow, and the
        counter row (when there is one) is never an option.  ``col`` is
        ignored: every list row owns the whole width, so the column never
        narrows a hit.  A hit lands the cursor and, for a ``commit=True``
        form control, leaves the row pending (the click is the choice, even
        on the row the cursor already sat on); a :class:`MultiSelect` leaves
        the result to the marks.  A disabled row (or a disabled control)
        refuses the hit.
        """
        if self.disabled:
            return False
        target = self._option_at(row)
        if target is None or self._is_disabled(target):
            return False
        self._index = target
        if self.commit and not self._multi:
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
        row answers ``False`` (nothing to repaint), and :meth:`render` rests
        the marked row on ``rows.hover`` -- whatever row it is
        on (D3).
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
        (:class:`RadioGroup` answers the selected label), so the editing
        paths -- :meth:`activate`, :meth:`_commit`, :meth:`toggle` -- read
        the option itself through here and never the variant's public view.
        """
        rows = self._rows()
        if not rows:
            return None
        return rows[self._index]

    def activate(self) -> bool:
        """Leave the option under the cursor pending.

        The list's :class:`~motui.kernel.document.Activable` verb: a host
        routes the return key here, then reads the result once through
        :meth:`take_result`.  A ``multi`` list is a toggle instead: the
        cursor row's mark flips and the pending result becomes the marked
        values (:meth:`toggle`).  Answers whether there was something to
        take (``False`` for an empty list or a disabled row, and nothing is
        left pending).
        """
        if self.disabled:
            return False
        if self._multi:
            return self.toggle()
        selected = self._selected_option()
        if selected is None or self._is_disabled(self._index):
            self._pending = None
            return False
        self._pending = self._chosen_of(selected)
        return True

    def take_result(self) -> object | None:
        """Read the pending result once and clear it (the ``Resultful`` door)."""
        value = self._pending
        self._pending = None
        return value

    def _is_disabled(self, index: int) -> bool:
        """Whether the data row ``index`` is disabled (whole control or per item)."""
        return self.disabled or index in self.disabled_items

    # -- the rows ---------------------------------------------------------------

    def _rows(self) -> Sequence[Option]:
        """The rows the cursor walks and the window renders."""
        return self.options

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
        cursor = self._cursor()
        size = cursor.count if self.max_rows is None else self.max_rows
        return cursor.window(size, anchor="center" if self.window else "top")

    def _mark_width(self) -> int:
        """The mark column's width (``multi`` only; ``0`` for a plain list).

        The pair's wider member sets it
        (:func:`~motui.kernel.glyphs.seat_width`, display columns), so
        both states take exactly one column.
        """
        if not self._multi:
            return 0
        marked_glyph, unmarked_glyph = self._mark_pair()
        return max(
            seat_width(marked_glyph), seat_width(unmarked_glyph)
        )

    def _mark_pair(self) -> tuple[str, str]:
        """The ``(marked, unmarked)`` pair the ``multi`` marks are drawn from."""
        return self.glyphs.check_on, self.glyphs.check_off

    def _chosen_of(self, option: Option) -> object:
        """What a chosen row leaves pending: the :class:`Option` itself.

        The seam :meth:`_commit` and :meth:`activate` write through: a menu
        carries the whole option, and a variant that speaks values narrows it
        (:class:`RadioGroup`).
        """
        return option

    def _commit(self) -> None:
        """Leave the row under the cursor pending (the ``commit`` knob)."""
        selected = self._selected_option()
        self._pending = None if selected is None else self._chosen_of(selected)

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
        """One row: the marker, the mark (``MultiSelect``), the label, the description.

        The segments carry their text styles only -- the marker seat, the
        mark and the label in ``content.accent`` on the cursor row (dim-merged
        from ``text.faint`` while unfocused and only when neither the label
        style nor the band it will ride has an explicit background -- dim is
        a foreground attribute, so on a background it would dim the text into
        the surface) and ``text.base`` elsewhere, the description in its own
        ``text.muted`` -- and the band is the row pipeline's
        (:func:`~motui.kernel.cell.rest`): ``rows.base`` at rest,
        ``rows.active``/``rows.inactive`` under the cursor row
        (focused/unfocused), ``rows.hover`` under the pointer's (D3, the
        hover winning wherever the two meet), the description column riding
        the band like every other cell of the row.  A disabled row paints every
        text cell in ``text.faint``.
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
        return f"({self._index + 1}/{count})"

    def _revision(self) -> object:
        """The value snapshot of everything the list's rows are made of.

        The rows themselves (``tuple(_rows())`` -- the subclass seam, so an
        ``Autocomplete`` snapshots its current matches), the whole option
        universe (the description column is measured over *it*, never the
        window or the filter), the title, the cursor glyph and the mark pair, the
        window cap and policy, the multi-selection state (the class switch and,
        for a :class:`MultiSelect`, a copy of the marks), the cursor, the
        pointer's mark, the focus/disabled flags, the disabled item set and
        the theme/``Styles`` the render resolves -- all plain values, so the
        tuple is a copy by construction.  A pending result is deliberately
        out: no row reads it.
        """
        return (
            tuple(self._rows()),
            tuple(self.options),
            self.title,
            self.glyphs.cursor,
            (self.glyphs.check_on, self.glyphs.check_off),
            self.max_rows,
            self.window,
            self._multi,
            (tuple(self.marked) if self._multi else ()),
            self._index,
            self._hover_row,
            self.focused,
            self.disabled,
            tuple(sorted(self.disabled_items)),
            self.theme,
            self.styles,
        )

    def revision(self) -> object:
        """The :class:`~motui.kernel.document.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this list
        keys its own row cache on the same value, so a moved cursor, a
        re-filter, a flipped mark or a hover invalidates the block's copy --
        and a **sealed** list's cursor band finally reaches the screen (D4).
        """
        return self._revision()

    def render(self, c: Constraints) -> Surface:
        """The window's rows, the title and the counter, each on its band.

        The constraint carries the width; a ``max_height`` budget
        truncates the leading rows (the title row included when it is the
        only row offered).  Every row goes through the row-band contract
        (:func:`~motui.kernel.cell.rest`): the item rows, the title row and
        the ``(i/n)`` counter row alike are ``fit`` to ``c.width`` and rest
        on their resolved band -- ``rows.base``, or ``rows.active`` /
        ``rows.inactive`` on the focused / unfocused cursor row and
        ``rows.hover`` on the hovered one (D3).  The styles are read off the
        theme/``Styles`` on every call, so a rethemed list repaints.  The
        surface is :meth:`Surface.clipped`, not padded: short rows keep
        their natural width, so the bytes a layout paints do not change.
        """
        text = self.group("text")
        rows = self._rows()
        start, stop = self._visible_range()
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
            current = i == self._index
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
        """The surface one row rests on: :meth:`RowStyles.band`, by precedence."""
        return self.group("rows").band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self._index})"


class MultiSelect(Select):
    """A :class:`Select` whose rows carry marks and whose result is the marked set.

    The multiple-selection variant of the menu family (D1): ``commit`` and a
    single pending pick are a single-choice notion, so this variant replaces
    them with :attr:`marked` -- the data-row indices the ``check_on`` /
    ``check_off`` seats report -- and :meth:`toggle`, the one gesture that
    flips the cursor row's mark.  An :meth:`~Select.activate` is the same
    gesture, and the pending result is recomputed from the marks in row
    order (``None`` while nothing is marked), so a host reads the whole
    selection the way the rows show it.  Rendering, the cursor, the window,
    the description column and the pointer's row mark are the base's.
    """

    __slots__ = ("marked",)

    #: This list is a multiple selection.
    _multi = True

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
        """Flip the cursor row's mark; ``True`` when there was one to flip.

        The multi-selection's one gesture (D1): the cursor row's mark flips
        and the pending result is recomputed from the marks, in row order.
        An empty list answers ``False`` and changes nothing.  A disabled
        control or cursor row refuses.
        """
        if self.disabled or self._selected_option() is None:
            return False
        if self._is_disabled(self._index):
            return False
        self.marked.toggle(self._index)
        self._sync_result()
        return True

    def _sync_result(self) -> None:
        """Recompute the pending result from the marks: their values, in row order.

        The variant's invariant -- the pending value *is* the marks, ``None``
        while none is set.  The values are the payloads (an option's label
        when its payload is ``None``), in data-row order, so a host reads the
        whole selection the way the rows show it.
        """
        values = [
            _option_value(option)
            for index, option in enumerate(self._rows())
            if index in self.marked
        ]
        self._pending = values or None

    def __repr__(self) -> str:
        return f"MultiSelect({self.options!r}, index={self._index})"


class _FormGroup:
    """The form groups' shared half: label rows and the form band rule."""

    __slots__ = ()

    @property
    def labels(self) -> list[str]:
        """The display labels, in row order (a fresh list per read)."""
        return [option.label for option in self.options]

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

    A :class:`Select` preset -- ``wrap=False`` (a step clamps, it never
    cycles), ``commit=True`` (the cursor *is* the selection: a step, a click
    and an activation all leave the new pick pending) and the ``(•)``
    marker -- with two traits of its own: the rows lead with ``(•) `` on the
    selected row and ``( ) `` on every other (not with the menu's arrow and
    indent), and the selected row's band is the form rule -- unfocused it
    rests on the ground as it is (a group does not dim its pick), focused it
    carries the theme's ``rows.active`` underneath its accent label.

    ``labels`` takes plain strings (the label is the value) or
    :class:`Option` entries (a label with its own payload), the same option
    vocabulary the menu family speaks; the pending result is the selected
    entry's value -- its label when a plain string was given or the option
    carries no payload.  A non-empty ``Option.description`` is a
    construction error: the group renders labels only.  ``glyphs.radio_off``
    and ``glyphs.radio_on`` are the row's own pair: the row renders their
    seats through
    :func:`~motui.kernel.glyphs.pair_seat`, padded to the wider member, so
    both states share one column; ``""`` disables a glyph and its seat.
    Rows step with :meth:`~Select.move` like a data view -- **clamped** at
    the ends, never wrapping -- and ``hover_at`` is the pointer tier's row
    marking (the marked row rests on ``rows.hover``, whatever row
    it is on), resolved the same way :meth:`~Select.click` resolves a cell,
    so the two can never disagree.  ``disabled``/``disabled_items`` work like
    the base's.
    """

    __slots__ = ()

    def __init__(
        self,
        labels: Sequence[str | Option],
        *,
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        _reject_descriptions(labels, "RadioGroup")
        super().__init__(
            _options(labels),
            max_rows=None,
            wrap=False,
            glyphs=glyphs,
            commit=True,
            disabled=disabled,
            disabled_items=disabled_items,
            theme=theme,
            styles=styles,
        )
        # The old constructor default: a form group starts unfocused.
        self.focused = False
        # The setter reads ``options``, which is armed by now.
        self.index = index

    # -- the selection ---------------------------------------------------------

    @property
    def selected(self) -> str | None:
        """The label of the selected row, or ``None`` for an empty group."""
        option = super().selected
        return None if option is None else option.label

    def _chosen_of(self, option: Option) -> object:
        """The value a chosen row carries: the payload, or the label itself."""
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
        """One radio row: the filled or empty marker pair, then the label.

        The segments carry their text styles only -- the mark in
        ``content.accent`` on the cursor row or ``text.base`` elsewhere, the
        label in ``text.base``, and a disabled row in ``text.faint`` -- and
        the band is the row pipeline's
        (:func:`~motui.kernel.cell.rest`): the pointer's
        band on the hovered row, the theme's ``rows.active`` band under the
        selected row while focused, the ground at rest.  The pair seat is
        :func:`~motui.kernel.glyphs.pair_seat`, padded to the wider member,
        so the two states share one column.
        """
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

    def _revision(self) -> object:
        """The base's snapshot (the glyph vocabulary included)."""
        return super()._revision()

    def __repr__(self) -> str:
        return f"RadioGroup({self.labels!r}, index={self._index}, focused={self.focused})"


class CheckboxGroup(_FormGroup, MultiSelect):
    """The multiple-choice group: a ``[x]`` / ``[ ]`` mark on every row.

    A :class:`MultiSelect` preset -- the marks are the selection,
    ``wrap=False`` (a step clamps) and only
    :meth:`~MultiSelect.toggle`, which an activation is, moves the pending
    result -- with the form bands :class:`RadioGroup` takes: the theme's
    ``rows.hover`` for the row under the pointer (winning wherever it lands)
    and ``rows.active`` under the cursor row while ``focused``, the pick
    never dimmed.  A row reads ``"\u2192 [x] label"`` under the cursor and
    ``"  [ ] label"`` elsewhere: the menu's marker seat, then the mark column
    (:func:`~motui.kernel.glyphs.pair_seat`), then the label.

    ``labels`` takes plain strings (the label is the value) or
    :class:`Option` entries, like :class:`RadioGroup`; the pending result is
    the marked rows' values in row order -- ``None`` while nothing is
    marked.  A non-empty ``Option.description`` is a construction error: the
    group renders labels only.  ``glyphs.check_on`` / ``check_off`` are the
    row's marked/unmarked pair: the column is the pair's wider seat, so both
    states line up, and two empty strings
    collapse the column entirely.

    :meth:`click` is the pointer gesture of a multi-select: it moves the
    cursor onto the clicked row **and** flips that row's mark, so a click
    is the same selection act the keyboard's ``toggle`` is.
    """

    __slots__ = ()

    def __init__(
        self,
        labels: Sequence[str | Option],
        *,
        marked: Iterable[int] = (),
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        _reject_descriptions(labels, "CheckboxGroup")
        super().__init__(
            _options(labels),
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
        # The setter reads ``options``, which is armed by now.
        self.index = index

    def click(self, row: int, col: int) -> bool:
        """Move the cursor onto a row and flip its mark; ``True`` on a hit.

        The multi-select's pointer gesture -- the P0 this preset exists to
        get right: inheriting the plain :meth:`~Select.click` would move
        the cursor and change no mark, so a click could never select
        anything.  ``col`` is ignored like the base's; a disabled control,
        a disabled row, the marker gap or a cell past the rows is a miss.
        """
        if self.disabled:
            return False
        target = self._option_at(row)
        if target is None or self._is_disabled(target):
            return False
        self._index = target
        self.marked.toggle(self._index)
        self._sync_result()
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
        """One check row: the marker seat, the mark, the label.

        The segments carry their text styles only -- the cursor row's in
        ``content.accent``, the others in ``text.base``, a disabled row in
        ``text.faint``, the mark column riding along -- and the band is the
        row pipeline's, the same form rule :class:`RadioGroup` renders by.
        The cursor seat is :func:`~motui.kernel.glyphs.seat`, the mark column
        :func:`~motui.kernel.glyphs.pair_seat` padded to the pair's wider
        member.
        """
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
        return f"CheckboxGroup({self.labels!r}, index={self._index})"
