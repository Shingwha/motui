"""Find: the search tier -- a query row over the document and its matches.

Matches are document addresses with the width they were laid out at, so
another width paints no highlight until re-addressed. Every change
reveals through the workspace."""

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
    from .workspace import Workspace

__all__ = ["Find"]

#: The query row's prompt: the tier's own, so an open find bar says what it is.
PROMPT = "find \u276f "

#: The counter with nothing to count.
COUNT_EMPTY = "(0/0)"


class Find:
    """A self-contained search: one query row, its matches and the overlay.

    The overlay registers at construction; ``detach`` unregisters and goes
    inert. ``matches`` is a fresh list of ``(bid, row, start, end)``."""

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
        "workspace",
    )

    def __init__(
        self,
        workspace: Workspace,
        *,
        theme: Theme | None = None,
        glyphs: Glyphs = GLYPHS,
    ) -> None:
        self._theme = theme if theme is not None else DEFAULT_THEME
        self.workspace = workspace
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
        workspace.frame.add_overlay(self, layer="overlay")

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
        """Show a fresh query row: the query and the matches reset."""
        self.input.clear()
        self._recompute()
        self._open = True
        self.workspace.refresh()

    def close(self) -> None:
        """Hide the tier: it consumes and paints nothing; the matches stay readable."""
        self._open = False
        self.workspace.refresh()

    def detach(self) -> None:
        """Unregister the overlay and go inert; idempotent."""
        self._detached = True
        if self in self.workspace.frame.overlays:
            self.workspace.frame.remove_overlay(self)

    def set_theme(self, theme: Theme) -> None:
        """Rebuild the query row on ``theme``, carrying an open query's text over."""
        text = self.input.text
        self._theme = theme
        self.input = Input(
            prompt=f"find {self.glyphs.prompt} ", glyphs=self.glyphs, theme=theme
        )
        if text:
            self.input.insert(text)

    # -- routing ---------------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Consume one event while open; enter/down/up step matches, escape
        closes, and anything else is the query row's."""
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
        """Put the current match on screen through the workspace's own reveal; the
        tier never touches a viewport."""
        if not self.matches:
            return
        bid, row, _, _ = self.matches[self.index]
        self.workspace.reveal(bid, row)

    # -- matching --------------------------------------------------------------

    def _recompute(self) -> None:
        """Re-address the matches for the current query and reset the cursor; the
        rows come from the blocks' own caches."""
        pane = self.workspace.frame.focused_pane
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
        """The width the focused pane's viewport was last laid out at, else the
        screen width."""
        pane = self.workspace.frame.focused_pane
        if pane is not None:
            region = self.workspace.frame.region(pane.id)
            if region is not None:
                return region.width
        return self.workspace.screen.width

    def _counter(self) -> str:
        """The row's right-hand readout: the current match over the total."""
        if not self.matches:
            return COUNT_EMPTY
        return f"({self.index + 1}/{len(self.matches)})"

    # -- the paint -------------------------------------------------------------

    def paint(self, frame) -> ScreenLayout:
        """The matches over their rows and the query row at the frame's bottom; a
        closed tier returns the layout as it stands."""
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
        """The pane's rows with every match marked, or ``None`` when none is
        painted; the current match merges hover on top."""
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
        """Splice the query row over the frame's bottom row, banded and with the
        counter at its right end."""
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
