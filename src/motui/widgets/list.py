"""List component: a cursor over a long sequence, rendered as a window.

:class:`List` is the toolkit's data list: ``items`` is a plain sequence of
strings, one row each, and the cursor's index is the one selection the host
steers.  The component never renders the whole sequence: it renders a
**window** of ``window`` rows around the cursor (half a window on either
side where the ends allow, so the window slides rather than scrolling the
cursor to its edge), led by a ``\u25b8`` marker on the cursor row and
indented by its width elsewhere, plus an ``\u2191 N more`` / ``\u2193 N
more`` counter row wherever items fall outside the window.  A thousand
items therefore render ``window`` rows and at most two counter rows -- the
rows a pane can actually hold -- and the counters say the rest is there.

The controller vocabulary is the peer of a table's: ``move(delta)`` steps
and **clamps** at the ends (a data view, not a menu cycle -- D10), ``home``
and ``end`` jump to the edges, ``click(row, col)`` maps one of the
component's own rendered rows back onto an item (the counter rows carry
none) and lands it in :attr:`chosen`, and ``activate()`` does the same for
the cursor row.  ``chosen`` is the item the host reads once; any consumed
keystroke clears it, so a stale pick never survives the next key.

``handle(event)`` is the list's keyboard door: ``up``/``down`` move,
``home``/``end`` jump, and -- with ``prefix_jump`` on, the default -- a key
whose name is a single printable character jumps to the first item starting
with that character, case-insensitively (a consumed printable, whether or
not an item matches).  With ``prefix_jump=False`` printables are left to
the host.

Only the kernel is imported: ``render`` is a pure function of the list and
``width``.  ``focused`` is the focus flag the focus tier sets
(:class:`~motui.kernel.block.Focusable`): while it is ``False`` the
cursor row's band merges the theme's ``dim`` -- the band stays
legible but loses weight, and every other row renders unchanged.
``hover``
is the pointer tier's flag and :meth:`hover_at` its row-level half: the item
row under the pointer wears the theme's ``ground_active`` band, the
engaged surface the cursor row wears too (D2).  The marking starts
``None``, so an un-hovered list renders byte-for-byte what it always did.

**Marking is a third, sticky emphasis.**  ``marked`` is the public
:class:`~motui.kernel.mark.MarkSet` of item indices and :meth:`toggle`
flips the cursor row's mark -- the host routes the key (the library binds
none: ``space`` stays declined by :meth:`handle`, and ``break``/``space``-
style chords are the host's own dispatch).  While the set is non-empty every
item row leads with the three-column ``[x] ``/``[ ] `` prefix
(:func:`~motui.kernel.mark.mark_prefix`) after the cursor's marker seat; an
empty set renders exactly the bytes the list always did.

**The row-band contract.**  Every row the list emits resolves its bands
once, at construction: ``_ground = _pick(ground_style, "ground")`` is the
resting surface, ``_selected_style`` (the cursor row's band) and
``_hover_style`` (the pointer's) both pick ``"ground_active"`` -- the
engaged surface, shared by the keyboard cursor and the hovered row (D2).
A row is its text-styled segments -- the marker seat, the mark prefix and
the label, which no longer carry the band themselves -- then
``.fit(width).fill(width, band)``: the W1 primitive, the band underneath,
the text styles on top, and the surface spanning the painting width.  A
resting row rests on the ground, the engaged row (the cursor's or the
pointer's) swaps the band, and an unfocused cursor row merges the theme's
``dim`` onto it, as today.  The fill is skipped while the band is ``NONE``
-- the default theme's ground -- so resting rows render exactly the bytes
they always did; the engaged row's band now spans the width, the
registered default change.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.events import Key, Paste
from ..kernel.lines import Line, Segment
from ..kernel.mark import MarkSet, mark_prefix
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed

__all__ = ["MARKER", "List"]

#: The cursor row's leading marker (the table family's own pointer shape).
MARKER = "\u25b8"

#: The counter rows' tokens: ``"<token> N more"`` above / below the window.
MORE_UP = "\u2191"
MORE_DOWN = "\u2193"


class List(Themed):
    """A cursor over ``items``, rendered as a ``window``-row view.

    ``index`` is the cursor -- a 0-based item index, clamped on assignment
    (``0`` for an empty list) -- and the item under it is read through
    :meth:`activate` / :attr:`chosen`.  The window follows the cursor:
    :meth:`render` shows at most ``window`` item rows centred on it (half a
    window where the ends allow), an ``\u2191 N more`` row above when items
    fall before the window and a ``\u2193 N more`` row below when they fall
    after it; the counter rows carry no item and leave the cursor alone.
    An empty list renders no rows.  A cursor the current ``items`` no longer
    answer reads as no cursor: the rows still render, the marker is simply
    absent and :meth:`activate` answers ``False``.

    ``window`` is the number of item rows rendered and must be at least 1
    (``ValueError`` otherwise).  ``prefix_jump`` arms :meth:`handle`'s
    printable-character jump.  Styles resolve from the theme at
    construction through the row-band contract: ``ground_style`` (the
    resting surface, the theme's ``ground``) rests under every row, the
    cursor row and the pointer's row both wear ``ground_active`` (D2), and
    the counter rows the theme's ``dim``.
    """

    __slots__ = (
        "_dim",
        "_ground",
        "_hover_row",
        "_hover_style",
        "_index",
        "_selected_style",
        "chosen",
        "focused",
        "hover",
        "items",
        "marked",
        "prefix_jump",
        "theme",
        "window",
    )

    def __init__(
        self,
        items: Sequence[str] = (),
        *,
        window: int = 8,
        ground_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
        prefix_jump: bool = True,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.items = list(items)
        if window < 1:
            raise ValueError(f"window must be at least 1 row, got {window}")
        self.window = window
        self.prefix_jump = prefix_jump
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        #: The marked items (:class:`~motui.kernel.mark.MarkSet`, raw item
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
        #: The pending pick: the item ``activate`` / a landing ``click``
        #: took, read once by the host, cleared by the next consumed key.
        self.chosen: str | None = None
        # Styles resolve once, at construction: theme fields only.
        self._ground = self._pick(ground_style, "ground")
        self._selected_style = self._pick(None, "ground_active")
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "ground_active")

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor's item index (``0`` while the list is empty)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        count = len(self.items)
        self._index = min(max(value, 0), count - 1) if count else 0

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` items, clamped at the ends; ``True`` on a move.

        The clamp is the table's deliberate opposite of a menu cycle (D10):
        a list is a data view, so the first and last items are real edges.
        The step clears a pending :attr:`chosen` -- landed or not -- so a
        stale pick never survives the next key.
        """
        self.chosen = None
        count = len(self.items)
        if count == 0 or delta == 0:
            return False
        target = min(max(self._index + delta, 0), count - 1)
        moved = target != self._index
        self._index = target
        return moved

    def home(self) -> bool:
        """Jump to the first item; ``True`` when the cursor moved."""
        self.chosen = None
        if not self.items or self._index == 0:
            return False
        self._index = 0
        return True

    def end(self) -> bool:
        """Jump to the last item; ``True`` when the cursor moved."""
        self.chosen = None
        if not self.items:
            return False
        last = len(self.items) - 1
        moved = self._index != last
        self._index = last
        return moved

    def _current(self) -> str | None:
        """The item under the cursor, or ``None`` (empty or a stale index)."""
        if 0 <= self._index < len(self.items):
            return self.items[self._index]
        return None

    def activate(self) -> bool:
        """Take the cursor's item into :attr:`chosen`; ``True`` when there was one.

        The list's :class:`~motui.kernel.block.Activable` verb: a host
        routes the return key here, reads ``chosen`` once and resets it to
        ``None``.  ``False`` -- and ``chosen`` stays ``None`` -- for an
        empty list or a cursor the current items no longer answer.
        """
        self.chosen = self._current()
        return self.chosen is not None

    def toggle(self) -> bool:
        """Flip the cursor item's mark; ``True`` when there was one to flip.

        The marking gesture beside the cursor's own: the cursor item's mark
        flips in :attr:`marked`, and nothing else moves -- ``index`` and
        :attr:`chosen` are the cursor's state.  The library binds no key to
        it (``space`` stays the host's, see :meth:`handle`), so a host
        routes its own mark key here.  ``False`` -- and no mark written --
        for an empty list or a cursor the current items no longer answer,
        the :meth:`~motui.widgets.choice.Select.toggle` rule.
        """
        if self._current() is None:
            return False
        self.marked.toggle(self._index)
        return True

    def click(self, row: int, col: int) -> bool:
        """Land the item rendered at block row ``row`` in :attr:`chosen`; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own ``render`` output
        -- exactly what :meth:`~motui.app.TUI.hit_test` reports --
        resolved through the same window arithmetic ``render`` emits
        (:meth:`_layout`): a counter row and every row past the rendered
        ones carry no item, so they answer ``False`` and change nothing.
        ``col`` is ignored, and deliberately so: an item row owns the whole
        width.  A hit moves the cursor there and takes that item into
        :attr:`chosen` (the radio family's contract: a landing click is a
        pick, read once by the host).
        """
        layout = self._layout()
        if not 0 <= row < len(layout):
            return False
        entry = layout[row]
        if not isinstance(entry, int):  # a counter row: no item to land on
            return False
        self._index = entry
        self.chosen = self.items[entry]
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
        that row on the theme's ``ground_active`` band.
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

    def handle(self, event: Key | Paste) -> bool:
        """Consume an event; ``True`` when the list took it.

        The routing table, in order: ``up``/``down`` move the cursor one item
        and are consumed; ``home``/``end`` jump to the edges and are
        consumed; with :attr:`prefix_jump` armed, a :class:`Key` whose name
        is a single printable character jumps to the first item that starts
        with it (case-insensitively) and is consumed whether or not an item
        matched -- a printable typed at a focused list is the list's own
        gesture, never a leak to the host.  Everything else -- ``enter``,
        ``tab``, the control chords, a :class:`Paste` -- is declined, so the
        host and the focus tier keep the keys they own.  Every consumed key
        clears a pending :attr:`chosen`.
        """
        if not isinstance(event, Key):
            return False
        name = event.name
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
        same row however the cursor wandered.  A miss moves nothing; either
        way the key was consumed and a pending pick is cleared.
        """
        self.chosen = None
        needle = char.lower()
        for index, item in enumerate(self.items):
            if item.lower().startswith(needle):
                moved = index != self._index
                self._index = index
                return moved
        return False

    # -- the window -------------------------------------------------------------

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` item indices rendered, one ``window`` wide.

        The window is centred on the cursor with half a window of rows on
        either side where the items allow, and clamped at the ends, so the
        cursor is always inside it and the window slides one row at a time
        near an edge.
        """
        count = len(self.items)
        if count <= self.window:
            return 0, count
        start = min(max(self._index - self.window // 2, 0), count - self.window)
        return start, start + self.window

    def _layout(self) -> list[str | int]:
        """What each rendered row carries: an item index, or a counter token.

        :meth:`render` emits one line per entry and the hit mapping
        (:meth:`click` / :meth:`hover_at`) reads the same list back, so the
        list's row arithmetic lives in exactly one place.  An ``int`` entry
        is the item's index; a string names a counter row that carries no
        item: ``MORE_UP`` above the window, ``MORE_DOWN`` below it.
        """
        count = len(self.items)
        if count == 0:
            return []
        start, stop = self._visible_range()
        layout: list[str | int] = []
        if start > 0:
            layout.append(MORE_UP)
        layout.extend(range(start, stop))
        if stop < count:
            layout.append(MORE_DOWN)
        return layout

    def _band(self, current: bool, hovered: bool) -> Style:
        """The surface one row rests on: the ground, or the engaged band.

        A resting row rests on ``_ground``; the cursor row carries
        ``_selected_style`` (``ground_active``) with the theme's ``dim``
        merged onto it while unfocused -- the band stays legible but loses
        weight; the pointer's row carries ``_hover_style`` (``ground_active``
        as well -- D2: the keyboard cursor and the hover share the one
        token), stacked over the cursor's band where the two meet.
        """
        if not current and not hovered:
            return self._ground
        band = self._selected_style if current else self._hover_style
        if current and not self.focused:
            band = band.merge(self._dim)  # unfocused: keep the hue, lose the weight
        if hovered:
            band = band.merge(self._hover_style)
        return band

    def _rest(
        self, line: Line, width: int, current: bool = False, hovered: bool = False
    ) -> Line:
        """One row on its band: the text-styled segments, ``fit``, band under.

        The row-band contract's rendering half: ``fit`` trims to ``width``,
        then the band :meth:`_band` resolved rests *underneath* the segments
        through the W1 primitive -- the band the base, the text styles on
        top (the Rich ``Padding(style=...)`` rule) -- and the row grows to
        the full painting width, the surface a grounded row wears.  The fill
        is skipped when the band is ``NONE`` (the default theme's ground):
        a resting row is then exactly the row it always was, byte for byte,
        while an engaged row's band -- and any themed ground -- spans the
        width (the registered default change).
        """
        fitted = line.fit(width)
        band = self._band(current, hovered)
        return fitted if band == NONE else fitted.fill(width, band)

    def _row(self, index: int) -> Line:
        """One item row: the marker (or its indent), the mark, the item text.

        The segments carry their text styles only -- the marker seat, the
        mark prefix and the label plain, none of them carrying the band --
        and the band is the row pipeline's (:meth:`_rest`): the ground at
        rest, ``ground_active`` on the cursor row (the theme's ``dim``
        merged onto it while unfocused) and on the pointer's row.  While
        :attr:`marked` holds anything every item row carries the ``[x] ``
        / ``[ ] `` prefix after the marker seat; an empty set renders the
        two-segment row the list always emitted.
        """
        lead = MARKER + " " if index == self._index else " " * (len(MARKER) + 1)
        segments = [Segment(lead)]
        if len(self.marked):
            segments.append(Segment(mark_prefix(index in self.marked)))
        segments.append(Segment(self.items[index]))
        return Line(tuple(segments))

    def revision(self) -> object:
        """The list's value snapshot: items, cursor, marks and styles.

        Every row input in one tuple -- the items (a copy of the host's
        list, so an in-place edit moves it), the cursor, the row under the
        pointer, the marks (their ascending snapshot: the mark column is a
        row input while anything is marked), the window size, the focus
        flag and the four resolved styles.  A pending :attr:`chosen` is
        deliberately out (no row reads it), and so is ``prefix_jump`` (it
        routes keys, it paints nothing).  The snapshot is what lets a
        **sealed** list's cursor band -- or a flipped mark -- finally reach
        the screen (D4).
        """
        return (
            tuple(self.items),
            self._index,
            self._hover_row,
            tuple(self.marked),
            self.window,
            self.focused,
            self._ground,
            self._selected_style,
            self._dim,
            self._hover_style,
        )

    def render(self, width: int) -> list[Line]:
        """The window of item rows and the counter rows, fitted to ``width``.

        Every row goes through the row-band contract (:meth:`_rest`): the
        item rows and the counter rows alike are ``fit`` to ``width`` and
        rest on their resolved band -- the ground, or ``ground_active`` on
        the engaged row.
        """
        count = len(self.items)
        if count == 0:
            return []
        start, stop = self._visible_range()
        rows: list[Line] = []
        for entry in self._layout():
            if isinstance(entry, int):
                rows.append(
                    self._rest(
                        self._row(entry),
                        width,
                        entry == self._index,
                        entry == self._hover_row,
                    )
                )
            elif entry == MORE_UP:
                rows.append(
                    self._rest(
                        Line.from_text(f"{MORE_UP} {start} more", self._dim), width
                    )
                )
            else:  # MORE_DOWN: the items past the window's last row
                rows.append(
                    self._rest(
                        Line.from_text(f"{MORE_DOWN} {count - stop} more", self._dim),
                        width,
                    )
                )
        return rows

    def __repr__(self) -> str:
        return f"List({len(self.items)} items, index={self._index}, window={self.window})"
