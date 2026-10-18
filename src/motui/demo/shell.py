"""The demo's shell: the left rail, the band rows, and the overlay that paints them.

The frame is a real two-pane split: ``tui.split("vertical", ratios=(1, 4))``
divides it into the **rail** (left: one vertical ``NavList`` over the
page names) and the **content** pane (right: the current page's blocks).
The rail is a pane of its own -- its own viewport, its own focus, the
frame's own hit-testing -- and the first child of a split keeps the
driver's document, so the rail lives in the primary document while the
page blocks live in the fresh one the content pane opened.

:func:`reserve` mounts one blank pinned block at each end of a
document -- the rows the shell's bands paint over -- and :class:`Bands`
splices the header row (``motui`` and the page left, the focus right) into
the frame's first row and the key hints into its last, both full width.
"""

from __future__ import annotations

from dataclasses import replace

from motui import NavList, Text, TUI, Theme
from motui.kernel.frame import splice_row
from motui.kernel.lines import Line

__all__ = ["Bands", "HINT_ITEMS", "RAIL_RATIOS", "SHELL_TITLE", "header_row", "mount_rail", "reserve"]

#: The name the header band prefixes to the page it is showing.
SHELL_TITLE = "motui"

#: The rail | content weights: the strip takes a fifth of the frame, and the
#: reference's own ``ratios`` (``ref/demo.md`` §2).
RAIL_RATIOS = (1, 4)

#: The host's own keys, as ``(key, label)`` pairs the session appends to the
#: current page's ``Page.hints`` on every ``show`` -- the keys every page
#: answers (``c-n``/``c-p``, ``tab``, ``c-f``, ``q``).  ``c-o`` and ``c-g``
#: are not here: they are the shell page's own exhibits, so its hints carry
#: them beside the panes and the stats box they drive.
HINT_ITEMS: tuple[tuple[str, str], ...] = (
    ("c-n / c-p", "pages"),
    ("tab", "focus"),
    ("c-f", "find"),
    ("q", "quit"),
)


def reserve(document) -> None:
    """Reserve the shell's two band rows in ``document``: blank pinned rows."""
    document.add(Text(""), pin="top")
    document.add(Text(""), pin="bottom")


def header_row(page: str, focus: str, *, theme: Theme, width: int) -> Line:
    """The header band's one row: ``motui`` and the page left, the readouts right."""
    status = f"focus: {focus}"
    left = Line.from_text(f" {SHELL_TITLE} \u00b7 {page} ", style=theme.accent)
    right = Line.from_text(f"{status} ", style=theme.dim)
    gap = width - left.width - right.width
    if gap >= 0:
        return left + Line.filled(gap) + right
    return left.fit(width)


def mount_rail(tui: TUI, names, *, theme: Theme, previous: NavList | None = None) -> NavList:
    """Mount the rail's vertical list in the primary document; return it.

    The list is one block, so the rail's own pane scrolls it when a short
    terminal cannot hold every label.  A re-mount -- the theme switch --
    removes the previous list first.  The session reads ``list.active``
    once per round (a click on a label is what moves it) and calls
    ``list.select(index)`` when it opens a page, and the component's own
    row-resolution is what makes the rail clickable without one cell of
    hand-rolled geometry.
    """
    if previous is not None:
        tui.remove(tui.get("rail").id)
    strip = NavList([str(name) for name in names], theme=theme)
    tui.add(strip, id="rail")
    return strip


class Bands:
    """The header and hint rows, painted over the composed frame."""

    __slots__ = ("_session",)

    def __init__(self, session) -> None:
        self._session = session

    def paint(self, frame):
        """Splice the two band rows into the composed layout."""
        layout = frame.layout
        rect = frame.rect
        if layout is None or rect is None or not layout.rows or rect.width <= 0:
            return layout
        session = self._session
        rows = list(layout.rows)
        header = header_row(
            "-" if session.page is None else session.page.name,
            session.focus_name(),
            theme=session.theme,
            width=rect.width,
        )
        rows[0] = splice_row(rows[0], header, rect.x, rect.width, rect.width)
        if len(rows) > 1:
            hint = session.hint_bar.render(rect.width)[0]
            rows[-1] = splice_row(rows[-1], hint, rect.x, rect.width, rect.width)
        return replace(layout, rows=rows)
