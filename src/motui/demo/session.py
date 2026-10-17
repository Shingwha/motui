"""The demo session: one controller over one :class:`~motui.app.TUI`.

:class:`Session` assembles the shell (the rail split, the two band rows
and their overlay, the scrollbar, the search tier, the copy gesture, the
pointer with its tooltip, the toasts and the dev stats overlay ``c-g``
mounts), owns the session's state (the theme variant, the frame-rate
readout, the current page, and the optional stats overlay and page pane)
and runs the host loop.

**Every activation has an echo.**  A widget's activation lands its pick in
``chosen``; the host reads that value **once**, resets it and reports it --
a toast, plus the current page's optional ``note`` hook.  The read happens
once per round in :meth:`_read_picks`, which scans the page's blocks, so the
host never has to know which door produced the pick.  A pick whose value
names a page opens that page; one naming a theme variant re-skins the shell.

**The host loop's dispatch order**, each tier seeing the event only while
the one before it left it alone::

    stats (counting only) -> scrollbar -> toasts -> the page's modal
    -> find (while open) -> gesture -> pointer -> ring (keyboard)
    -> the host's own keys

The ring never sees the host's own keys: ``q`` quits whatever holds the
focus, and an open query row (the search tier's, or a page's modal)
consumes every printable and its own ``enter``/arrows/``escape`` before the
gestures -- ``c-c`` alone still quits.  A round's own work runs in
:meth:`_after_round` once per round, and the page key the host owns
(``c-t``) is handled after the ring, so a focused field keeps its own keys.
"""

from __future__ import annotations

from motui import (
    Key,
    MouseEvent,
    Pointer,
    Scrollbar,
    SelectionGesture,
    Theme,
    Toasts,
    Tree,
    TUI,
)
from motui.interaction import Find, Stats, Tooltip
from motui.kernel import Pane, Selection, extract
from motui.widgets import ShortcutBar

from .content import THEMES
from .page import Page, PageBody
from .registry import BY_NAME, PAGES
from .shell import HINT_ITEMS, RAIL_RATIOS, Bands, mount_rail, reserve

#: The page animation beat, in seconds (interactive sessions only: the headless
#: replay never sleeps).
PAGE_TICK = 0.1

#: The keys the host owns outright: the ring never sees them, so ``q`` always
#: quits, ``c-f`` always opens the search, ``c-g`` always toggles the dev
#: stats overlay and a lost window focus always reaches the host.
HOST_KEYS = frozenset(
    {"c-n", "c-p", "c-f", "c-g", "tab", "c-o", "q", "c-c", "escape", "focus_out"}
)

#: The theme variants by name: the payload the styles exhibit's picker
#: carries, and the table :meth:`Session._read_picks` resolves one against.
THEME_INDEX = {name: index for index, (name, _) in enumerate(THEMES)}

#: The canned queries ``c-t`` cycles on the data page, in order (the host's
#: own list: the widget's contract is ``Tree.filter(query)``, the host supplies
#: the query -- an ``Input`` row or a key).
TREE_FILTERS: tuple[str | None, ...] = ("kernel", "lines", "widget", None)

#: The page whose picker picks a theme: its picks re-skin the session.
STYLES = BY_NAME.get("styles")


class Session:
    """The demo session, mounted at construction."""

    def __init__(self, tui: TUI) -> None:
        self.tui = tui
        self.theme_index = 0
        #: The registry's table, held so a page can read it (the overview's
        #: index walks it) without importing the registry.
        self.pages = PAGES
        self.page: Page | None = None
        self.body: PageBody | None = None
        #: The right pane the current page owns through its ``enter`` hook.
        self.aside: Pane | None = None
        #: The pointer tier for the current page's ring; retargeted per page.
        self.pointer: Pointer | None = None
        #: The pointer's hint band, mounted beside it and retargeted with it.
        self.tooltip: Tooltip | None = None
        #: The dev stats overlay while ``c-g`` holds it mounted, else ``None``
        #: (the chrome page reads it for its event-count row).
        self.stats: Stats | None = None
        self._cursor_shape: str = "block"  # the last DECSCUSR shape written
        self._tree_filter: int = 0  # the canned query c-t applies next
        self._body_ids: list[str] = []
        self._in_show = False  # show() owns the round: the after-round stays out
        # The split, before anything mounts on it: the first child keeps the
        # driver's document (the rail's home), the second opens a fresh one.
        self.rail_pane, self.main = tui.split("vertical", ratios=RAIL_RATIOS)
        for pane in (self.rail_pane, self.main):
            reserve(pane.document)
        self.hint_bar = ShortcutBar(HINT_ITEMS, theme=self.theme)
        self.bands = Bands(self)
        tui.frame.add_overlay(self.bands)  # the bands sit under the toasts
        self.gesture = SelectionGesture(tui, on_end=self._copy_toast)
        self.scrollbar = Scrollbar(tui, pane=self.main.id)
        self.toasts = Toasts(tui)
        self.rail = mount_rail(tui, (page.name for page in PAGES), theme=self.theme)
        #: The shell's search tier: ``c-f`` opens its query row over whatever
        #: page is on screen (one tier per session -- a page switch closes
        #: it, its addresses belonged to the page that left).
        self.find = Find(tui, theme=self.theme)
        tui.every(PAGE_TICK, self._page_tick)
        if PAGES:
            self.show(PAGES[0])
        tui.paint()

    @property
    def theme(self) -> Theme:
        """The session's current :data:`~motui.demo.content.THEMES` variant."""
        return THEMES[self.theme_index][1]

    def focus_name(self) -> str:
        """The focused leaf's short name for the header band -- its class, lower-cased."""
        ring = None if self.body is None else self.body.focus
        target = None if ring is None else ring.focused
        return "-" if target is None else type(target).__name__.lower()

    # -- pages ------------------------------------------------------------------

    def show(self, page: Page) -> None:
        """Switch to ``page``: leave the old, replace the body, land at the top."""
        self.page = page
        self.tui.set_title(f"motui \u00b7 {page.name}")
        self._tree_filter = 0  # the fresh page's tree opens unfiltered
        self._in_show = True
        try:
            previous = self.body
            if previous is not None and previous.leave is not None:
                previous.leave(self)
            self.close_aside()
            self.find.close()
            self._clear_body()
            self.body = page.build(self)
            for block in self.body.blocks:
                self._body_ids.append(self.main.document.add(block).id)
            if self.body.enter is not None:
                self.body.enter(self)
            self.main.focus()
            self.main.viewport.scroll_up(1 << 20)  # a page opens at its top
            self.rail.select(self._page_index())
            self._retarget_pointer()
            self._sync_cursor_shape()
        finally:
            self._in_show = False
        self.tui.invalidate()

    def _page_index(self) -> int:
        """The current page's index in :data:`~motui.demo.registry.PAGES`."""
        return PAGES.index(self.page) if self.page in PAGES else 0

    def _clear_body(self) -> None:
        """Remove every block the previous body mounted."""
        for block_id in self._body_ids:
            try:
                self.main.document.remove(block_id)
            except KeyError:
                pass  # a page that removed its own block is its own business
        self._body_ids = []

    def _modal(self):
        """The current page's open modal, or ``None`` (the chrome page's palette)."""
        modal = None if self.body is None else self.body.modal
        if modal is not None and getattr(modal, "is_open", False):
            return modal
        return None

    def _retarget_pointer(self) -> None:
        """Point the pointer tier at the new page: its ring, or none."""
        if self.pointer is not None:
            self.pointer.clear()
        ring = None if self.body is None else self.body.focus
        self.pointer = Pointer(self.tui, ring=ring)
        if self.tooltip is not None:
            self.tooltip.detach()  # the old pointer's band retires with it
        self.tooltip = Tooltip(self.tui, self.pointer, theme=self.theme)
        if self.stats is not None:
            self.stats.pointer = self.pointer

    def _follow_rail(self) -> None:
        """Land a click on the rail: switch to the page it selected."""
        index = self.rail.active
        if self.page is None or index == self._page_index():
            return
        if 0 <= index < len(PAGES):
            self.show(PAGES[index])

    # -- the loop ---------------------------------------------------------------

    async def run(self, _tui: TUI) -> None:
        """The host loop: read, route, repaint -- until quit or end of input."""
        tui = self.tui
        running = True
        while running:
            if not tui.interactive:
                # The replay never sleeps, so it outruns the pump's throttle:
                # compose between events, or a scripted click would hit-test
                # against the frame as it stood two commands ago.
                tui.paint()
            event = await tui.read_key()
            if event is None:
                break  # source exhausted (piped replay) or terminal closed
            try:
                running = self._round(event)
            finally:
                self._after_round()
        tui.stop()

    def _round(self, event) -> bool:
        """One event round's dispatch; ``False`` when the round asked to quit."""
        if self.stats is not None and self.stats.handle(event):
            self.tui.invalidate()  # the counters moved: paint the fresh box
        consumed = self.scrollbar.handle(event)
        if not consumed:
            consumed = self.toasts.handle(event)
        modal = self._modal()
        if not consumed and modal is not None:
            consumed = modal.handle(event)
        # The search tier sits between the page's modal and the gestures:
        # while its query row is open it owns the keyboard.
        if not consumed and self.find.is_open:
            consumed = self.find.handle(event)
        if not consumed:
            consumed = self.gesture.handle(event)
        # The pointer watches **beside** the gesture -- never skipped, and it
        # never consumes: its ``True`` is a repaint cue.  A drag's motion
        # touches no hover, so the gesture keeps every report it owns.
        if self.pointer is not None and self.pointer.handle(event):
            self.tui.invalidate()
        if consumed:
            return True
        if not isinstance(event, Key) or isinstance(event, MouseEvent):
            return True  # a report no tier claimed: there is nothing more to route
        ring = None if self.body is None else self.body.focus
        if (
            event.name not in HOST_KEYS
            and not event.char  # no printable ever reaches a field (no editor here)
            and ring is not None
            and ring.handle(event)
        ):
            return True  # the focused widget took it: an arrow moved, enter activated
        name = event.name
        if name == "focus_out":
            # DECSET 1004's blur: the terminal lost the focus, so the leaf
            # under the pointer may have been scrubbed out from under it.
            # The host owns the cleanup, and the next motion re-resolves it.
            if self.pointer is not None:
                self.pointer.clear()
            return True
        if name == "c-c":
            return False  # the one quit gesture the query rows never outrank
        if self.find.is_open or self._modal() is not None:
            # A query row owns the keyboard while it is open: the host's own
            # keys give way, so tab/c-n/c-p/c-o cannot disturb a half-typed
            # query (a printable never reaches here -- the row consumed it).
            return True
        if name == "q":
            return False  # the second quit gesture
        if name == "c-f":
            self.find.open()
        elif name == "c-g":
            self._toggle_stats()
        elif name == "c-n" and len(PAGES):
            self.show(PAGES[(self._page_index() + 1) % len(PAGES)])
        elif name == "c-p" and len(PAGES):
            self.show(PAGES[(self._page_index() - 1) % len(PAGES)])
        elif name == "tab" and ring is not None:
            ring.focus_next()  # the ring binds nothing; tab is the host's
        elif name == "c-o":
            self._cycle_panes()  # c-o is the frame's pane cycle
        elif name == "c-t":
            self._cycle_tree_filter()  # the page's tree, if it has one
        return True

    def _after_round(self) -> None:
        """A round's own work, exactly once, whatever tier dispatched it."""
        if self._in_show:
            return
        self._follow_rail()
        self._read_picks()
        self._sync_cursor_shape()
        self.tui.invalidate()

    def _sync_cursor_shape(self) -> None:
        """Tell the terminal the cursor shape the focused leaf asks for."""
        leaf = None
        modal = self._modal()
        if modal is not None:
            leaf = getattr(modal, "input", None)  # the palette's query row
        if leaf is None and self.find.is_open:
            leaf = self.find.input  # the search tier's query row
        if leaf is None:
            ring = None if self.body is None else self.body.focus
            leaf = None if ring is None else ring.focused
        shape = getattr(leaf, "cursor_shape", "block")
        if shape == self._cursor_shape:
            return
        self._cursor_shape = shape
        self.tui.set_cursor_shape(shape)

    # -- the page gestures the host owns -----------------------------------------

    def _cycle_tree_filter(self) -> bool:
        """``c-t``: apply the next canned query to the page's tree."""
        tree = next(
            (
                block
                for block in (self.body.blocks if self.body is not None else ())
                if isinstance(block, Tree)
            ),
            None,
        )
        if tree is None:
            return False
        query = TREE_FILTERS[self._tree_filter]
        self._tree_filter = (self._tree_filter + 1) % len(TREE_FILTERS)
        tree.filter(query)
        self._report("filter: cleared" if query is None else f"filter: {query!r}")
        return True

    # -- activations and their echo ---------------------------------------------

    def _read_picks(self) -> None:
        """Read every page component's pending pick once, then report it."""
        if self.body is None:
            return
        for component in self.body.blocks:
            chosen = getattr(component, "chosen", None)
            if chosen is None:
                continue
            component.chosen = None  # the host reads a pick exactly once
            value = getattr(chosen, "value", chosen)
            if value is None:
                value = chosen  # a payload-less option: report the option itself
            page = BY_NAME.get(str(value))
            if page is not None:
                self.show(page)  # the pick named a page: open it (no toast)
                continue
            if self.page is STYLES and str(value) in THEME_INDEX:
                self.set_theme(THEME_INDEX[str(value)])  # the pick named a theme: re-skin
            self._report(f"chosen: {value!r}")

    def _report(self, text: str) -> None:
        """Publish one report: the toast, and the page's own echo line."""
        self.toasts.show(text, style=self.theme.toast)
        body = self.body
        if body is not None and body.note is not None:
            body.note(text)

    # -- the theme and the overlays ----------------------------------------------

    def set_theme(self, index: int) -> None:
        """Switch to ``THEMES[index]`` and rebuild everything built from it."""
        self.theme_index = index % len(THEMES)
        theme = self.theme
        self.rail = mount_rail(self.tui, (page.name for page in PAGES),
                               theme=theme, previous=self.rail)
        self.hint_bar = ShortcutBar(HINT_ITEMS, theme=theme)
        self.find.set_theme(theme)
        if self.stats is not None:
            self.stats.set_theme(theme)  # the mounted box follows the re-skin
        if self.page is not None:
            self.show(self.page)  # a re-skin is a rebuild, not a page opening

    def _toggle_stats(self) -> None:
        """``c-g``: mount the dev stats overlay, or unmount it."""
        if self.stats is None:
            self.stats = Stats(self.tui, pointer=self.pointer, theme=self.theme)
        else:
            self.stats.detach()
            self.stats = None
        self.tui.invalidate()

    def _page_tick(self) -> None:
        """The page beat: run the current page's animation, if it has one."""
        body = self.body
        if body is None or body.tick is None:
            return
        body.tick()
        self.tui.invalidate()

    # -- the right pane: the page's own ------------------------------------------

    def open_aside(self) -> Pane:
        """Open the page's own right pane from the frame's split; return it."""
        self.main.focus()
        _, right = self.tui.split("vertical", ratios=(2, 1))
        self.aside = right
        self.tui.invalidate()
        return right

    def close_aside(self) -> None:
        """Close the page's own right pane; the content column takes the width back."""
        if self.aside is None:
            return
        self.aside.close()  # the kernel's un-split
        self.aside = None
        if self.tui.selection_pane is None:
            self.tui.set_selection(None)  # a selection in the closed pane lost its addresses
        self.tui.invalidate()

    # -- focus and copy ---------------------------------------------------------

    def _cycle_panes(self) -> None:
        """``c-o``: focus the next pane in the frame's order (wrapping around)."""
        panes = self.tui.frame.panes
        focused = self.tui.frame.focused_pane
        if focused is None or not panes:
            return
        ids = [pane.id for pane in panes]
        if focused.id in ids:
            panes[(ids.index(focused.id) + 1) % len(panes)].focus()
            if self.pointer is not None:
                self.pointer.clear()
            self.tui.invalidate()

    def _copy_toast(self, tui: TUI, selection: Selection) -> None:
        """The selection ``on_end``: copy the range through OSC 52 and toast the
        answer -- only when the screen answered ``True`` (a pipe has no clipboard)."""
        pane = tui.selection_pane
        document = tui.document if pane is None else pane.document
        region = None if pane is None else tui.frame.region(pane.id)
        width = tui.screen.width if region is None else region.width
        text = extract(document, selection, width=width)
        if tui.screen.copy(text):
            self.toasts.show(
                f"Copied {len(text.splitlines())} lines", style=self.theme.toast
            )
