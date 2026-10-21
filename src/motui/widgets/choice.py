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
focus flag the focus tier sets (an unfocused cursor row renders its
cursor-text style and band with ``theme.dim`` merged -- but only when they
carry no explicit background: ``dim`` is a foreground attribute, so on a
background band it dims the text into the surface instead of weakening the
band; the band itself is the signal then), and ``hover_at`` is the pointer
tier's row marking (the marked row rests on the theme's ``hover``).

**The row-band contract.**  Every row resolves its bands through one
:class:`~motui.widgets.bands.RowBands` value: the theme constructor seeds
``ground`` (the resting surface), ``active`` (the cursor row's band, the
theme's ``ground_active``), ``hover`` (the pointer's, ``hover``) and the
``dim`` attenuation (``dim``), and the explicit ``ground_style`` /
``active_style`` / ``hover_style`` / ``disabled_style`` parameters override
their token.  A row is its text-styled segments -- the marker seat, the
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

Five knobs express every variant of the family (D1), so there is one base
class and no second copy of the cursor/window arithmetic:

* ``wrap`` -- a menu cycles its ends (``True``, the default), a data view
  clamps (``False``);
* ``marker`` -- the cursor row's leading glyph;
* ``commit`` -- a form control (``True``) leaves the row it landed on
  pending as it moves or is clicked; a menu (``False``, the default) only
  writes on :meth:`Select.activate`;
* ``multi`` -- a multiple-selection list (``True``): the rows carry the
  ``[x] ``/``[ ] `` mark of :class:`~motui.kernel.mark.MarkSet`,
  :meth:`Select.toggle` flips the cursor row's mark, and the pending
  result is the marked values;
* ``window`` -- ``max_rows`` means a top-stick window (``False``, the
  default) or a centred one (``True``, the data view's policy).

The rows' glyphs are content, not style: ``Select``'s ``marker`` (default
:data:`~motui.kernel.glyphs.MENU_CURSOR`) and ``mark_pair`` (the
``multi`` marks), ``RadioGroup``'s ``empty``/``filled`` pair and
``CheckboxGroup``'s ``mark_pair`` are keyword-only constructor parameters.
Each seat is measured through :func:`~motui.kernel.glyphs.seat_width`
(``visible_width``, never ``len``), a state pair is padded through
:func:`~motui.kernel.glyphs.pair_seat` so both states share one column,
and an empty string disables the glyph and its whole seat -- ``marker=""``
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
from dataclasses import dataclass, replace
from typing import Sequence

from ..kernel import glyphs
from ..kernel.cursor import CursorWindow
from ..kernel.lines import Line, Segment
from ..kernel.mark import MarkSet
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed
from .bands import BandedRows, RowBands

__all__ = ["CheckboxGroup", "Option", "RadioGroup", "Select"]

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


class Select(BandedRows, Themed):
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
    are indented by its seat width (``0`` when it is ``""`` -- no dangling
    separator).  A counter row ``(i/n)`` (the cursor's
    1-based row over the row count) is rendered only while the window
    actually scrolls, so short lists stay clean.

    :meth:`activate` is the list's activation: it leaves the option under
    the cursor pending and answers whether there was one to take.  The host
    reads it once through :meth:`take_result`, which clears it; :meth:`move`
    and :meth:`~motui.widgets.autocomplete.Autocomplete.set_query` clear the
    pending value, so a stale pick never survives the next keystroke.  Two
    knobs change that contract (D1): ``commit=True`` leaves the row the
    cursor landed on pending as it moves or is clicked (the cursor *is* the
    choice), and ``multi=True`` turns the list into a multiple selection --
    the rows carry the ``mark_pair`` seats (:attr:`marked`; default the
    vocabulary's ``[x]``/``[ ]``, padded to the pair's wider member so both
    states share one column, and two empty strings collapse the column),
    :meth:`toggle` (and an :meth:`activate`, which is the same gesture)
    flips the cursor row's mark, and the pending result is recomputed as the
    marked rows' values, in row order (``None`` while nothing is marked).

    ``select(index)`` places the cursor on an enabled row and answers
    whether it moved; ``home()``/``end()`` are its two edges, skipping
    disabled rows.  ``disabled`` refuses every cursor gesture for the whole
    control, ``disabled_items`` marks individual data rows: :meth:`move`
    steps over them, :meth:`click`/:meth:`activate`/:meth:`toggle` reject
    them, and they render ``disabled_style`` (the theme's ``dim`` by
    default).

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.block.Focusable`): while it is ``True`` the
    cursor row's label renders in ``cursor_text_style``; while it is
    ``False`` that style is merged with the theme's ``dim`` -- the cursor
    stays legible but loses weight, and nothing else on the row changes (the
    description column keeps its own ``dim``).  The merge is skipped when
    the style carries an explicit background, where ``dim`` would dim the
    text into the surface instead of weakening it.  The cursor row's *band*
    is the contract's ``ground_active``, resting underneath the label; the
    same background rule applies to it.  Resting rows, the title row and the
    counter row rest on the ground.

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`);
    :meth:`hover_at` marks the option row under the pointer -- resolved
    through the same arithmetic :meth:`click` uses -- and the marked row
    rests on the theme's ``hover`` band, whatever row it is on (D3: the
    hover wins outright over the cursor's).  The marking lives in one
    private row index that starts ``None``, so an un-hovered list renders
    byte-for-byte what it always did.
    """

    __slots__ = (
        "_cursor_text_style",
        "_description_style",
        "_disabled_style",
        "_hover_row",
        "_index",
        "_label_style",
        "_pending",
        "_title_style",
        "bands",
        "commit",
        "disabled",
        "disabled_items",
        "focused",
        "hover",
        "marked",
        "max_rows",
        "mark_pair",
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
        marker: str = glyphs.MENU_CURSOR,
        mark_pair: tuple[str, str] = (glyphs.MARKED, glyphs.UNMARKED),
        commit: bool = False,
        multi: bool = False,
        marked: Iterable[int] = (),
        window: bool = False,
        focused: bool = True,
        label_style: Style | None = None,
        cursor_text_style: Style | None = None,
        description_style: Style | None = None,
        title_style: Style | None = None,
        ground_style: Style | None = None,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        disabled_style: Style | None = None,
        bands: RowBands | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.options = list(options)
        self.title = title
        self.max_rows = max_rows
        self.wrap = wrap
        self.marker = marker
        self.mark_pair = mark_pair
        self.commit = commit
        self.multi = multi
        self.window = window
        #: The whole control refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The data rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)
        #: The marked rows (data-row indices) the ``multi`` knob reads and
        #: :meth:`toggle` flips; a single-choice list never marks.
        self.marked = MarkSet(marked) if multi else MarkSet()
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
        #: The pending one-shot result: written by ``activate`` and, under
        #: the ``commit`` knob, by every move/click that landed on a row;
        #: read once by :meth:`take_result` and, under ``multi``, the marked
        #: values themselves rather than a pending pick.
        self._pending: Option | list[object] | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._label_style = label_style if label_style is not None else NONE
        self._cursor_text_style = self._pick(cursor_text_style, "accent")
        self._description_style = self._pick(description_style, "dim")
        self._title_style = title_style if title_style is not None else NONE
        self._disabled_style = self._pick(disabled_style, "dim")
        # The row bands: one theme value, with the explicit style parameters
        # overriding their token (the old explicit > theme > DEFAULT_THEME
        # precedence).  ``bands=`` replaces the theme seed wholesale.
        seed = bands if bands is not None else RowBands.from_theme(self._theme)
        overrides: dict[str, Style] = {}
        if ground_style is not None:
            overrides["ground"] = ground_style
        if disabled_style is not None:
            overrides["disabled"] = disabled_style
        self.bands = replace(seed, **overrides) if overrides else seed
        if self.multi:
            self._sync_result()

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor's row of :meth:`_rows` (``0`` for an empty list)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = self._cursor().clamp(value)

    def select(self, index: int) -> bool:
        """Place the cursor on the row ``index`` (clamped); ``True`` when it moved.

        A disabled row is refused, like every other cursor gesture; an empty
        list has nothing to select.  Under ``commit=True`` the landed row is
        left pending (the cursor is the choice).
        """
        if self.disabled:
            return False
        rows = self._rows()
        if not rows:
            return False
        target = self._cursor().clamp(index)
        if target == self._index or self._is_disabled(target):
            return False
        self._index = target
        if self.commit and not self.multi:
            self._commit()
        return True

    def home(self) -> bool:
        """Place the cursor on the first enabled row; ``True`` when it moved."""
        return self._place_edge(0, 1)

    def end(self) -> bool:
        """Place the cursor on the last enabled row; ``True`` when it moved."""
        return self._place_edge(len(self._rows()) - 1, -1)

    def _place_edge(self, start: int, step: int) -> bool:
        """Walk from an edge to the first enabled row, in one direction."""
        rows = self._rows()
        if self.disabled or not rows:
            return False
        position = start
        for _ in range(len(rows)):
            if 0 <= position < len(rows) and not self._is_disabled(position):
                if position == self._index:
                    return False
                self._index = position
                if self.commit and not self.multi:
                    self._commit()
                return True
            position += step
        return False

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` enabled rows; ``True`` when it moved.

        Wrapping (the default) steps off the last row onto the first, and off
        the first onto the last; ``wrap=False`` clamps at the ends instead.
        An empty list, a disabled control, or a direction with no enabled
        landing moves nowhere.  What the step leaves pending follows the
        knobs: a menu clears its pending pick (a stale activation never
        survives the next keystroke), a ``commit=True`` form control leaves
        the row it landed on, and a ``multi=True`` one leaves the result to
        the marks.
        """
        if self.disabled or delta == 0:
            return False
        rows = self._rows()
        if not rows:
            return False
        step = 1 if delta > 0 else -1
        target = self._index
        moved = False
        for _ in range(abs(delta)):
            candidate = self._next_enabled(target, step)
            if candidate is None or candidate == target:
                break
            target = candidate
            moved = True
        if not moved:
            return False
        self._index = target
        if not (self.commit or self.multi):
            self._pending = None
        if self.commit and not self.multi:
            self._commit()
        return True

    def _next_enabled(self, start: int, step: int) -> int | None:
        """The next enabled row in ``step``'s direction, or ``None``.

        A wrapping walk checks every row once (and therefore answers
        ``None`` when they are all disabled); a clamping walk answers
        ``None`` at the boundary.
        """
        count = len(self._rows())
        position = start
        for _ in range(count):
            if self.wrap:
                position = (position + step) % count
            else:
                position += step
                if position < 0 or position >= count:
                    return None
            if not self._is_disabled(position):
                return position
        return None

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the rendered row ``row``; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own render -- what
        :meth:`~motui.app.TUI.hit` reports -- so the title row
        (when there is one) is row 0, the window's rows follow, and the
        counter row (when there is one) is never an option.  ``col`` is
        ignored: every list row owns the whole width, so the column never
        narrows a hit.  A hit lands the cursor and, for a ``commit=True``
        form control, leaves the row pending (the click is the choice, even
        on the row the cursor already sat on); a ``multi=True`` list leaves
        the result to the marks.  A disabled row (or a disabled control)
        refuses the hit.
        """
        if self.disabled:
            return False
        target = self._option_at(row)
        if target is None or self._is_disabled(target):
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
        row answers ``False`` (nothing to repaint), and :meth:`render` rests
        the marked row on the theme's ``hover`` band -- whatever row it is
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

        The list's :class:`~motui.kernel.block.Activable` verb: a host
        routes the return key here, then reads the result once through
        :meth:`take_result`.  A ``multi`` list is a toggle instead: the
        cursor row's mark flips and the pending result becomes the marked
        values (:meth:`toggle`).  Answers whether there was something to
        take (``False`` for an empty list or a disabled row, and nothing is
        left pending).
        """
        if self.disabled:
            return False
        if self.multi:
            return self.toggle()
        selected = self._selected_option()
        if selected is None or self._is_disabled(self._index):
            self._pending = None
            return False
        self._pending = self._chosen_of(selected)
        return True

    def toggle(self) -> bool:
        """Flip the cursor row's mark; ``True`` when there was one to flip.

        The ``multi`` list's one gesture (D1): the cursor row's mark flips
        and the pending result is recomputed from the marks, in row order.
        An empty list -- or a single-choice one, whose result is the
        cursor's option and not a set of marks -- answers ``False`` and
        changes nothing.  A disabled control or cursor row refuses.
        """
        if self.disabled or not self.multi or self._selected_option() is None:
            return False
        if self._is_disabled(self._index):
            return False
        self.marked.toggle(self._index)
        self._sync_result()
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
        """The mark column's width (``multi`` only; ``0`` for a plain list).

        The pair's wider member sets it
        (:func:`~motui.kernel.glyphs.seat_width`, display columns), so
        both states take exactly one column.
        """
        if not self.multi:
            return 0
        marked_glyph, unmarked_glyph = self.mark_pair
        return max(
            glyphs.seat_width(marked_glyph), glyphs.seat_width(unmarked_glyph)
        )

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

    def _sync_result(self) -> None:
        """Recompute the pending result from the marks: their values, in row order.

        The ``multi`` knob's invariant -- the pending value *is* the marks,
        ``None`` while none is set.  The values are the payloads (an
        option's label when its payload is ``None``), in data-row order, so
        a host reads the whole selection the way the rows show it.
        """
        values = [
            _option_value(option)
            for index, option in enumerate(self._rows())
            if index in self.marked
        ]
        self._pending = values or None

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
        return glyphs.seat_width(self.marker) + self._mark_width() + widest + GAP

    def _row(
        self,
        option: Option,
        current: bool,
        column: int,
        hovered: bool = False,
        marked: bool = False,
        disabled: bool = False,
    ) -> Line:
        """One row: the marker, the mark (``multi``), the label, the description.

        The segments carry their text styles only -- the marker seat, the
        mark and the label in ``cursor_text_style`` on the cursor row (the
        theme's ``accent``, ``dim``-merged while unfocused and only when
        neither the label style nor the band it will ride has an explicit
        background -- ``dim`` is a foreground attribute, so on a background
        it dims the text into the surface) and ``label_style`` elsewhere,
        the description in its own ``dim`` -- and the band is the row
        pipeline's (:meth:`_rest`): the ground at rest, ``ground_active``
        under the cursor row, ``hover`` under the pointer's (D3, the hover
        winning wherever the two meet), the description column riding the
        band like every other cell of the row.  A disabled row paints every
        text cell in ``disabled_style``.
        """
        lead = glyphs.seat_width(self.marker)
        if disabled:
            style = self._disabled_style
        else:
            style = self._cursor_text_style if current else self._label_style
            if current and not self.focused:
                band = self._band(current=True, hovered=hovered)
                if style.bg is None and band.bg is None:
                    style = style.merge(self.bands.dim)  # unfocused: lose the weight
        segments = [
            Segment(glyphs.seat(self.marker) if current else " " * lead, style),
        ]
        if self.multi:
            marked_glyph, unmarked_glyph = self.mark_pair
            glyph, other = (
                (marked_glyph, unmarked_glyph)
                if marked
                else (unmarked_glyph, marked_glyph)
            )
            segments.append(Segment(glyphs.pair_seat(glyph, other), style))
        segments.append(Segment(option.label, style))
        if option.description and column:
            pad = column - lead - self._mark_width() - visible_width(option.label)
            if pad > 0:
                segments.append(Segment(" " * pad))
            description_style = self._disabled_style if disabled else self._description_style
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
        window or the filter), the title, the marker and the mark pair, the
        window cap and policy, the ``multi`` flag with a copy of the marks,
        the cursor, the pointer's mark, the focus/disabled flags, the
        disabled item set and the resolved styles -- all plain values, so
        the tuple is a copy by construction.  A pending result is
        deliberately out: no row reads it.
        """
        return (
            tuple(self._rows()),
            tuple(self.options),
            self.title,
            self.marker,
            self.mark_pair,
            self.max_rows,
            self.window,
            self.multi,
            tuple(self.marked),
            self._index,
            self._hover_row,
            self.focused,
            self._label_style,
            self._cursor_text_style,
            self._description_style,
            self._title_style,
            self.bands,
            self.disabled,
            tuple(sorted(self.disabled_items)),
            self._disabled_style,
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
        """The window's rows, the title and the counter, each on its band.

        Every row goes through the row-band contract (:meth:`_rest`): the
        item rows, the title row and the ``(i/n)`` counter row alike are
        ``fit`` to ``width`` and rest on their resolved band -- the ground,
        or ``ground_active`` on the unhovered cursor row and ``hover`` on
        the hovered one (D3).
        """
        rows = self._rows()
        start, stop = self._visible_range()
        column = self._description_column()
        out: list[Line] = []
        if self.title:
            out.append(self._rest(Line.from_text(self.title, self._title_style), width))
        for i in range(start, stop):
            current = i == self._index
            hovered = i == self._hover_row
            out.append(
                self._rest(
                    self._row(
                        rows[i],
                        current,
                        column,
                        hovered,
                        i in self.marked,
                        self._is_disabled(i),
                    ),
                    width,
                    current,
                    hovered,
                )
            )
        counter = self._counter()
        if counter:
            out.append(self._rest(Line.from_text(counter, self._description_style), width))
        return out

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self._index})"


class _FormGroup(Select):
    """The form groups' shared half: label rows and the form band rule.

    A form group reads its labels straight off the options and paints the
    hover band over the engaged row whichever row it lands on, the engaged
    band on the selected row only while focused -- a group does not dim its
    pick -- and the ground everywhere else.  The explicit ``hover_style`` /
    ``active_style`` parameters re-aim the base's band tokens at
    construction, which is the only difference between a group and a
    plain list's bands.
    """

    __slots__ = ()

    @property
    def labels(self) -> list[str]:
        """The display labels, in row order (a fresh list per read)."""
        return [option.label for option in self.options]

    def _apply_form_bands(
        self, hover_style: Style | None, active_style: Style | None
    ) -> None:
        """Re-aim the form tokens the base resolved with the explicit styles."""
        overrides: dict[str, Style] = {}
        if hover_style is not None:
            overrides["hover"] = hover_style
        if active_style is not None:
            overrides["active"] = active_style
        if overrides:
            self.bands = replace(self.bands, **overrides)

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The form band rule: the hover band wins, then the focused selection's."""
        if hovered:
            return self.bands.hover
        if current and self.focused:
            return self.bands.active
        return self.bands.ground


class RadioGroup(_FormGroup):
    """The single-choice group: one ``(•)`` marker on one row.

    A :class:`Select` preset -- ``wrap=False`` (a step clamps, it never
    cycles), ``commit=True`` (the cursor *is* the selection: a step, a click
    and an activation all leave the new pick pending) and the ``(•)``
    marker -- with two traits of its own: the rows lead with ``(•) `` on the
    selected row and ``( ) `` on every other (not with the menu's arrow and
    indent), and the selected row's band is the form rule -- unfocused it
    rests on the ground as it is (a group does not dim its pick), focused it
    carries ``active_style`` (the theme's ``ground_active``) underneath its
    accent label.

    ``labels`` takes plain strings (the label is the value) or
    :class:`Option` entries (a label with its own payload), the same option
    vocabulary the menu family speaks; the pending result is the selected
    entry's value -- its label when a plain string was given or the option
    carries no payload.  A non-empty ``Option.description`` is a
    construction error: the group renders labels only.  ``empty`` and
    ``filled`` (default the vocabulary's ``( )``/``(•)`` pair) are the row's
    own glyph pair: the row renders their seats through
    :func:`~motui.kernel.glyphs.pair_seat`, padded to the wider member, so
    both states share one column; ``""`` disables a glyph and its seat.
    Rows step with :meth:`~Select.move` like a data view -- **clamped** at
    the ends, never wrapping -- and ``hover_at`` is the pointer tier's row
    marking (the marked row rests on the theme's ``hover`` band, whatever row
    it is on), resolved the same way :meth:`~Select.click` resolves a cell,
    so the two can never disagree.  ``disabled``/``disabled_items`` work like
    the base's.
    """

    __slots__ = ("empty", "filled")

    def __init__(
        self,
        labels: Sequence[str | Option],
        *,
        index: int = 0,
        empty: str = glyphs.RADIO_EMPTY,
        filled: str = glyphs.RADIO_FILLED,
        label_style: Style | None = None,
        active_style: Style | None = None,
        hover_style: Style | None = None,
        ground_style: Style | None = None,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        disabled_style: Style | None = None,
        bands: RowBands | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        _reject_descriptions(labels, "RadioGroup")
        super().__init__(
            _options(labels),
            max_rows=None,
            wrap=False,
            marker="",  # the row renders its own glyph pair, not the menu's seat
            commit=True,
            ground_style=ground_style,
            focused=focused,
            label_style=label_style,
            disabled=disabled,
            disabled_items=disabled_items,
            disabled_style=disabled_style,
            bands=bands,
            theme=theme,
        )
        self.empty = empty
        self.filled = filled
        # The form bands: the explicit parameters re-aim the base's tokens.
        self._apply_form_bands(hover_style, active_style)
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

        The segments carry their text styles only -- the selected row's
        mark and label in the cursor-text style (the theme's ``accent``),
        the others in ``label_style``, a disabled row in ``disabled_style``
        -- and the band is the row pipeline's (:meth:`_rest`): the pointer's
        band on the hovered row, the group's ``active_style`` band under the
        selected row while focused, the ground at rest.  The pair seat is
        :func:`~motui.kernel.glyphs.pair_seat`, padded to the wider member,
        so the two states share one column.
        """
        style = self._disabled_style if disabled else (
            self._cursor_text_style if current else self._label_style
        )
        glyph, other = (
            (self.filled, self.empty) if current else (self.empty, self.filled)
        )
        mark = glyphs.pair_seat(glyph, other)
        return Line((Segment(mark, style), Segment(option.label, style)))

    def _revision(self) -> object:
        """The base's snapshot plus the group's own glyph pair.

        ``Select._revision`` carries the option rows, the cursor, the
        disabled inputs and the styles; the radio row draws
        ``empty``/``filled`` on top of that, so both are row inputs here.
        """
        return (*super()._revision(), self.empty, self.filled)

    def __repr__(self) -> str:
        return f"RadioGroup({self.labels!r}, index={self._index}, focused={self.focused})"


class CheckboxGroup(_FormGroup):
    """The multiple-choice group: a ``[x]`` / ``[ ]`` mark on every row.

    A :class:`Select` preset -- ``multi=True`` (the marks are the
    selection), ``wrap=False`` (a step clamps) and ``commit=False`` (only
    :meth:`~Select.toggle`, which an activation is, moves the pending
    result) -- with the form bands :class:`RadioGroup` takes:
    ``hover_style`` for the row under the pointer (the theme's ``hover``,
    winning wherever it lands) and ``active_style`` (the theme's
    ``ground_active``) under the cursor row while ``focused``, the pick
    never dimmed.  A row reads ``"\u2192 [x] label"`` under the cursor and
    ``"  [ ] label"`` elsewhere: the menu's marker seat, then the mark column
    (:func:`~motui.kernel.glyphs.pair_seat`), then the label.

    ``labels`` takes plain strings (the label is the value) or
    :class:`Option` entries, like :class:`RadioGroup`; the pending result is
    the marked rows' values in row order -- ``None`` while nothing is
    marked.  A non-empty ``Option.description`` is a construction error: the
    group renders labels only.  ``mark_pair`` (default the vocabulary's
    ``[x]``/``[ ]``) is the row's marked/unmarked pair: the column is the
    pair's wider seat, so both states line up, and two empty strings
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
        mark_pair: tuple[str, str] = (glyphs.MARKED, glyphs.UNMARKED),
        label_style: Style | None = None,
        active_style: Style | None = None,
        hover_style: Style | None = None,
        ground_style: Style | None = None,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        disabled_style: Style | None = None,
        bands: RowBands | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        _reject_descriptions(labels, "CheckboxGroup")
        super().__init__(
            _options(labels),
            max_rows=None,
            wrap=False,
            commit=False,
            multi=True,
            marked=marked,
            mark_pair=mark_pair,
            ground_style=ground_style,
            focused=focused,
            label_style=label_style,
            disabled=disabled,
            disabled_items=disabled_items,
            disabled_style=disabled_style,
            bands=bands,
            theme=theme,
        )
        # The form bands: the explicit parameters re-aim the base's tokens.
        self._apply_form_bands(hover_style, active_style)
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
        the base's cursor-text style (the theme's ``accent``), the others in
        ``label_style``, a disabled row in ``disabled_style``, the mark
        column riding along -- and the band is the row pipeline's, the same
        form rule :class:`RadioGroup` renders by.  The cursor seat is
        :func:`~motui.kernel.glyphs.seat`, the mark column
        :func:`~motui.kernel.glyphs.pair_seat` padded to the pair's wider
        member.
        """
        style = self._disabled_style if disabled else (
            self._cursor_text_style if current else self._label_style
        )
        lead = glyphs.seat_width(self.marker)
        marked_glyph, unmarked_glyph = self.mark_pair
        glyph, other = (
            (marked_glyph, unmarked_glyph)
            if marked
            else (unmarked_glyph, marked_glyph)
        )
        segments = [
            Segment(glyphs.seat(self.marker) if current else " " * lead, style),
            Segment(glyphs.pair_seat(glyph, other), style),
            Segment(option.label, style),
        ]
        return Line(tuple(segments))

    def __repr__(self) -> str:
        return f"CheckboxGroup({self.labels!r}, index={self._index})"
