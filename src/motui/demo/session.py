"""The demo session: one controller over one :class:`~motui.app.TUI`.

:class:`Session` assembles the shell -- the rail split, the band overlay, the
scrollbar, the search tier, the copy gesture, the pointer with its tooltip,
the toasts and the ``c-g`` stats box -- owns the state (the theme variant,
the current page, the optional page pane) and runs the host loop.

**Every activation has an echo.**  A widget lands its pick in ``chosen``; the
host reads it once per round -- :meth:`_read_picks` gives the page's own
resolver (``Exhibit.build`` hangs it on the body) the report door -- and
answers with a toast plus the page's ``note``.  A pick carrying an ``Action``
runs it with the host, so opening a page or re-skinning the shell is the
page's data, never the host's.  The host's own gestures are generic too:
``space`` flips the focused leaf's ``toggle()``, and ``c-t`` hands the
exhibit whose slot the page seeded the next of its canned queries.

**The dispatch order**, each tier seeing the event only while the one before
it left it alone::

    stats (counting only) -> scrollbar -> toasts -> the page's modal
    -> find (while open) -> gesture -> pointer -> ring (keyboard)
    -> the host's own keys

The ring never sees :data:`HOST_KEYS`; an open query row -- the search
tier's or a page's modal -- owns every printable and its own ``enter``/
arrows/``escape`` first, and ``c-c`` alone quits ahead of everything.  A page
switch closes the search: its addresses belonged to the page that left.
"""

from __future__ import annotations

from motui import (
    KeyEvent,
    MouseEvent,
    Pointer,
    Scrollbar,
    SelectionGesture,
    Theme,
    Toasts,
    TUI,
)
from motui.interaction import Find, Stats, Tooltip
from motui.kernel import FocusEvent, Pane, Selection, extract
from motui.widgets import ShortcutBar

from .assets import THEMES
from .kit import Pick
from .page import Page, PageBody
from .registry import PAGES
from .shell import HINT_ITEMS, RAIL_RATIOS, Bands, mount_rail, reserve

#: The page animation beat, in seconds (interactive sessions only: the headless
#: replay never sleeps).
PAGE_TICK = 0.1

#: The keys the host owns outright -- the ring never sees them, so ``q`` quits,
#: ``space``/``c-t`` always run the page's own gestures, and a lost window
#: focus (a :class:`~motui.kernel.events.FocusEvent`) always reaches the host.
HOST_KEYS = frozenset({
    "c-n", "c-p", "c-f", "c-g", "space", "tab", "c-o", "q", "c-c", "escape",
})


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
        #: What a page owns through its hooks: the right pane, the pointer tier
        #: for its ring, that pointer's tooltip band, and the stats overlay
        #: while ``c-g`` holds it mounted (the shell page reads its counts).
        self.aside: Pane | None = None
        self.pointer: Pointer | None = None
        self.tooltip: Tooltip | None = None
        self.stats: Stats | None = None
        self._cursor_shape: str = "block"  # the last DECSCUSR shape written
        self._filter: int = 0  # the next canned query c-t applies (per page)
        self._body_ids: list[str] = []
        self._in_show = False  # show() owns the round: the after-round stays out
        # The split, before anything mounts on it: the first child keeps the
        # driver's document (the rail's home), the second opens a fresh one.
        self.rail_pane, self.main = tui.split("vertical", ratios=RAIL_RATIOS)
        for pane in (self.rail_pane, self.main):
            reserve(pane.document)
        self.hint_bar = ShortcutBar(self._hint_items(), theme=self.theme)
        self.bands = Bands(self)
        tui.frame.add_overlay(self.bands)  # the bands sit under the toasts
        self.gesture = SelectionGesture(tui, on_end=self._copy_toast)
        self.scrollbar = Scrollbar(tui, pane=self.main.id)
        self.toasts = Toasts(tui)
        self.rail = mount_rail(tui, (page.name for page in PAGES), theme=self.theme)
        self.find = Find(tui, theme=self.theme)  # c-f's query row over the page
        tui.every(PAGE_TICK, self._page_tick)
        if PAGES:
            self.show(PAGES[0])
        tui.paint()

    @property
    def theme(self) -> Theme:
        """The session's current :data:`~motui.demo.assets.THEMES` variant."""
        return THEMES[self.theme_index][1]

    def focus_name(self) -> str:
        """The focused leaf's short name for the header band -- its class, lower-cased."""
        ring = None if self.body is None else self.body.focus
        target = None if ring is None else ring.focused
        return "-" if target is None else type(target).__name__.lower()

    def _hint_items(self) -> list[tuple[str, str]]:
        """The band's rows: the current page's own keys, then the host's globals.

        The page's hints are its ``Page.hints`` (the page's own keys, the
        ones that fit a one-row band); ``shell.HINT_ITEMS`` is the host's own
        -- the keys every page answers (``c-n``/``c-p``, ``tab``, ``c-f``,
        ``q``), so the band follows the page and the session's keys never
        fall off it.
        """
        page = () if self.page is None else self.page.hints
        return [*page, *HINT_ITEMS]

    # -- pages ------------------------------------------------------------------

    def show(self, page: Page) -> None:
        """Switch to ``page``: leave the old, replace the body, land at the top."""
        self.page = page
        self.tui.set_title(f"motui \u00b7 {page.name}")
        self.hint_bar = ShortcutBar(self._hint_items(), theme=self.theme)
        self._filter = 0  # a fresh page's filterable view opens unfiltered
        self._in_show = True
        try:
            previous = self.body
            if previous is not None and previous.leave is not None:
                previous.leave(self)
            self.close_aside()
            self.find.close()  # the search addressed the page that is leaving
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
        """The current page's open modal, or ``None``."""
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
            event = await tui.read_event()
            if event is None:
                break  # source exhausted (piped replay) or terminal closed
            try:
                running = self._round(event)
            finally:
                self._after_round()
        tui.stop()

    def _round(self, event) -> bool:
        """One event round's dispatch; ``False`` when the round asked to quit."""
        if isinstance(event, KeyEvent) and event.key == "c-c":
            # The one quit gesture no tier outranks: a modal swallows every key
            # nobody took, so a host chord that must survive an open panel is
            # routed before every tier.
            return False
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
        # The pointer watches **beside** the gesture -- never skipped, never
        # consuming: its ``True`` is a repaint cue.
        if self.pointer is not None and self.pointer.handle(event):
            self.tui.invalidate()
        if consumed:
            return True
        if isinstance(event, FocusEvent):
            # DECSET 1004's blur: the leaf under the pointer may have been
            # scrubbed out from under it; the next motion re-resolves it.
            if not event.focused and self.pointer is not None:
                self.pointer.clear()
            return True
        if not isinstance(event, KeyEvent):
            return True  # a report no tier claimed: there is nothing more to route
        ring = None if self.body is None else self.body.focus
        if (
            event.key not in HOST_KEYS
            and not event.char  # no printable ever reaches a field (no editor here)
            and ring is not None
            and ring.handle(event)
        ):
            return True  # the focused widget took it: an arrow moved, enter activated
        name = event.key
        if self.find.is_open or self._modal() is not None:
            # A query row owns the keyboard while it is open: the host's keys
            # give way, so tab/c-n/c-p/c-o cannot disturb a half-typed query.
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
        elif name == "space":
            self._mark_cursor_row()
        elif name == "tab" and ring is not None:
            ring.focus_next()  # the ring binds nothing; tab is the host's
        elif name == "c-o":
            self._cycle_panes()  # c-o is the frame's pane cycle
        elif name == "c-t":
            self._cycle_tree_filter()  # the page's filterable exhibit, if it has one
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
            leaf = getattr(modal, "input", None)  # an open panel's query row
        if leaf is None and self.find.is_open:
            leaf = self.find.input
        if leaf is None:
            ring = None if self.body is None else self.body.focus
            leaf = None if ring is None else ring.focused
        shape = getattr(leaf, "cursor_shape", "block")
        if shape != self._cursor_shape:
            self._cursor_shape = shape
            self.tui.set_cursor_shape(shape)

    # -- the page gestures the host owns -----------------------------------------

    def _mark_cursor_row(self) -> bool:
        """``space``: flip the focused view's cursor-row mark, where it has one.

        The marks belong to the view; no widget binds a key to them, so the
        host routes the focused ring target's own ``toggle()``.
        """
        ring = None if self.body is None else self.body.focus
        target = None if ring is None else ring.focused
        toggle = getattr(target, "toggle", None)
        if toggle is None:
            return False
        toggle()
        return True

    def _cycle_tree_filter(self) -> bool:
        """``c-t``: hand the page's filterable exhibit the next query it offers.

        The view's contract is its own ``filter(query)``; the page registers
        the canned queries as its slot's ``meta`` and the kit forwards the
        lookup, so the host reads no page's name and no widget's class.  The
        focused leaf answers first when it is such a view, the page's own
        exhibit when the ring stands elsewhere (a table beside a tree); a page
        that seeds none leaves the key to nobody.
        """
        body = self.body
        meta = None if body is None else getattr(body, "slot_meta", None)
        if meta is None:
            return False
        ring = body.focus
        focused = None if ring is None else ring.focused
        for target in (focused, *body.blocks):
            if target is None or getattr(target, "filter", None) is None:
                continue
            queries = meta(target)
            if not queries:
                continue
            query = queries[self._filter % len(queries)]
            self._filter = (self._filter + 1) % len(queries)
            target.filter(query)
            line = "filter: cleared" if query is None else f"filter: {query!r}"
            self._toast(line)  # the host's own line, verbatim
            self._note(Pick(target, None, line))  # ... which the page's echo answers
            return True
        return False

    # -- activations and their echo ---------------------------------------------

    def _read_picks(self) -> None:
        """Read every page component's pending pick once, then report it.

        A kit page's body resolves its own picks (``Exhibit.build`` hangs
        ``resolve_picks`` on it): it runs the pick's ``Action`` with this
        session and reports the rest through the host's door.  A body
        without one is scanned instead and each pick reports as the
        pre-formatted line its string-shaped ``note`` reads -- no page
        builds one any more, and the fallback stays for a host's own body.
        """
        if self.body is None:
            return
        resolve = getattr(self.body, "resolve_picks", None)
        if resolve is not None:
            resolve(self._report)
            return
        for component in self.body.blocks:
            chosen = getattr(component, "chosen", None)
            if chosen is None:
                continue
            component.chosen = None  # the host reads a pick exactly once
            value = getattr(chosen, "value", chosen)
            if value is None:
                value = chosen  # a payload-less option: report the option itself
            self._report(f"chosen: {value!r}")

    def _report(self, report: Pick | str) -> None:
        """Publish one report: the toast for it, then the page's own ``note``.

        A kit page hands a structured :class:`~motui.demo.kit.Pick`; a body
        without a resolver hands its pre-formatted ``"chosen: \u2026"`` line
        instead.  The host's own lines (``c-t``) take :meth:`_toast` and
        :meth:`_note` directly, so they are never reprinted as a second
        ``chosen:``.
        """
        self._toast(report if isinstance(report, str) else f"chosen: {report.value!r}")
        self._note(report)

    def _toast(self, text: str) -> None:
        """Raise one line as a toast in the theme's band."""
        self.toasts.show(text, style=self.theme.toast)

    def _note(self, report: Pick | str) -> None:
        """Hand one report to the current page's own ``note``, if it has one."""
        body = self.body
        if body is not None and body.note is not None:
            body.note(report)

    # -- the theme and the overlays ----------------------------------------------

    def set_theme(self, index: int) -> None:
        """Switch to ``THEMES[index]`` and rebuild everything built from it."""
        self.theme_index = index % len(THEMES)
        theme = self.theme
        self.rail = mount_rail(self.tui, (page.name for page in PAGES),
                               theme=theme, previous=self.rail)
        self.hint_bar = ShortcutBar(self._hint_items(), theme=theme)  # the page's stay
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
