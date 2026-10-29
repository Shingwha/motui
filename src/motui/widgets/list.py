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
and ``end`` jump to the edges, ``on_click(pos)`` maps one of the
component's own rendered rows back onto an item (the counter rows carry
none) and leaves it pending, and ``activate()`` does the same for the
cursor row.  ``take()`` is the one-shot read (it clears the pick);
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
the focus tier sets: while it is ``False`` the
cursor row's band is ``rows.inactive`` and every other row renders
unchanged.  ``hover``
is the pointer tier's flag and :meth:`on_hover` its row-level half: the item
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
carry the band themselves -- then ``.clip(WrapMode.ELLIPSIS, width).fill(fitted.width, band)``:
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

from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from ..widgets.mark import MarkSet
from .strip import Keymap

__all__ = ["List"]

#: Private row-plan tokens for the two counter rows.  The token cannot be
#: the glyph itself: a host may pass the same string for ``more_up`` and
#: ``more_down`` (or any string), and the plan must still tell the rows
#: apart from each other and from an item index.
_ABOVE = object()
_BELOW = object()


class List(CursorWidget):
    """A cursor over ``items``, rendered as a ``window``-row view.

    ``index`` is the cursor -- a 0-based item index, clamped on assignment
    (``0`` for an empty list) -- and the item under it is taken by
    :meth:`on_action` and read once through :meth:`take`.  The window follows the cursor:
    :meth:`render` shows at most ``window`` item rows centred on it (half a
    window where the ends allow), an ``\u2191 N more`` row above when items
    fall before the window and a ``\u2193 N more`` row below when they fall
    after it; the counter rows carry no item and leave the cursor alone.
    An empty list renders no rows.  A cursor the current ``items`` no longer
    answer reads as no cursor: the rows still render, the marker is simply
    absent and :meth:`on_action` answers ``False``.

    ``window`` is the number of item rows rendered and must be at least 1
    (``ValueError`` otherwise).  ``prefix_jump`` arms :meth:`handle`'s
    printable-character jump.  ``glyphs`` is the row vocabulary (see the
    module docstring): each member is a plain string rendered as content,
    and an empty string disables the glyph and its seat -- ``cursor=""``
    starts every label at column 0, ``more_up=""`` drops the arrow from the
    counter row's seat.  The vocabulary is a row input: assign it to touch the
    widget.
    Styles resolve from the theme at render time through the row-band
    contract: the resting surface is ``rows.base``, the cursor row wears
    ``rows.active`` (``rows.inactive`` while unfocused) and the pointer's
    row ``rows.hover`` (D3: one token per signal), the counter rows
    ``text.muted`` and a disabled row ``text.faint``.  ``styles=`` replaces
    a whole role group; assigning ``theme`` or ``styles`` touches the
    widget, so a theme switch repaints a mounted list.
    """

    __slots__ = (
        "_hover_row",
        "disabled",
        "disabled_items",
        "glyphs",
        "items",
        "marked",
        "prefix_jump",
        "window",
    )

    #: The list owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The family table plus the marking key.
    keymap = Keymap({**CURSOR_KEYMAP, "space": "toggle"})

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
        #: ``_hover_row`` (:meth:`on_hover`).
        self.hover = False
        #: The marked items (:class:`~motui.widgets.mark.MarkSet`, raw item
        #: indices): :meth:`toggle` flips the cursor row's mark, and while
        #: the set is non-empty every item row leads with its
        #: ``[x] ``/``[ ] `` prefix.  The set is the host's to read, clear
        #: and fill.
        self.marked = MarkSet()
        # The item row the pointer is on, or ``None``; written by
        # ``on_hover``, read by ``render``.  ``None`` renders byte-for-byte
        # what the list always did.
        self._hover_row: int | None = None
        #: The whole control refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The item rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)

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

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        """The items the cursor walks."""
        return len(self.items)

    def _entry_at(self, index: int) -> object | None:
        """The item at visible row ``index`` (side-effect free)."""
        return self.items[index]

    def _cursor_disabled(self) -> Iterable[int]:
        """The item rows a move steps over and ``select`` refuses."""
        return self.disabled_items

    def _cursor_wraps(self) -> bool:
        """A data view clamps at its ends (D10); it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        """The whole-list disabled switch gates every cursor verb."""
        return not self.disabled

    def _page_size(self, size: int) -> int:
        """A page is the visible window, capped by the item count."""
        return min(size, self.window)

    def _is_disabled(self, index: int) -> bool:
        """Whether item ``index`` is disabled (the whole control or per item)."""
        return self.disabled or index in self.disabled_items

    # -- the verbs ---------------------------------------------------------------

    def activate(self) -> bool:
        """Leave the cursor item pending; ``False`` on no enabled item."""
        if self.selected is None or self._is_disabled(self.index):
            return False
        self._emit(self.selected)
        return True

    def toggle(self) -> bool:
        """Flip the cursor item's mark; ``True`` when there was one to flip.

        The marking gesture beside the cursor's own: the cursor item's mark
        flips in :attr:`marked`, and nothing else moves -- ``index`` and the
        pending result are the cursor's state, so a toggle never emits.
        ``False`` -- and no mark written -- for an empty list, a disabled
        control, or a disabled cursor row, the
        :meth:`~motui.widgets.choice.Select.toggle` rule.
        """
        if self.selected is None or self._is_disabled(self.index):
            return False
        self.marked.toggle(self.index)
        self.touch()
        return True

    def on_click(self, pos: Pos) -> bool:
        """Land the item rendered at block row ``pos.y``; ``True`` on a hit.

        ``pos.y`` is a 0-based row of this component's own ``render`` output
        -- exactly what :meth:`~motui.app.TUI.hit` reports --
        resolved through the same window arithmetic ``render`` emits
        (:meth:`_layout`): a counter row and every row past the rendered
        ones carry no item, so they answer ``False`` and change nothing.
        ``pos.x`` is ignored, and deliberately so: an item row owns the
        whole width.  A hit moves the cursor there (a state change, never a
        pick -- activation is the emitting verb).  A disabled control or
        item refuses the hit and changes nothing.
        """
        if self.disabled:
            return False
        layout = self._layout()
        if not 0 <= pos.y < len(layout):
            return False
        entry = layout[pos.y]
        if not isinstance(entry, int):  # a counter row: no item to land on
            return False
        if self._is_disabled(entry):
            return False
        self.select(entry)
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the item row under the pointer; ``True`` when the marking changed.

        The pointer tier's row-level half: ``pos.y`` is a 0-based row of
        this component's own ``render`` output, resolved through the same
        layout :meth:`on_click` reads -- a counter row carries no item and
        clears the marking, exactly as a row past the rendered ones does.
        The column is ignored, and ``None`` clears the marking (the pointer
        left).  The answer is whether the marked row changed, so a motion
        inside one row answers ``False``; :meth:`render` rests that row on
        ``rows.hover``, whatever row it is on (D3).
        """
        target: int | None = None
        if pos is not None:
            row = pos.y
            layout = self._layout()
            if 0 <= row < len(layout):
                entry = layout[row]
                if isinstance(entry, int):
                    target = entry
        changed = target != self._hover_row
        if changed:
            self._hover_row = target
            self.touch()
        return changed

    # -- the keyboard -----------------------------------------------------------

    def on_key(self, event: KeyEvent) -> bool:
        """Consume an event; ``True`` when the list took it.

        The routing table, in order: the event's key through
        :attr:`keymap` (the shared cursor table plus ``space: toggle``, and
        whatever a host rebound) and then its action; with
        :attr:`prefix_jump` armed, a :class:`~motui.kernel.events.KeyEvent`
        whose ``key`` is a single printable character jumps to the first
        item that starts with it (case-insensitively) and is consumed
        whether or not an item matched -- a printable typed at a focused
        list is the list's own gesture, never a leak to the host.
        Everything else -- ``enter``, ``tab``, the control chords, a
        :class:`~motui.kernel.events.PasteEvent` -- is declined, so the
        host and the focus tier keep the keys they own.  A disabled control
        declines everything.
        """
        if self.disabled or not isinstance(event, KeyEvent):
            return False
        name = event.key
        if name in self.keymap:
            return super().on_key(event)
        if self.prefix_jump and len(name) == 1 and name.isprintable():
            self._jump(name)
            return True
        return False

    def _jump(self, char: str) -> bool:
        """Move the cursor to the first item starting with ``char``; ``True`` on a landing.

        The prefix-jump rule, case-insensitive and always scanned from the
        top of the list ("the first item"), so the same key lands on the
        same row however the cursor wandered.  Disabled items are skipped
        like every other cursor gesture.  A miss moves nothing and leaves
        the pending result alone (no state changed).
        """
        needle = char.lower()
        for index, item in enumerate(self.items):
            if not self._is_disabled(index) and item.lower().startswith(needle):
                moved = index != self.index
                if moved:
                    self.select(index)
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
        self._sync_cursor()
        return self._cursor.window(self.window, anchor="center")

    def _layout(self) -> list[int | object]:
        """What each rendered row carries: an item index, or a counter token.

        :meth:`render` emits one line per entry and the hit mapping
        (:meth:`on_click` / :meth:`on_hover`) reads the same list back, so the
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
        if index == self.index:
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

    def render(self, c: Constraints) -> Surface:
        """The window of item rows and the counter rows, fitted to the width.

        The constraint carries the width; a ``max_height`` budget
        truncates the leading rows (the window never grows past the height
        it was offered).  Every row goes through the row-band contract
        (:func:`~motui.kernel.cell.rest`): the
        item rows and the counter rows alike are ``fit`` to ``c.width`` and
        rest on their resolved band -- the ground, the active band on the
        engaged row, the hover band on the pointer's row and the disabled
        band on a disabled item.  The surface is :meth:`Surface.clipped`,
        not padded, so the bytes a layout paints are the 1.x rows.
        """
        count = len(self.items)
        if count == 0:
            return Surface.clipped([], c.width)
        start, stop = self._visible_range()
        cursor_index = self.index
        rows: list[Line] = []
        for entry in self._layout():
            if isinstance(entry, int):
                item_disabled = self._is_disabled(entry)
                rows.append(
                    rest(
                        self._row(entry, item_disabled),
                        c.width,
                        self._band(
                            entry == cursor_index,
                            entry == self._hover_row,
                            item_disabled,
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
        return f"List({len(self.items)} items, index={self.index}, window={self.window})"
