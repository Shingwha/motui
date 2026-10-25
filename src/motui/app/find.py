"""Find: the search tier -- its own query row over the document, and its matches.

:class:`Find` packages the whole incremental search the way
:class:`~motui.app.command_palette.CommandPalette` packages its command list: a query
:class:`~motui.widgets.textfield.Input` row the tier owns (no host editor
feeds it), the **matches** that row's text finds in a document, a cursor over
them, and an overlay that paints them over the composed frame.  Opening
resets the query; typing re-addresses the matches; ``enter``/``down`` step to
the next match and ``up`` to the previous one -- the ends wrap -- and
``escape`` closes.  Every change **reveals** the current match through the
driver (:meth:`~motui.app.Runtime.reveal`), so the tier owns no scrolling of
its own; "bring this address on screen" is the kernel-side ability
(``Viewport.scroll_to``), not a hole opened for search.

**What is searched.**  The document of the pane **focused** when the query
changed -- the same resolution ``tui.reveal`` scrolls -- every block in
document order, fixed-region blocks included (they are part of the document:
they highlight in place, and revealing one moves nothing because a pinned
block never scrolls away).  A match is a document address
``(bid, row, start, end)``: the block id, the 0-based row within that block
at the width the pane was last laid out at, and the hit's display-column
range.  The width travels with the address -- another width wraps other
rows -- so a frame laid out at a different width paints **no** highlight
until the next query change re-addresses the matches, the stance the
selection overlay takes for a reflow.  Matching is a case-insensitive
substring (lower-case comparison) and non-overlapping, in document order.

**The contract.**  Like every controller of the assembly tier, the host
drives it: ``handle(event) -> bool`` consumes one event while the tier is
open (``escape`` closes it) and answers whether the event was the tier's, so
the host routes it between the chrome and the gestures and repaints on a
``True`` (the ``CommandPalette`` reading).  A closed tier consumes nothing and
paints nothing; the overlay stays **registered** for the controller's life
(the ``Toasts`` rule -- ``detach()`` unregisters *and* goes inert), so open
and close only flip the state the paint and the routing read.  There is
**no ``chosen``**: search is a continuing state, not a pick.  The host reads
:attr:`matches`/:attr:`index` for a status readout of its own.

The paint is the pure half: the query row lands on the frame's **bottom
row** on the theme's ``overlays.toast`` band, with an ``(i/n)`` counter at
its right end, and every match is cut out of its row and merged under
:attr:`~motui.kernel.theme.TextStyles.selection` -- the current one under
:attr:`~motui.kernel.theme.SurfaceStyles.hover` again.  Closed, the composed
layout comes back exactly as it stands.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ..kernel.events import Event, KeyEvent, PasteEvent
from ..kernel.frame import splice_row
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, cut_line, overlay
from ..kernel.text import WrapMode, visible_width
from ..kernel.theme import DEFAULT_THEME, Theme
from ..kernel.layout import ScreenLayout
from ..widgets.textfield import Input
from ..kernel.layout import Constraints

if TYPE_CHECKING:
    from .runtime import Runtime

__all__ = ["Find"]

#: The query row's prompt: the tier's own, so an open find bar says what it is.
PROMPT = "find \u276f "

#: The counter with nothing to count.
COUNT_EMPTY = "(0/0)"


class Find:
    """A self-contained search: one query row, its matches, and the overlay.

    ``tui`` is the driver whose focused pane's document is searched and whose
    frame the overlay registers on (at construction -- the ``Toasts``
    lifecycle, so ``detach()`` is the one unmount) and whose
    :meth:`~motui.app.Runtime.reveal` puts the current match on screen.
    ``theme`` (default :data:`~motui.kernel.theme.DEFAULT_THEME`) skins
    the query row and the highlight bands; ``set_theme`` rebuilds the row on
    a new one, carrying an open query's text over.

    :attr:`input` is the query row itself (a host may restyle its prompt or
    read ``input.text``; :attr:`query` is the same text),
    :attr:`matches` the read-only snapshot of the last query's hits -- a
    fresh list of ``(bid, row, start, end)`` tuples, replaced whole on every
    recompute -- and :attr:`index` the cursor over them.  The tier starts
    closed.
    """

    __slots__ = (
        "_detached",
        "_index",
        "_open",
        "_pane_id",
        "_theme",
        "_width",
        "glyphs",
        "input",
        "matches",
        "runtime",
    )

    def __init__(
        self,
        tui: Runtime,
        *,
        theme: Theme | None = None,
        glyphs: Glyphs = GLYPHS,
    ) -> None:
        self._theme = theme if theme is not None else DEFAULT_THEME
        self.runtime = tui
        self.glyphs = glyphs
        self.input = Input(
            prompt=f"find {glyphs.prompt} ", glyphs=glyphs, theme=theme
        )
        self.matches: list[tuple[str, int, int, int]] = []
        self._index = 0
        self._open = False
        self._detached = False
        #: The pane the matches are addresses in (its id) and the width their
        #: rows were rendered at -- the pair a paint checks before it marks
        #: anything, so no stale address ever lands on another document's rows.
        self._pane_id: str | None = None
        self._width = 0
        tui.frame.add_overlay(self, layer="overlay")

    def __repr__(self) -> str:
        return (
            f"Find(open={self._open}, query={self.query!r}, "
            f"matches={len(self.matches)}, index={self.index})"
        )

    @property
    def index(self) -> int:
        """The cursor's match (``0`` while there are none), clamped on assignment."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = min(max(value, 0), len(self.matches) - 1) if self.matches else 0

    # -- the lifecycle ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the tier is showing (and therefore consuming keys)."""
        return self._open

    @property
    def query(self) -> str:
        """The query row's text, the one the matches were addressed for."""
        return self.input.text

    def open(self) -> None:
        """Show a fresh query row: the query and the matches reset.

        An open tier consumes the keys the host hands it and paints its row
        and highlights; the frame is invalidated so the row lands.  Reopening
        a closed tier always starts from the empty query, exactly as
        :meth:`~motui.app.command_palette.CommandPalette.open` does.
        """
        self.input.clear()
        self._recompute()
        self._open = True
        self.runtime.refresh()

    def close(self) -> None:
        """Hide the tier: it consumes nothing and paints nothing.

        The matches stay readable (their addresses are the query's, not the
        visibility's); the next :meth:`open` starts over from an empty query.
        """
        self._open = False
        self.runtime.refresh()

    def detach(self) -> None:
        """Unregister the overlay and go inert (the controller convention).

        The registration is the constructor's, for the frame's life; a
        detached tier stops painting **and** stops consuming keys --
        :meth:`handle` answers ``False`` to everything, whatever the tier's
        open state.  Idempotent: a second detach keeps the flag and touches
        no registry.  This is the unmount, distinct from :meth:`close`,
        which only hides an attached tier.
        """
        self._detached = True
        if self in self.runtime.frame.overlays:
            self.runtime.frame.remove_overlay(self)

    def set_theme(self, theme: Theme) -> None:
        """Rebuild the query row on ``theme``, the rest of the skin following.

        Only the row bakes styles at construction (the bands are read off the
        theme at paint time), so the row is rebuilt and a query in progress
        keeps its text -- the caret ends at the text's end.  The overlay
        registration rides untouched.
        """
        text = self.input.text
        self._theme = theme
        self.input = Input(
            prompt=f"find {self.glyphs.prompt} ", glyphs=self.glyphs, theme=theme
        )
        if text:
            self.input.insert(text)

    # -- routing ---------------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Consume one event while open; see the module docstring.

        ``enter`` and ``down`` step to the next match and ``up`` to the
        previous one -- wrapping around the ends, and doing nothing (but
        still consuming) when there are no matches; ``escape`` closes the
        tier.  Everything else is the query row's: an event it consumes
        re-addresses the matches, resets the cursor to the first, and
        reveals it.  A closed tier consumes nothing; a detached one is
        inert -- whatever the key, the answer is ``False``.
        """
        if self._detached or not self._open:
            return False
        if isinstance(event, KeyEvent):
            if event.key in ("enter", "down"):
                self._step(1)
                return True
            if event.key == "up":
                self._step(-1)
                return True
            if event.key == "escape":
                self.close()
                return True
            consumed = self.input.on_key(event)
        elif isinstance(event, PasteEvent):
            consumed = self.input.on_paste(event)
        else:
            consumed = False
        if consumed:
            self._recompute()
            self._reveal_current()
            return True
        return False

    def _step(self, delta: int) -> None:
        """Move the cursor ``delta`` matches (wrapping) and reveal the landing."""
        if not self.matches:
            return
        self.index = (self.index + delta) % len(self.matches)
        self._reveal_current()

    def _reveal_current(self) -> None:
        """Put the current match on screen through the driver's own reveal.

        The one road to visibility (D10): the tier never touches a viewport.
        ``tui.reveal`` invalidates the frame when the window moved, so a step
        or a query change repaints through it; a caller that wants the host's
        own repaint cue reads :meth:`handle`'s answer.
        """
        if not self.matches:
            return
        bid, row, _, _ = self.matches[self.index]
        self.runtime.reveal(bid, row)

    # -- matching --------------------------------------------------------------

    def _recompute(self) -> None:
        """Re-address the matches for the current query and reset the cursor.

        The document of the pane focused **now** -- the pane ``tui.reveal``
        would scroll -- walked in document order; each match keeps the width
        it was rendered at in :attr:`_width`, and the pane id in
        :attr:`_pane_id`, so the paint can tell a frame its addresses still
        fit from one they do not.  The rows come from each block's own
        cache (:meth:`~motui.kernel.document.Section.rows_view`): a new query over a
        long document reads what the blocks already hold -- the cached lists
        themselves, this walk never mutating them -- instead of
        re-wrapping every block, and a block whose content moved carries a
        moved revision, so a hit is never stale.  The cursor restarts at
        the first match: a new query addresses a new set (D10).
        """
        pane = self.runtime.frame.focused_pane
        self._pane_id = None if pane is None else pane.id
        self._width = self._pane_width()
        self.matches = []
        self._index = 0
        query = self.query
        if not query or pane is None:
            return
        needle = query.lower()
        span = len(needle)
        width = self._width
        for block in pane.document.blocks():
            for row_index, row in enumerate(block.rows_view(Constraints(width=width))):
                text = row.text
                lowered = text.lower()
                found = lowered.find(needle)
                while found >= 0:
                    self.matches.append(
                        (
                            block.id,
                            row_index,
                            visible_width(text[:found]),
                            visible_width(text[: found + span]),
                        )
                    )
                    found = lowered.find(needle, found + span)

    def _pane_width(self) -> int:
        """The width the focused pane's viewport was last laid out at.

        The pane's placement rectangle -- chrome subtracted -- which is the
        width its on-screen rows are in; before the first composition (no
        placement yet) the screen width stands in, the best a frame that was
        never laid out has.
        """
        pane = self.runtime.frame.focused_pane
        if pane is not None:
            region = self.runtime.frame.region(pane.id)
            if region is not None:
                return region.width
        return self.runtime.screen.width

    def _counter(self) -> str:
        """The row's right-hand readout: the current match over the total."""
        if not self.matches:
            return COUNT_EMPTY
        return f"({self.index + 1}/{len(self.matches)})"

    # -- the paint -------------------------------------------------------------

    def paint(self, frame) -> ScreenLayout:
        """The matches over their rows and the query row at the frame's bottom.

        The highlight half is the kernel's range-cut shape
        (:func:`~motui.kernel.selection.highlight`) applied per match:
        each row the matches own is cut at their column boundaries and the
        hit runs merge ``theme.text.selection``, the current match merging
        ``theme.surfaces.hover`` on top.  The marks are only painted when the
        frame's pane and width are the ones the addresses were made in --
        they are read off that pane's own laid-out rows and spliced back
        through :meth:`~motui.kernel.frame.Frame.with_pane_rows`, so a
        match is marked exactly where its glyphs are.  The query row lands on
        the frame's bottom row, on the theme's ``overlays.toast`` band, the
        counter at its right end.  Closed -- or with nothing to mark -- the
        composed rows are only ever gained the query row, or handed back
        exactly as they stand.
        """
        layout = frame.layout
        if layout is None or not self._open:
            return layout
        if self.matches and self._addresses_this_frame(frame):
            marked = self._marked_rows(frame)
            if marked is not None:
                layout = frame.with_pane_rows(self._pane_id, marked)
        return self._with_query_row(layout, frame)

    def _addresses_this_frame(self, frame) -> bool:
        """Whether the matches were addressed in this frame's pane and width."""
        if self._pane_id is None or frame.pane(self._pane_id) is None:
            return False
        region = frame.region(self._pane_id)
        return region is not None and region.width == self._width

    def _marked_rows(self, frame) -> list[Line] | None:
        """The matched pane's rows with every match marked, or ``None``.

        Walks the pane's own laid-out rows and their ownership table (its
        :meth:`~motui.kernel.frame.Frame.pane_layout`), so an address is
        marked only where the row it names actually sits; ``None`` when no
        painted row carries a match (all of them scrolled away).
        """
        layout = frame.pane_layout(self._pane_id)
        if layout is None:
            return None
        by_row: dict[tuple[str, int], list[tuple[int, int, bool]]] = {}
        current = self.matches[self.index]
        for match in self.matches:
            bid, row, start, end = match
            by_row.setdefault((bid, row), []).append((start, end, match == current))
        rows = list(layout.rows)
        marked = False
        for index, owner in enumerate(layout.row_blocks):
            spans = None if owner is None else by_row.get(owner)
            if not spans:
                continue
            row = rows[index]
            pieces = []
            at = 0
            for start, end, is_current in spans:
                style = self._theme.text.selection
                if is_current:
                    style = style.merge(self._theme.surfaces.hover)
                pieces.extend(cut_line(row, at, start).segments)
                pieces.extend(
                    seg.with_style(seg.style.merge(style))
                    for seg in cut_line(row, start, end).segments
                )
                at = end
            pieces.extend(cut_line(row, at, row.width).segments)
            rows[index] = Line(pieces)
            marked = True
        return rows if marked else None

    def _with_query_row(self, layout: ScreenLayout, frame) -> ScreenLayout:
        """Splice the query row over the frame's bottom row, banded.

        The row renders the query at the width left of the counter's cells
        (so the two never overlap), pads the gap, and paints the whole strip
        over the theme's ``toast`` band -- the colored-vs-attribute rule the
        palette's own panel follows.  A frame too short for the row (or one
        that never composed) keeps its rows: the query row is the last of
        them, and a screen with none has none to give.
        """
        rect = frame.rect
        if rect is None or rect.width <= 0 or not layout.rows:
            return layout
        cell = Line.from_text(self._counter(), self._theme.text.faint)
        room = max(1, rect.width - cell.width - 1)  # one gap column before the counter
        query_rows = [row.clip(WrapMode.ELLIPSIS, room) for row in self.input.render(Constraints(width=room))] or [Line()]
        rows = [
            *query_rows[:-1],
            query_rows[-1].fill(room) + Line.from_text(" ") + cell,
        ]
        band = self._theme.overlays.toast
        rows = [
            Line(overlay(band, row.segments)) + Line.filled(rect.width - row.width, band)
            for row in rows
        ]
        target = list(layout.rows)
        top = rect.bottom - len(rows)  # bottom-anchored: the query row takes the last one
        for offset, row in enumerate(rows):
            index = top + offset
            if 0 <= index < len(target):
                target[index] = splice_row(
                    target[index], row, rect.x, rect.width, rect.width
                )
        return replace(layout, rows=target)
