"""List component: a cursor over a long sequence, rendered as a window.

:class:`List` is the toolkit's data list: ``items`` is a plain sequence of
strings, one row each, and the cursor's index is the one selection the host
steers.  The component never renders the whole sequence: it renders a
**window** of ``window`` rows around the cursor (half a window on either
side where the ends allow, so the window slides rather than scrolling the
cursor to its edge), led by a ``\u25b8`` cursor seat on the cursor row and
indented by its width elsewhere, plus an ``\u2191 N more`` / ``\u2193 N
more`` counter row wherever items fall outside the window.  A thousand
items therefore render ``window`` rows and at most two counter rows -- the
rows a pane can actually hold -- and the counters say the rest is there.

The ``glyphs`` vocabulary carries the marks (one keyword-only parameter):
``cursor`` leads the cursor row, ``more_up`` / ``more_down`` label the
counter rows, and ``check_on`` / ``check_off`` is the marked/unmarked pair
:attr:`marked` renders.  Every glyph is content, not style: it is rendered
in the row's own text style and never enters the theme.  A seat is measured through
:func:`~motui.kernel.glyphs.seat_width` (``visible_width``, never ``len``),
so a wide glyph takes its columns and every row's label still starts at one
column; an empty string disables the glyph and its whole seat, leaving no
dangling space.  A pair is padded through
:func:`~motui.kernel.glyphs.pair_seat`, so the marked and unmarked rows
share one column width.

The controller vocabulary is the peer of a table's: ``move(delta)`` steps
and **clamps** at the ends (a data view, not a menu cycle -- D10), ``home``
and ``end`` jump to the edges, ``click(row, col)`` maps one of the
component's own rendered rows back onto an item (the counter rows carry
none) and leaves it pending, and ``activate()`` does the same for the
cursor row.  ``take_result()`` is the one-shot read (it clears the pick);
any consumed keystroke clears it too, so a stale pick never survives the
next key.  ``disabled`` refuses every gesture, ``disabled_items`` marks
individual rows (the cursor steps over them), and a disabled row paints
``text.faint``.

``handle(event)`` is the list's keyboard door: ``up``/``down`` move,
``home``/``end`` jump, and -- with ``prefix_jump`` on, the default -- a key
whose name is a single printable character jumps to the first item starting
with that character, case-insensitively (a consumed printable, whether or
not an item matches).  With ``prefix_jump=False`` printables are left to
the host.

Only the kernel is imported: ``render`` is a pure function of the list and
``width``.  ``focused`` is the focus flag the focus tier sets
(:class:`~motui.kernel.document.Focusable`): while it is ``False`` the
cursor row's band is ``rows.inactive`` and every other row renders
unchanged.  ``hover``
is the pointer tier's flag and :meth:`hover_at` its row-level half: the item
row under the pointer wears ``rows.hover`` (the pointer's own token, D3),
whatever row it is on.  The marking starts
``None``, so an un-hovered list renders byte-for-byte what it always did.

**Marking is a third, sticky emphasis.**  ``marked`` is the public
:class:`~motui.widgets.mark.MarkSet` of item indices and :meth:`toggle`
flips the cursor row's mark -- the host routes the key (the library binds
none: ``space`` stays declined by :meth:`handle`, and ``break``/``space``-
style chords are the host's own dispatch).  While the set is non-empty every
item row leads with the three-column ``[x] ``/``[ ] `` prefix
(:func:`~motui.kernel.glyphs.pair_seat`) after the cursor's marker seat; an
empty set renders exactly the bytes the list always did.

**The row-band contract.**  Every row the list emits resolves its band from
the theme's row roles through :meth:`~motui.kernel.theme.RowStyles.band`:
``rows.base`` at rest, ``rows.active`` on the focused cursor row and
``rows.inactive`` on the unfocused one, ``rows.hover`` under the pointer
(D3: one token per signal) and ``rows.disabled`` on a disabled row.
``styles=`` may replace the ``rows`` group (and any other).  A row is its
text-styled
segments -- the marker seat, the mark prefix and the label, which no longer
carry the band themselves -- then ``.fit(width).fill(fitted.width, band)``:
the W1 primitive, the band underneath, the text styles on top.  The band merges
under the row's own cells -- a pill behind the text, never a ribbon
across the pane; a full-surface band is the host's container's job
(``Padding(fill_style=...)`` / ``Panel(frame=False, style=...)``, which
fill every row to the width they are handed).  A resting row rests on the
ground, the engaged row (the cursor's or the pointer's) swaps the band, and an
unfocused cursor row wears ``rows.inactive``.  The
fill is skipped while the band is ``NONE`` -- the default theme's ground
and both its engaged bands -- so resting rows render exactly the bytes
they always did, and so do the cursor row and the hovered row until a
host themes them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..widgets.cursor import Cursor
from ..kernel.events import Event, KeyEvent
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat, seat_width
from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.layout import Constraints, as_constraints
from ..widgets.mark import MarkSet
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["List"]

#: Private row-plan tokens for the two counter rows.  The token cannot be
#: the glyph itself: a host may pass the same string for ``more_up`` and
#: ``more_down`` (or any string), and the plan must still tell the rows
#: apart from each other and from an item index.
_ABOVE = object()
_BELOW = object()


class List(Widget):
    """A cursor over ``items``, rendered as a ``window``-row view.

    ``index`` is the cursor -- a 0-based item index, clamped on assignment
    (``0`` for an empty list) -- and the item under it is taken by
    :meth:`activate` and read once through :meth:`take_result`.  The window follows the cursor:
    :meth:`render` shows at most ``window`` item rows centred on it (half a
    window where the ends allow), an ``\u2191 N more`` row above when items
    fall before the window and a ``\u2193 N more`` row below when they fall
    after it; the counter rows carry no item and leave the cursor alone.
    An empty list renders no rows.  A cursor the current ``items`` no longer
    answer reads as no cursor: the rows still render, the marker is simply
    absent and :meth:`activate` answers ``False``.

    ``window`` is the number of item rows rendered and must be at least 1
    (``ValueError`` otherwise).  ``prefix_jump`` arms :meth:`handle`'s
    printable-character jump.  ``glyphs`` is the row vocabulary (see the
    module docstring): each member is a plain string rendered as content,
    and an empty string disables the glyph and its seat -- ``cursor=""``
    starts every label at column 0, ``more_up=""`` drops the arrow from the
    counter row's seat.  The vocabulary is a row input and part of
    :meth:`revision`.
    Styles resolve from the theme at render time through the row-band
    contract: the resting surface is ``rows.base``, the cursor row wears
    ``rows.active`` (``rows.inactive`` while unfocused) and the pointer's
    row ``rows.hover`` (D3: one token per signal), the counter rows
    ``text.muted`` and a disabled row ``text.faint``.  ``styles=`` replaces
    a whole role group; ``theme`` and ``styles`` are part of
    :meth:`revision`, so a theme switch repaints a mounted list.
    """

    __slots__ = (
        "_hover_row",
        "_index",
        "_pending",
        "disabled",
        "disabled_items",
        "glyphs",
        "items",
        "marked",
        "prefix_jump",
        "window",
    )

    def __init__(
        self,
        items: Sequence[str] = (),
        *,
        window: int = 8,
        prefix_jump: bool = True,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.items = list(items)
        if window < 1:
            raise ValueError(f"window must be at least 1 row, got {window}")
        self.window = window
        self.prefix_jump = prefix_jump
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = False
        self.glyphs = glyphs
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        #: The marked items (:class:`~motui.widgets.mark.MarkSet`, raw item
        #: indices): :meth:`toggle` flips the cursor row's mark, and while
        #: the set is non-empty every item row leads with its
        #: ``[x] ``/``[ ] `` prefix.  The set is the host's to read, clear
        #: and fill.
        self.marked = MarkSet()
        self._index = 0
        # The item row the pointer is on, or ``None``; written by
        # ``hover_at``, read by ``render``.  ``None`` renders byte-for-byte
        # what the list always did.
        self._hover_row: int | None = None
        #: The whole control refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The item rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)
        # The pending one-shot pick: written by ``activate`` / a landing
        # ``click``, read once by ``take_result`` and cleared by every
        # consumed key.
        self._pending: str | None = None

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The surface one row rests on: :meth:`RowStyles.band`, by precedence.

        The cursor row wears ``rows.active`` while focused and
        ``rows.inactive`` while not; the pointer's row ``rows.hover`` and a
        resting row ``rows.base``.  The ``rows`` group comes from
        ``styles`` when overridden, else the theme.
        """
        return self.group("rows").band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor's item index (``0`` while the list is empty)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = Cursor(len(self.items)).clamp(value)

    def _cursor(self) -> Cursor:
        """The cursor value over the current items and disabled set."""
        return Cursor(
            len(self.items),
            index=self._index,
            disabled=self.disabled_items,
        )

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` enabled items, clamped at the ends.

        The clamp is the table's deliberate opposite of a menu cycle (D10):
        a list is a data view, so the first and last items are real edges.
        ``disabled_items`` are stepped over, and a disabled control moves
        nowhere.  The step clears a pending result -- landed or not -- so a
        stale pick never survives the next key.
        """
        self._pending = None
        if self.disabled or delta == 0:
            return False
        cursor = self._cursor()
        moved = cursor.move(delta)
        self._index = cursor.index
        return moved

    def home(self) -> bool:
        """Jump to the first enabled item; ``True`` when the cursor moved."""
        self._pending = None
        if self.disabled:
            return False
        cursor = self._cursor()
        moved = cursor.home()
        self._index = cursor.index
        return moved

    def end(self) -> bool:
        """Jump to the last enabled item; ``True`` when the cursor moved."""
        self._pending = None
        if self.disabled:
            return False
        cursor = self._cursor()
        moved = cursor.end()
        self._index = cursor.index
        return moved

    def _is_disabled(self, index: int) -> bool:
        """Whether item ``index`` is disabled (the whole control or per item)."""
        return self.disabled or index in self.disabled_items

    def _current(self) -> str | None:
        """The enabled item under the cursor, or ``None`` (empty, stale, disabled)."""
        if 0 <= self._index < len(self.items) and not self._is_disabled(self._index):
            return self.items[self._index]
        return None

    def activate(self) -> bool:
        """Leave the cursor's item pending; ``True`` when there was one to take.

        The list's :class:`~motui.kernel.document.Activable` verb: a host
        routes the return key here and reads the result once through
        :meth:`take_result`.  ``False`` -- and nothing pending -- for an
        empty list, a disabled control, or a disabled cursor row.
        """
        current = self._current()
        self._pending = current
        return current is not None

    def take_result(self) -> str | None:
        """Read the pending pick once and clear it (the ``Resultful`` door)."""
        value = self._pending
        self._pending = None
        return value

    def toggle(self) -> bool:
        """Flip the cursor item's mark; ``True`` when there was one to flip.

        The marking gesture beside the cursor's own: the cursor item's mark
        flips in :attr:`marked`, and nothing else moves -- ``index`` and
        the pending result are the cursor's state.  The library binds no key
        to it (``space`` stays the host's, see :meth:`handle`), so a host
        routes its own mark key here.  ``False`` -- and no mark written --
        for an empty list, a disabled control, or a disabled cursor row,
        the :meth:`~motui.widgets.choice.Select.toggle` rule.
        """
        if self._current() is None:
            return False
        self.marked.toggle(self._index)
        return True

    def click(self, row: int, col: int) -> bool:
        """Land the item rendered at block row ``row``; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own ``render`` output
        -- exactly what :meth:`~motui.app.TUI.hit` reports --
        resolved through the same window arithmetic ``render`` emits
        (:meth:`_layout`): a counter row and every row past the rendered
        ones carry no item, so they answer ``False`` and change nothing.
        ``col`` is ignored, and deliberately so: an item row owns the whole
        width.  A hit moves the cursor there and leaves that item pending
        (the radio family's contract: a landing click is a pick, read once
        through :meth:`take_result`).  A disabled control or item refuses
        the hit and changes nothing.
        """
        if self.disabled:
            return False
        layout = self._layout()
        if not 0 <= row < len(layout):
            return False
        entry = layout[row]
        if not isinstance(entry, int):  # a counter row: no item to land on
            return False
        if self._is_disabled(entry):
            return False
        self._index = entry
        self._pending = self.items[entry]
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the item row under a rendered row; ``True`` when the marking changed.

        The pointer tier's row-level half: ``row`` is a 0-based row of this
        component's own ``render`` output, resolved through the same layout
        :meth:`click` reads -- a counter row carries no item and clears the
        marking, exactly as a row past the rendered ones does.  ``col`` is
        ignored like ``click``'s, and a negative ``row`` clears the marking
        (the pointer left).  The answer is whether the marked row changed,
        so a motion inside one row answers ``False``; :meth:`render` rests
        that row on ``rows.hover``, whatever row it is on (D3).
        """
        target: int | None = None
        if row >= 0:
            layout = self._layout()
            if 0 <= row < len(layout):
                entry = layout[row]
                if isinstance(entry, int):
                    target = entry
        changed = target != self._hover_row
        self._hover_row = target
        return changed

    # -- the keyboard -----------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Consume an event; ``True`` when the list took it.

        The routing table, in order: ``up``/``down`` move the cursor one item
        and are consumed; ``home``/``end`` jump to the edges and are
        consumed; with :attr:`prefix_jump` armed, a
        :class:`~motui.kernel.events.KeyEvent` whose ``key`` is a single
        printable character jumps to the first item that starts with it
        (case-insensitively) and is consumed whether or not an item matched
        -- a printable typed at a focused list is the list's own gesture,
        never a leak to the host.  Everything else -- ``enter``, ``tab``,
        the control chords, a :class:`~motui.kernel.events.PasteEvent` -- is
        declined, so the host and the focus tier keep the keys they own.
        Every consumed key clears a pending result; a disabled control
        declines everything.
        """
        if self.disabled or not isinstance(event, KeyEvent):
            return False
        name = event.key
        if name == "up":
            self.move(-1)
            return True
        if name == "down":
            self.move(1)
            return True
        if name == "home":
            self.home()
            return True
        if name == "end":
            self.end()
            return True
        if self.prefix_jump and len(name) == 1 and name.isprintable():
            self._jump(name)
            return True
        return False

    def _jump(self, char: str) -> bool:
        """Move the cursor to the first item starting with ``char``; ``True`` on a landing.

        The prefix-jump rule, case-insensitive and always scanned from the
        top of the list ("the first item"), so the same key lands on the
        same row however the cursor wandered.  Disabled items are skipped
        like every other cursor gesture.  A miss moves nothing; either way
        the key was consumed and a pending result is cleared.
        """
        self._pending = None
        needle = char.lower()
        for index, item in enumerate(self.items):
            if not self._is_disabled(index) and item.lower().startswith(needle):
                moved = index != self._index
                self._index = index
                return moved
        return False

    # -- the window -------------------------------------------------------------

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` item indices rendered, one ``window`` wide.

        The centring :class:`~motui.widgets.cursor.Cursor` policy: half
        a window on either side of the cursor where the items allow, clamped
        at both ends, so the cursor is always inside the window and the
        window slides one row at a time near an edge.
        """
        return self._cursor().window(self.window, anchor="center")

    def _layout(self) -> list[int | object]:
        """What each rendered row carries: an item index, or a counter token.

        :meth:`render` emits one line per entry and the hit mapping
        (:meth:`click` / :meth:`hover_at`) reads the same list back, so the
        list's row arithmetic lives in exactly one place.  An ``int`` entry
        is the item's index; the private ``_ABOVE`` / ``_BELOW`` tokens
        name the counter rows that carry no item -- above the window and
        below it -- and are deliberately not the configured glyphs, which a
        host may repeat.
        """
        count = len(self.items)
        if count == 0:
            return []
        start, stop = self._visible_range()
        layout: list[int | object] = []
        if start > 0:
            layout.append(_ABOVE)
        layout.extend(range(start, stop))
        if stop < count:
            layout.append(_BELOW)
        return layout

    def _row(self, index: int, disabled: bool = False) -> Line:
        """One item row: the marker seat, the mark, the item text.

        The segments carry their text styles only -- the marker seat, the
        mark prefix and the label in ``text.base`` (``text.faint`` when
        disabled), none of them carrying the band -- and the band is the row
        pipeline's (:func:`~motui.kernel.cell.rest`):
        ``rows.base`` at rest, ``rows.active`` on the focused cursor row
        (``rows.inactive`` while unfocused), ``rows.hover`` on the pointer's
        row and ``rows.disabled`` on a disabled row.  The cursor seat is
        ``seat(marker)`` and the other rows are indented by its width
        (``0`` when the marker is ``""``).  While :attr:`marked` holds
        anything every item row carries its pair's seat
        (:func:`~motui.kernel.glyphs.pair_seat`), padded to the pair's
        wider member, after the marker seat; an empty set renders the
        two-segment row the list always emitted.
        """
        style = self.group("text").faint if disabled else self.group("text").base
        if index == self._index:
            lead = seat(self.glyphs.cursor)
        else:
            lead = " " * seat_width(self.glyphs.cursor)
        segments = [Segment(lead, style)]
        if len(self.marked):
            marked = index in self.marked
            first, second = self.glyphs.check_on, self.glyphs.check_off
            glyph, other = (first, second) if marked else (second, first)
            segments.append(Segment(pair_seat(glyph, other), style))
        segments.append(Segment(self.items[index], style))
        return Line(tuple(segments))

    def revision(self) -> object:
        """The list's value snapshot: items, cursor, marks, glyphs and bands.

        Every row input in one tuple -- the items (a copy of the host's
        list, so an in-place edit moves it), the cursor, the row under the
        pointer, the marks (their ascending snapshot: the mark column is a
        row input while anything is marked), the four row glyphs, the
        window size, the focus flag, the whole-control
        disabled flag, the disabled item set, the theme and the ``styles``
        overrides (the bands and text roles resolve from them at render
        time).  A pending result is deliberately out (no row reads it), and
        so is ``prefix_jump`` (it routes keys, it paints nothing).  The
        snapshot is what lets a **sealed** list's cursor band -- or a flipped
        mark -- finally reach the screen (D4).
        """
        return (
            tuple(self.items),
            self._index,
            self._hover_row,
            tuple(self.marked),
            self.glyphs,
            self.window,
            self.focused,
            self.disabled,
            tuple(sorted(self.disabled_items)),
            self.theme,
            self.styles,
        )

    def render(self, c: Constraints | int) -> Surface:
        """The window of item rows and the counter rows, fitted to the width.

        A bare ``int`` is the 1.x spelling and is normalized through
        :func:`motui.kernel.layout.as_constraints`; a ``max_height`` budget
        truncates the leading rows (the window never grows past the height
        it was offered).  Every row goes through the row-band contract
        (:func:`~motui.kernel.cell.rest`): the
        item rows and the counter rows alike are ``fit`` to ``c.width`` and
        rest on their resolved band -- the ground, the active band on the
        engaged row, the hover band on the pointer's row and the disabled
        band on a disabled item.  The surface is :meth:`Surface.clipped`,
        not padded, so the bytes a layout paints are the 1.x rows.
        """
        c = as_constraints(c)
        count = len(self.items)
        if count == 0:
            return Surface.clipped([], c.width)
        start, stop = self._visible_range()
        rows: list[Line] = []
        for entry in self._layout():
            if isinstance(entry, int):
                item_disabled = self._is_disabled(entry)
                rows.append(
                    rest(
                        self._row(entry, item_disabled),
                        c.width,
                        self._band(
                            entry == self._index, entry == self._hover_row, item_disabled
                        ),
                    )
                )
            elif entry is _ABOVE:  # the items before the window
                rows.append(
                    rest(
                        Line.from_text(
                            f"{seat(self.glyphs.more_up)}{start} more",
                            self.group("text").muted,
                        ),
                        c.width,
                        self._band(False, False),
                    )
                )
            else:  # _BELOW: the items past the window's last row
                rows.append(
                    rest(
                        Line.from_text(
                            f"{seat(self.glyphs.more_down)}{count - stop} more",
                            self.group("text").muted,
                        ),
                        c.width,
                        self._band(False, False),
                    )
                )
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"List({len(self.items)} items, index={self._index}, window={self.window})"
