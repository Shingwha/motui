"""The gallery session: one controller over one :class:`~mocode_tui.app.TUI`.

:class:`Gallery` assembles the shell (the pinned header, the pinned status
row, the palette overlay, the scrollbar, the copy gesture, the pointer, the
toasts), owns the session's state (the theme variant, the frame-rate
readout, the current page, the optional right pane) and runs the host loop.

**Driving a page.**  The page's :class:`~mocode_tui.focus.FocusRing` is the
keyboard door -- ``tab`` cycles the focus, the arrows move the focused
widget and ``enter`` activates it -- and the ring's click policy is behind
the mounted :class:`~mocode_tui.pointer.Pointer`, which also owns the hover:
a stationary click dispatches the cell, focuses the component it landed on
and activates it on the second click, and a motion flips the ``hover`` flag
of the leaf under the pointer.  There is **no editor anywhere**: the only
text input in the gallery is the palette's own query row while the ``/``
panel is open.

**Every activation has an echo.**  A widget's activation lands its pick in
``chosen``; the host reads that value **once** and resets it, then reports
it -- a toast, plus the current page's optional
:attr:`~gallery.page.PageBody.note` hook, which lets the page echo the last
pick in a line of its own.  Both activation paths run through that one
report: the keyboard's ``enter`` and the second click of the click policy.
The read happens once per event **round**, in :meth:`_read_picks`: it scans
the ring's targets for a pending ``chosen``, so the host never has to know
which door produced the pick.  A pick whose value names a page opens that
page (the overview's index walks the gallery that way); a pick that names a
theme variant, on the styles page, re-skins the shell through
:meth:`set_theme`.

**Moving between pages.**  Three roads lead to a page, and all of them run
through :meth:`show`: a click on the header's tab strip (the host follows
``Tabs.active`` once per round), the ``c-n``/``c-p`` keys for the
next/previous page (the ends wrap), and the ``/`` palette by name.  ``show``
moves the strip's marker and repaints the title and the status row, so the
three never disagree with the page on screen.

**A page may own the right pane.**  A body with an
:attr:`~gallery.page.PageBody.enter` hook is a layout, not a list: ``show``
mounts the page's blocks, calls ``enter(gallery)`` -- the page opens its
pane through :meth:`open_aside` and fills it -- and calls ``leave(gallery)``
on the way out.  The slot is one pane deep: the ``/split`` preview and a
page's pane are the same slot, so ``/split`` on a page that owns a pane
toasts instead of opening a third.

**The host loop's dispatch order**, one line per tier, each seeing the event
only while the one before it left it alone::

    scrollbar -> toasts -> palette (while open) -> gesture -> pointer
    -> ring (keyboard) -> the host's own keys

The ring never sees the host's own keys (``c-n``/``c-p``/``tab``/``c-o``/
``/``/``q``/``c-c``/``escape``) and no printable character ever reaches it:
``q`` quits and ``/`` opens the panel whatever holds the focus, and a field
cannot steal a keystroke typed at the shell.  A round's own work runs in
:meth:`_after_round` -- the tab-strip follow, the pick read, the status
refresh -- exactly once, whatever tier dispatched the event.

The command list is the registry's pages plus the four actions below -- the
palette's rows and the dispatch table both derive from it.
"""

from __future__ import annotations

from mocode_tui import (
    Column,
    DIM,
    EveryHandle,
    Key,
    MouseEvent,
    Pane,
    Pointer,
    ProgressBar,
    Scrollbar,
    Selection,
    SelectionGesture,
    Spacer,
    Spinner,
    Text,
    Theme,
    Toasts,
    TUI,
    extract,
)

from .content import THEMES
from .page import Page, PageBody
from .registry import BY_NAME, Command, PAGES, page_commands, palette_options
from .shell import Header, PaletteOverlay, Status

# Pacing in seconds (interactive sessions only -- the headless replay yields).
PAGE_TICK = 0.1     # the page animation beat (the stream exhibit, the live bars)
FPS_INTERVAL = 0.5  # the frame-rate sampling period

#: The keys the host owns outright: the ring never sees them, so ``q`` always
#: quits and ``/`` always opens the palette, whatever holds the focus.
HOST_KEYS = frozenset({"c-n", "c-p", "tab", "c-o", "/", "q", "c-c", "escape"})

#: The theme variants by name: the payload the styles exhibit's picker
#: carries, and the table :meth:`Gallery._read_picks` resolves one against.
THEME_INDEX = {name: index for index, (name, _) in enumerate(THEMES)}

#: The page whose picker picks a theme: its picks re-skin the session.
STYLES = BY_NAME.get("styles")


def _focus_name(target) -> str:
    """The short name of a focus target: its class, lower-cased.

    One spelling for the status row's ``focus=<name>`` -- a page with no
    ring, or a ring with nothing focused, reads ``-``.
    """
    return "-" if target is None else type(target).__name__.lower()


class Gallery:
    """The gallery session, mounted at construction.

    ``Gallery(tui)`` builds the whole shell before it returns: the header is
    pinned top, the status row pinned bottom, the scrollbar, the toast
    overlay, the selection gesture and the palette ride the frame, and the
    gallery opens on the first page in the registry.  ``await
    gallery.run()`` is the host loop; it returns when the user quits
    (``q``, ``Ctrl-C``, a closed terminal) or the key source runs out.
    """

    def __init__(self, tui: TUI) -> None:
        self.tui = tui
        self.theme_index = 0
        self.fps = 0.0
        self.fps_on = True
        self.fps_frames = tui.painter.frames
        self.fps_at = tui.clock()
        self.page: Page | None = None
        self.body: PageBody | None = None
        self.preview: Pane | None = None
        self.preview_tick: EveryHandle | None = None
        #: The right pane the current page owns through its ``enter`` hook.
        self.aside: Pane | None = None
        #: The pointer tier for the current page's ring; retargeted per page.
        self.pointer: Pointer | None = None
        self._body_ids: list[str] = []
        self._in_show = False  # show() owns the round: the after-round stays out
        self.main = tui.frame.panes[0]  # the content pane; /split adds one beside it
        self.gesture = SelectionGesture(tui, on_end=self._copy_toast)
        self.scrollbar = Scrollbar(tui)
        self.toasts = Toasts(tui)
        self.header = Header(tui, PAGES, theme=self.theme)
        self.status = Status(tui, theme=self.theme)
        self.palette = PaletteOverlay(tui, palette_options(COMMANDS), theme=self.theme)
        tui.every(FPS_INTERVAL, self._fps_tick)
        tui.every(PAGE_TICK, self._page_tick)
        if PAGES:
            self.show(PAGES[0])
        tui.paint()

    @property
    def theme(self) -> Theme:
        """The session's current :data:`~gallery.content.THEMES` variant."""
        return THEMES[self.theme_index][1]

    # -- pages ------------------------------------------------------------------

    def show(self, page: Page) -> None:
        """Switch to ``page``: leave the old, replace the body, land at the top.

        The order is fixed: the previous page's ``leave`` runs first (its
        ``enter`` resources -- a pane, a mounted row -- are released while
        the page is still the current one), the pane slot is closed
        defensively (a page that forgot cannot leak its pane into the next
        visit), the previous body's blocks are removed, the new body's
        blocks are appended in order -- each its own block, which is what
        lets a click reach a widget -- then the new page's ``enter`` runs
        and the header, the status row and the pointer follow.  The blocks
        stay **open** (never sealed): a sealed block caches its rows, and a
        page's widgets must re-render when the focus, the hover and the
        click paths move them.
        """
        self.page = page
        self._in_show = True
        try:
            previous = self.body
            if previous is not None and previous.leave is not None:
                previous.leave(self)
            self.close_aside()
            self._clear_body()
            self.body = page.build(self)
            for block in self.body.blocks:
                self._body_ids.append(self.tui.add(block).id)
            if self.body.enter is not None:
                self.body.enter(self)
            self.main.focus()
            self.tui.scroll_up(1 << 20)  # out of stick-to-bottom: a page opens at its top
            self.header.refresh(page, self._page_index(), self.body)
            self._retarget_pointer()
            self._show_status()
        finally:
            self._in_show = False
        self.tui.invalidate()

    def _page_index(self) -> int:
        """The current page's index in :data:`~gallery.registry.PAGES`."""
        return PAGES.index(self.page) if self.page in PAGES else 0

    def _clear_body(self) -> None:
        """Remove every block the previous body mounted."""
        for block_id in self._body_ids:
            try:
                self.tui.remove(block_id)
            except KeyError:
                pass  # a page that removed its own block is its own business
        self._body_ids = []

    def _retarget_pointer(self) -> None:
        """Point the pointer tier at the new page: its ring, or none.

        A page switch is a pane switch's sibling -- the hovered leaf may be
        gone -- so the old pointer is cleared before the new one mounts;
        with a ring the pointer runs the ring's click policy, without one it
        dispatches the deepest clickable leaf itself.
        """
        if self.pointer is not None:
            self.pointer.clear()
        ring = None if self.body is None else self.body.focus
        self.pointer = Pointer(self.tui, ring=ring)

    def _follow_nav(self) -> None:
        """Land a click on the tab strip: switch to the tab it selected.

        The header's strip is a plain clickable component, so a stationary
        click on it is dispatched by the pointer like any other component's
        -- ``Tabs.click`` moves ``active`` -- and the host follows once per
        event round, exactly one round behind nothing.  A strip marker that
        already names the page on screen, and an out-of-range index, answer
        nothing.
        """
        index = self.header.nav.active
        if self.page is None or index == self._page_index():
            return
        if 0 <= index < len(PAGES):
            self.show(PAGES[index])

    # -- the loop ---------------------------------------------------------------

    async def run(self, _tui: TUI) -> None:
        """The host loop: read, route, repaint -- until quit or end of input.

        The driver calls its body with its own instance; the gallery is
        built on that same driver, so the argument is only the contract's
        shape.  The dispatch order is in the module docstring; a round's own
        work (:meth:`_after_round`) runs in the ``finally``, on every way a
        round can settle, and before the round's repaint can compose -- so a
        click that moved the tab strip or a pick that re-skinned the shell
        is painted with the round that made it.
        """
        tui = self.tui
        running = True
        while running:
            if not tui.interactive:
                # The replay never sleeps, so it outruns the pump's repaint
                # throttle: compose between events, or a scripted click would
                # hit-test against the frame as it stood two commands ago.
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
        """One event round's dispatch; ``False`` when the round asked to quit.

        The order is the module docstring's.  The short-circuit is
        load-bearing: a press on the scrollbar strip belongs to the bar, a
        press inside a toast band to the toast, and a drag's reports must
        reach the gesture rather than the pointer's hover.
        """
        consumed = self.scrollbar.handle(event)
        if not consumed:
            consumed = self.toasts.handle(event)
        if not consumed and self.palette.is_open:
            consumed = self.palette.handle(event)
            if consumed:
                pick = self.palette.palette.chosen
                self.palette.palette.chosen = None  # the host reads a pick exactly once
                if pick is not None:
                    return self._dispatch(str(pick))
                return True
        if not consumed:
            consumed = self.gesture.handle(event)
        # The pointer watches **beside** the gesture -- never skipped, and it
        # never consumes: its ``True`` is a repaint cue (the hover moved, or
        # a stationary click was dispatched through the ring's policy).  A
        # press is only remembered, a drag's motion drops it and touches no
        # hover, so the gesture keeps every report it owns.
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
        if name == "q" or name == "c-c":
            return False  # the two quit gestures
        if name == "/":
            self.palette.open()
        elif name == "c-n" and len(PAGES):
            self.show(PAGES[(self._page_index() + 1) % len(PAGES)])
        elif name == "c-p" and len(PAGES):
            self.show(PAGES[(self._page_index() - 1) % len(PAGES)])
        elif name == "tab" and ring is not None:
            ring.focus_next()  # the ring binds nothing; tab is the host's
        elif name == "c-o":
            self._cycle_panes()  # c-o is the frame's pane cycle
        elif name == "escape":
            self._close_preview()
        return True

    def _after_round(self) -> None:
        """A round's own work, exactly once, whatever tier dispatched it.

        The tab-strip follow (a click on a label moved ``Tabs.active``), the
        pick read (an activation -- key or click -- landed a ``chosen``),
        and the status refresh (the focus or the cursor may have moved); the
        span of :meth:`show` itself passes, since a page switch lands its
        own state whole.
        """
        if self._in_show:
            return
        self._follow_nav()
        self._read_picks()
        self._show_status()
        self.tui.invalidate()

    # -- activations and their echo ---------------------------------------------

    def _read_picks(self) -> None:
        """Read every ring target's pending pick once, then report it.

        The host half of the ``chosen`` contract the widgets document (the
        component writes it, the host reads it exactly once and resets it to
        ``None``): one scan per round, so the pick is read however it was
        produced -- the keyboard's ``enter`` or the click policy's second
        click.  A value that names a page opens that page; a value that
        names a theme variant on the styles page re-skins the shell (and the
        echo lands on the fresh page); every other pick is reported as
        ``chosen: <value>`` -- a toast, plus the page's own echo.
        """
        ring = None if self.body is None else self.body.focus
        if ring is None:
            return
        for target in ring.targets:
            chosen = getattr(target, "chosen", None)
            if chosen is None:
                continue
            target.chosen = None  # the host reads a pick exactly once
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

    def _dispatch(self, value: str) -> bool:
        """Run one chosen (or typed) palette command; ``False`` asks to quit."""
        name = value[1:] if value.startswith("/") else value
        command = BY_COMMAND.get(name)
        if command is None:
            self._report(f"unknown command: /{name}")
            return True
        keep_going = command.run(self)
        self.tui.invalidate()
        return keep_going

    # -- the action commands ----------------------------------------------------

    def cmd_split(self) -> bool:
        """``/split``: open the live preview pane, or close it again.

        The preview and a page's own pane share the one right-pane slot, so
        on a page that owns a pane the command opens nothing and toasts why
        -- a third pane is not what this exhibit demos.
        """
        if self.aside is not None:
            self._report("this page owns the right pane -- /split is for pages without one")
            return True
        if self.preview is None:
            self._open_preview()
        else:
            self._close_preview()
        return True

    def cmd_theme(self) -> bool:
        """``/theme``: cycle to the next variant, through :meth:`set_theme`."""
        return self.set_theme((self.theme_index + 1) % len(THEMES))

    def set_theme(self, index: int) -> bool:
        """Switch to ``THEMES[index]`` and rebuild everything built from it.

        The one road to a new skin, taken by ``/theme`` and by the styles
        exhibit's picker (whose ``chosen`` names the variant).  Every
        component that bakes styles at construction is rebuilt: the
        header's strip and rule, the status row, the palette, and the
        current page -- re-shown, so its widgets take the new theme too.
        Answers ``True``: a theme switch never ends the session.
        """
        self.theme_index = index % len(THEMES)
        theme = self.theme
        self.header.set_theme(theme)
        self.status.set_theme(theme)
        self.palette.set_theme(theme)
        if self.page is not None:
            self.show(self.page)  # a re-skin is a rebuild, not a page opening
        return True

    def cmd_fps(self) -> bool:
        """``/fps``: toggle the frame-rate readout on the status row."""
        self.fps_on = not self.fps_on
        self._show_status()
        return True

    def cmd_quit(self) -> bool:
        """``/quit``: leave the gallery."""
        return False

    # -- the readouts -------------------------------------------------------------

    def _show_status(self) -> None:
        """Publish ``<page> · focus=<target>`` and the readout on the status row."""
        name = "-" if self.page is None else self.page.name
        ring = None if self.body is None else self.body.focus
        target = None if ring is None else ring.focused
        self.status.refresh(name, _focus_name(target), fps=self.fps, fps_on=self.fps_on)

    def _fps_tick(self) -> None:
        """One sample: frames since the last tick over the wall interval; no
        invalidate, so the readout never measures its own repaints."""
        now, frames = self.tui.clock(), self.tui.painter.frames
        self.fps = (frames - self.fps_frames) / max(now - self.fps_at, 1e-6)
        self.fps_frames, self.fps_at = frames, now
        self._show_status()

    def _page_tick(self) -> None:
        """The page beat: run the current page's animation, if it has one."""
        body = self.body
        if body is None or body.tick is None:
            return
        body.tick()
        self.tui.invalidate()

    # -- the right pane: aside and preview --------------------------------------

    def open_aside(self) -> Pane:
        """Open the page's own right pane from the frame's split; return it.

        The page-side half of the pane story, called by a body's ``enter``:
        the preview gives the slot up first (the two are one slot, one pane
        deep), ``tui.split`` divides the primary pane -- the left child
        keeps the gallery's document, the right child opens empty -- and the
        pane is remembered so :meth:`close_aside` can hand the cells back.
        """
        self._close_preview()
        _, right = self.tui.split("vertical", ratios=(2, 1))
        self.aside = right
        self.tui.invalidate()
        return right

    def close_aside(self) -> None:
        """Close the page's own right pane; the gallery takes the width back.

        :meth:`~mocode_tui.core.frame.Pane.close` is the kernel's un-split;
        the collapsed parent keeps the gallery's document and the whole
        rectangle.  Called by :meth:`show` (before the next body mounts and,
        defensively, after a body's ``leave``), so a page switch never
        inherits the last exhibit's pane.
        """
        if self.aside is None:
            return
        self.aside.close()  # the kernel's un-split
        self.aside = None
        if self.tui.selection_pane is None:
            self.tui.set_selection(None)  # a selection in the closed pane lost its addresses
        self.tui.invalidate()

    def _open_preview(self) -> None:
        """``/split``'s opening half: a pane of live widgets beside the page.

        The pane opens over a fresh document with a beat of its own
        (``tui.every``), plus filler rows for its own wheel scroll; the
        block stays unsealed so it re-renders every frame.  The preview is
        shell chrome, not an exhibit: its live line is what proves the pane
        repaints on its own.
        """
        theme = self.theme
        _, right = self.tui.split("vertical", ratios=(2, 1))
        self.preview = right
        spinner = Spinner("live")
        bar = ProgressBar(0.0, label="preview", width_chars=14, theme=theme)
        line = Text(f"{spinner.frame} {spinner.text}", style=theme.accent)
        right.document.add(Column([
            Text("a second Pane", style=theme.accent),
            Text("the frame tiles; each pane scrolls on its own", style=DIM),
            line,
            bar,
            Spacer(1),
            Text("the wheel scrolls the pane under the pointer", style=DIM),
            *(Text(f"pane row {i:02d}") for i in range(20)),
        ]))
        self.preview_tick = self.tui.every(
            PAGE_TICK, lambda: self._tick_preview(spinner, bar, line)
        )
        self.tui.invalidate()

    def _tick_preview(self, spinner, bar, line) -> None:
        """One preview beat: step the spinner, advance the bar, repaint."""
        if self.preview is None:
            return
        spinner.advance()
        bar.fraction = (bar.fraction + 0.07) % 1.0
        line.text = f"{spinner.frame} {spinner.text}"
        self.tui.invalidate()

    def _close_preview(self) -> None:
        """``/split`` again, or escape: hand the pane's cells back."""
        if self.preview is None:
            return
        if self.preview_tick is not None:
            self.preview_tick.cancel()
            self.preview_tick = None
        self.preview.close()  # the kernel's un-split
        self.preview = None
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


#: Every palette entry: the registry's pages, then the session's own actions.
COMMANDS: tuple[Command, ...] = page_commands() + (
    Command("split", "Toggle the live preview pane", Gallery.cmd_split),
    Command("theme", "Cycle to the next theme variant", Gallery.cmd_theme),
    Command("fps", "Toggle the frame-rate readout", Gallery.cmd_fps),
    Command("quit", "Leave the gallery", Gallery.cmd_quit),
)

BY_COMMAND = {command.name: command for command in COMMANDS}
