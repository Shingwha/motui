"""shell: the gallery's pinned chrome and the modal palette overlay.

Four controllers, one job each:

:class:`Header` is the pinned top of the gallery -- four one-row blocks in
render order: the title (``mocode-tui gallery \u00b7 <page>``), the ``Tabs``
strip whose labels are the pages, the hint line (the current page's ``hint``
plus the shell's own keys) and the rule.  The strip is ``fit`` to its row,
so the sum of the ``nav`` labels is what must stay inside the pane's content
width; a click on a label is opened by the host through the strip's own
``click``.  Both the strip and the rule bake their styles at construction,
so a theme switch rebuilds all four blocks (:meth:`Header.set_theme`); the
hint line is re-ellipsized to the pane's content width every
:meth:`Header.refresh` -- a pinned row is one row by contract, on the split
screen too.

:class:`Shortcuts` is the footer's key-hint row, pinned bottom **above**
the status row: one :class:`~mocode_tui.widgets.ShortcutBar` listing the
shell's own keys (``c-n``/``c-p``, ``/``, ``c-f``, ``c-g``, ``tab``,
``c-c``), rendered in the theme's accent/dim bands and truncated by ``fit``
on a narrow screen.

:class:`Status` is the pinned bottom of the gallery: one ``StatusLine``,
left ``<page> \u00b7 focus=<target>``, right the frame-rate readout.  It is
one row whatever the two sides say.

:class:`PaletteOverlay` is the gallery's modal text input -- opened by ``/``,
closed the moment a command is taken or escape pressed.  It is an **overlay**
in the frame's own sense (:class:`~mocode_tui.chrome.Toasts` is the
reference): a pure ``paint(frame) -> layout`` registered on the frame only
while open, drawing the ``Palette``'s rows bottom-anchored over the composed
rows -- above the pinned footer rows, over the theme's ``toast`` band -- and
unregistered on close, so a closed palette contributes exactly nothing: no
rows, no registry entry, no keys.  The palette brings its own query row
(``widgets.Palette``); the gallery mounts no editor of its own, and the other
self-owned query row is the search tier's (``mocode_tui.search.Find``), whose
host loop lives in :mod:`gallery.session`.
"""

from __future__ import annotations

from dataclasses import replace

from mocode_tui import (
    DEFAULT_THEME,
    Divider,
    Option,
    Palette,
    ShortcutBar,
    StatusLine,
    Tabs,
    Text,
    TUI,
    Theme,
)
from mocode_tui.core.frame import splice_row
from mocode_tui.core.lines import Line, overlay
from mocode_tui.core.style import Style
from mocode_tui.core.text import ellipsize_tail
from mocode_tui.core.viewport import ScreenLayout

__all__ = ["GALLERY_TITLE", "Header", "PaletteOverlay", "Shortcuts", "Status"]

#: The brand the header names, ahead of the current page.
GALLERY_TITLE = "mocode-tui gallery"

#: The scrollbar the gallery mounts budgets one column of the primary pane;
#: a hint line is ellipsized against the leftover content width.
SCROLLBAR_COLUMNS = 1

#: The pinned footer rows the palette overlay must not cover: the shortcut
#: bar and the status line.
STATUS_ROWS = 2

#: The narrowest content width a hint line is ellipsized against (a screen
#: that narrow has larger problems than a truncated hint).
MIN_HINT_WIDTH = 20

#: The shell's own keys, in the order the hint line names them: what is left
#: once the page's own hint (when it has one) has been named.
SHELL_KEYS = (
    "click a tab \u00b7 c-n / c-p pages \u00b7 / palette \u00b7 c-f find "
    "\u00b7 tab focus \u00b7 c-c quits"
)

#: The footer's own key hints -- the same keys the hint line's tail names,
#: as ``(key, label)`` pairs for the :class:`ShortcutBar`.
SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("c-n / c-p", "pages"),
    ("/", "palette"),
    ("c-f", "find"),
    ("c-g", "stats"),
    ("tab", "focus"),
    ("c-c", "quit"),
)


class Header:
    """The pinned top: title, tab strip, hint line, rule -- four blocks.

    ``pages`` is the registry's page table (the strip carries one ``nav``
    label per page); ``theme`` the skin the four blocks bake at
    construction.  Constructing it mounts the blocks pinned top, in row
    order -- the only four pinned-top blocks the gallery ever mounts -- and
    :meth:`set_theme` re-mounts them on a new skin.
    """

    def __init__(
        self, tui: TUI, pages=(), *, theme: Theme | None = None
    ) -> None:
        self.tui = tui
        self._pages = tuple(pages)
        self._theme = theme if theme is not None else DEFAULT_THEME
        self._ids: tuple[str, ...] = ()
        self._mount()

    def _mount(self) -> None:
        """(Re)build the four blocks and mount them pinned top, in row order."""
        for block_id in self._ids:
            self.tui.remove(block_id)
        self.title = Text("", style=self._theme.accent)
        self.nav = Tabs([page.nav for page in self._pages], theme=self._theme)
        self.hint = Text("", style=self._theme.dim)
        self.rule = Divider(theme=self._theme)
        self._ids = (
            self.tui.add(self.title, id="header-title", pin="top").id,
            self.tui.add(self.nav, id="header-tabs", pin="top").id,
            self.tui.add(self.hint, id="header-hint", pin="top").id,
            self.tui.add(self.rule, id="header-rule", pin="top").id,
        )

    def set_theme(self, theme: Theme) -> None:
        """Re-mount the header on ``theme`` (``Tabs`` bakes its styles once)."""
        self._theme = theme
        self._mount()

    def refresh(self, page, index: int, body=None) -> None:
        """Paint the header for ``page``: title, marker, hint.

        ``index`` is the page's place in the registry (the strip's marker),
        and ``body`` the built page whose ``hint`` the line names -- with
        the shell's own keys after it, and the whole line ellipsized to the
        primary pane's current content width, so the hint is one row even
        while a page owns the right pane.
        """
        self.title.text = f"{GALLERY_TITLE} \u00b7 {page.name}"
        self.nav.select(index)
        hint = f"\u2191\u2193/enter: {body.hint} \u00b7 {SHELL_KEYS}" if (
            body is not None and body.focus is not None and body.hint
        ) else SHELL_KEYS
        self.hint.text = ellipsize_tail(hint, self.content_width)

    @property
    def content_width(self) -> int:
        """The primary pane's current content width, best effort.

        The pane's placement minus the scrollbar's budget once the frame has
        been laid out; the screen width minus the same budget before the
        first composition (and on a screen too narrow to matter).
        """
        region = self.tui.frame.region("primary")
        width = region.width if region is not None else self.tui.screen.width
        return max(width - SCROLLBAR_COLUMNS, MIN_HINT_WIDTH)


class Shortcuts:
    """The pinned footer's key-hint row: one ``ShortcutBar``.

    Mounted before the status row, so the bottom region renders it **above**
    the status line (pinned blocks paint in document order).  One block,
    always one row; :meth:`set_theme` re-mounts it on a new skin
    (``ShortcutBar`` resolves its styles at construction).
    """

    __slots__ = ("_id", "_theme", "bar", "tui")

    def __init__(self, tui: TUI, *, theme: Theme | None = None) -> None:
        self.tui = tui
        self._theme = theme if theme is not None else DEFAULT_THEME
        self._id: str = ""
        self._mount()

    def _mount(self) -> None:
        if self._id:
            self.tui.remove(self._id)
        self.bar = ShortcutBar(SHORTCUTS, theme=self._theme)
        self._id = self.tui.add(self.bar, id="shortcuts", pin="bottom").id

    def set_theme(self, theme: Theme) -> None:
        """Re-mount the bar on ``theme``."""
        self._theme = theme
        self._mount()


class Status:
    """The pinned bottom: one ``StatusLine``, under the shortcut bar.

    Left ``<page> \u00b7 focus=<target>``, right the frame-rate readout, so
    a page switch and the focused widget are visible before anything is
    touched.  One block, always one row; :meth:`set_theme` re-mounts it on a
    new skin (``StatusLine`` resolves its styles at construction).
    """

    def __init__(self, tui: TUI, *, theme: Theme | None = None) -> None:
        self.tui = tui
        self._theme = theme if theme is not None else DEFAULT_THEME
        self._id: str = ""
        self._mount()

    def _mount(self) -> None:
        if self._id:
            self.tui.remove(self._id)
        self.line = StatusLine(left=(), right=(), theme=self._theme)
        self._id = self.tui.add(self.line, id="status", pin="bottom").id

    def set_theme(self, theme: Theme) -> None:
        """Re-mount the status row on ``theme``."""
        self._theme = theme
        self._mount()

    def refresh(self, name: str, focus: str, *, fps: float, fps_on: bool) -> None:
        """The two sides: the page and its focus left, the readout right."""
        self.line.left = (f"{name} \u00b7 focus={focus}",)
        self.line.right = (f"{fps:.1f} fps",) if fps_on else ("fps off",)


class PaletteOverlay:
    """The modal ``Palette``: bottom-anchored over the composed frame.

    The controller half is one registration (the frame's overlay registry,
    only while open) and one ``handle`` (the palette's own consume-one-event
    contract); the painting half is ``paint``, a pure function of the
    composed rows and the open palette.  ``open`` shows the palette with an
    empty query and registers the overlay; ``close`` hides it and
    unregisters -- object identity is the registry's claim, so both are
    guarded by membership and both are idempotent.  ``band_style`` is the
    band painted under the rows (the theme's ``toast`` by default): the
    panel reads as a band over the page, one row of the page context left
    untouched above the status row, exactly like a toast does.
    """

    def __init__(
        self,
        tui: TUI,
        options,
        *,
        theme: Theme | None = None,
        band_style: Style | None = None,
        max_rows: int = 8,
    ) -> None:
        self.tui = tui
        self._options = list(options)
        self._theme = theme if theme is not None else DEFAULT_THEME
        self._band_style = band_style
        self.palette = Palette(self._options, theme=theme, max_rows=max_rows)

    # -- the lifecycle ------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the palette is showing (and the overlay registered)."""
        return self.palette.is_open

    def open(self) -> None:
        """Show a fresh palette and register the overlay; idempotent."""
        self.palette.open()
        if self not in self.tui.frame.overlays:
            self.tui.frame.add_overlay(self)
        self.tui.invalidate()

    def close(self) -> None:
        """Hide the palette and unregister the overlay; idempotent."""
        self.palette.close()
        self._unregister()
        self.tui.invalidate()

    def set_theme(self, theme: Theme) -> None:
        """Rebuild the palette on ``theme`` (its row widgets bake styles once)."""
        self._theme = theme
        self.palette = Palette(self._options, theme=theme, max_rows=self.palette.list.max_rows)

    def handle(self, event) -> bool:
        """Route ``event`` through the palette; keep the registration in sync.

        The palette consumes its own dismiss keys (``enter`` and
        ``escape``), so the moment it reports closed the overlay is
        unregistered -- the same rule :meth:`close` runs, whichever road
        closed it.  A palette that is still open stays registered.
        """
        consumed = self.palette.handle(event)
        if not self.palette.is_open:
            self._unregister()
        return consumed

    def _unregister(self) -> None:
        """Drop the overlay registry entry, if it is there (idempotent)."""
        if self in self.tui.frame.overlays:
            self.tui.frame.remove_overlay(self)

    # -- the paint ----------------------------------------------------------

    def paint(self, frame) -> ScreenLayout:
        """The palette's rows over the composed frame's bottom, banded.

        The palette renders at the frame's full width; the rows sit just
        above the pinned status row (``STATUS_ROWS``), painted over the
        theme's band, and a frame too short for all of them clips from the
        top.  Closed -- and therefore unregistered -- the very layout comes
        back unchanged.
        """
        layout = frame.layout
        rect = frame.rect
        if not self.palette.is_open or rect is None or rect.width <= 0:
            return layout
        rows = [row.fit(rect.width) for row in self.palette.render(rect.width)]
        if not rows:
            return layout
        band = self._band_style if self._band_style is not None else self._theme.toast
        room = max(rect.height - STATUS_ROWS, 1)
        rows = rows[-room:]  # a frame this short shows the query row and below
        top = rect.bottom - STATUS_ROWS - len(rows)
        if top < rect.y:
            rows = rows[rect.y - top:]
            top = rect.y
        target = list(layout.rows)
        for offset, row in enumerate(rows):
            index = top + offset
            if not 0 <= index < len(target):
                continue
            target[index] = splice_row(
                target[index],
                _band_row(row, rect.width, band),
                rect.x,
                rect.width,
                rect.width,
            )
        return replace(layout, rows=target)


def _band_row(row: Line, width: int, band: Style) -> Line:
    """One palette row: its content over the band, filled out to ``width``.

    The colored-vs-attribute rule of the toast band verbatim
    (:func:`~mocode_tui.core.lines.overlay`): the band paints underneath, a
    segment carrying a color of its own keeps it and an attribute-only one
    shows the band through -- then the row is filled to ``width`` so a blank
    content row reads as a solid band row.
    """
    content = Line(overlay(band, row.segments))
    return content + Line.filled(width - row.width, band)
