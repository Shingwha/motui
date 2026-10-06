"""The showcase session: one controller over one :class:`~mocode_tui.app.TUI`.

:class:`Showcase` assembles the shell (the pinned banner, the transcript, the
composer footer, the scrollbar, the copy gesture), owns the session's state
(the theme variant, the frame-rate readout, the preview pane, the current
page) and runs the host loop.

**Driving a page.** While the composer is empty, the page's
:class:`~mocode_tui.focus.FocusRing` owns the interaction: ``tab`` cycles the
focus, the arrows move the focused widget and ``enter`` activates it, and a
stationary left click runs the ring's click policy (dispatch the cell, focus
the component it landed on, activate on the second click).  Anything typed
goes to the composer; a submit runs a command (a leading ``/``) or streams a
canned reply on the chat page.

**Every activation has an echo.**  A widget's activation lands its pick in
``chosen``; the host reads that value **once** and resets it, then reports it
-- a toast, plus the current page's optional
:attr:`~showcase.page.PageBody.note` hook, which lets the page echo the last
pick in a line of its own.  Both activation paths run through that one
report: the keyboard's ``enter`` and the second click of the click policy.
A target that can be activated but has no ``chosen`` to carry (a ``Tree``
folds; it takes nothing) still reports -- ``activate \u2192 tree``, the act
it performed, never a bare ``None`` that would read like a failure -- so one
activation is always one record.  The report is also where the pick is
dispatched: a value naming a page opens that page, and the styles exhibit's
pick names a theme, so the host re-skins through :meth:`Showcase.set_theme`.

**The log is the record every report leaves.**  :attr:`Showcase.log` keeps
the last :data:`LOG_ROWS` reports, newest first -- picks, focus moves and
page openings alike; it is the one story of the session, and a report that
would be noise as a toast (``focus \u2192 tree`` on every ``tab``, the
``\u2192 <page>`` of a page switch) passes ``toast=False`` and goes to the
log only.  The loud half -- the toast and the page's ``note`` echo -- stays
reserved for activations, whose outcome is what a page echoes; the
``interaction`` exhibit draws the whole log on its last-action rows, the
echoes arriving on the report itself and the quiet records on the page's own
beat.

**Moving between exhibits.** Three roads lead to a page, and all of them run
through :meth:`Showcase.show`: a click on the banner's tab strip (one short
label per page), the ``c-n``/``c-p`` keys for the next/previous exhibit (the
ends wrap), and the ``/`` palette by name.  ``show`` moves the strip's
``active`` marker and repaints the title and the status line, so the three
never disagree with the page on screen -- and it reports the road it took
(``\u2192 <page>``, logged without a toast) unless the caller is a rebuild
rather than a move (the theme switch re-shows the current page).

The command list is the registry's pages plus the four actions below -- the
palette's rows, the ``/help`` reply and the dispatch table all derive from it.
"""

from __future__ import annotations

import asyncio

from mocode_tui import (
    Column,
    Composer,
    Divider,
    DIM,
    EveryHandle,
    Key,
    Markdown,
    Message,
    MouseEvent,
    Pane,
    ProgressBar,
    Scrollbar,
    Selection,
    SelectionGesture,
    Spacer,
    Spinner,
    Tabs,
    Text,
    Theme,
    Toasts,
    Transcript,
    Tree,
    TreeNode,
    TUI,
    extract,
)
from mocode_tui.core import Activable, ellipsize_tail

from .content import PLACEHOLDER, REPLY_LONG, REPLY_SHORT, THEMES, THINKING
from .page import Page, PageBody
from .registry import BY_NAME, Command, PAGES, help_text, page_commands, palette_options

# Pacing in seconds (interactive sessions only -- the headless replay yields).
WORD_DELAY = 0.03   # per streamed word of the thinking preamble
LINE_DELAY = 0.04   # per streamed Markdown source line
FPS_INTERVAL = 0.5  # the frame-rate sampling period
PAGE_TICK = 0.1     # the page animation beat (live bars, spinners)

#: The banner's hint line is one row by contract: the pane's content width is
#: the screen minus the scrollbar's one budgeted column, and a line wider than
#: that wraps -- which would add a banner row and change the frame's geometry.
BANNER_CHROME = 1

#: The theme variants by name: the payload the styles exhibit's picker carries,
#: and the table :meth:`Showcase._read_pick` resolves a theme pick against.
THEME_INDEX = {name: index for index, (name, _) in enumerate(THEMES)}

#: How many recent reports :attr:`Showcase.log` keeps, newest first -- the
#: rows the ``interaction`` exhibit's last-action panel draws.
LOG_ROWS = 3


def _focus_name(target) -> str:
    """The short name of a focus target: its class, lower-cased.

    One spelling for the two readers of the focus -- the status line's
    ``focus=<name>`` and the log's ``focus \u2192 <name>`` -- so the readout
    and the record never disagree about who is holding the focus.
    """
    return "-" if target is None else type(target).__name__.lower()


class Showcase:
    """The showcase session, mounted at construction.

    ``Showcase(tui)`` builds the whole shell before it returns: the banner is
    pinned top, the transcript and chrome mount, the composer footer opens its
    band, and the overview page is on screen with the IME anchor parked.
    ``await session.run()`` is the host loop; it returns when the user quits
    (``Ctrl-C``, ``/quit``, a closed terminal) or the key source runs out, and
    it waits for any streaming reply before stopping the driver.
    """

    def __init__(self, tui: TUI) -> None:
        self.tui = tui
        self.theme_index = 0
        self.answered = False
        self.fps = 0.0
        self.fps_on = True
        self.fps_frames = tui.painter.frames
        self.fps_at = tui.clock()
        #: The last :data:`LOG_ROWS` reports, newest first -- the record every
        #: activation, focus move and page opening leaves (:meth:`_report`).
        self.log: list[str] = []
        self.preview: Pane | None = None
        self.preview_tick: EveryHandle | None = None
        self.replies: set[asyncio.Task[None]] = set()
        self.page: Page | None = None
        self.body: PageBody | None = None
        self._banner_ids: tuple[str, ...] = ()  # the pinned banner blocks, in row order
        self.composer: Composer
        self.main = tui.frame.panes[0]  # the content pane; /split adds one beside it
        self.transcript = Transcript(tui)
        self.toasts = Toasts(tui)
        self.scrollbar = Scrollbar(tui)
        self.gesture = SelectionGesture(tui, on_end=self._copy_to_toast)
        self._press: tuple[int, int] | None = None
        self._banner()
        self._mount_footer()
        tui.every(FPS_INTERVAL, self._fps_tick)
        tui.every(PAGE_TICK, self._page_tick)
        self.show(PAGES[0])
        self.composer.anchor_cursor()
        tui.paint()  # the very first frame already carries the IME anchor

    @property
    def theme(self) -> Theme:
        """The session's current :data:`~showcase.content.THEMES` variant."""
        return THEMES[self.theme_index][1]

    # -- pages ------------------------------------------------------------------

    def show(self, page: Page, *, announce: bool = True) -> None:
        """Switch to ``page``: replace the body, land it at the top, refocus.

        The transcript is emptied first, so a page never inherits the last
        one's blocks; the body's blocks are appended in order, each its own
        block -- which is what lets a click reach a widget.  The blocks stay
        **open** (never sealed): a sealed block caches its rows, and a page's
        widgets must re-render when the focus and click paths move them.
        The banner follows in :meth:`_banner_labels`, so the tab strip's
        marker, the title and the status line all name the page on screen.

        ``announce`` logs the road: every page opening -- a tab-strip click,
        ``c-n``/``c-p``, a palette pick, the overview's live index, a typed
        question landing on the chat page -- reports ``\u2192 <name>`` once
        (no toast: a page switch is a road, not a pick), after the new body
        is mounted, so the arriving exhibit's own echo reads it.  The
        rebuilds that are not roads pass ``announce=False``: the theme
        switch re-shows the current page, and re-opening it in the log would
        be a record of a move that never happened.
        """
        self.page = page
        self.transcript.theme = self.theme
        self.transcript.clear()
        self.body = page.build(self)
        for block in self.body.blocks:
            self.transcript.append(block)
        self.main.focus()
        self.tui.scroll_up(1 << 20)  # out of stick-to-bottom: a page opens at its top
        self._banner_labels()
        if announce:
            self._report(f"\u2192 {page.name}", toast=False)
        self.tui.invalidate()

    def _page_index(self) -> int:
        """The current page's index in :data:`PAGES` (0 for a page not listed)."""
        return PAGES.index(self.page) if self.page in PAGES else 0

    def _banner(self) -> None:
        """The header, pinned top: it survives scrolling and a page switch.

        Four one-row blocks, added in render order: the title, the tab strip
        (one label per page), the hint line and the rule.  Called again on a
        theme change -- the blocks are detached and re-added in that same
        order, and the rebuild is the only way the strip follows a new theme
        (``Tabs`` resolves its styles once, at construction, like every
        component).
        """
        for block_id in self._banner_ids:
            self.tui.remove(block_id)
        self._title = Text("", style=self.theme.accent)
        self._nav = Tabs([page.nav for page in PAGES], theme=self.theme)
        self._hint = Text("", style=DIM)
        self._rule = Divider(theme=self.theme)
        self._banner_ids = (
            self.tui.add(self._title, id="banner-title", pin="top").id,
            self.tui.add(self._nav, id="banner-tabs", pin="top").id,
            self.tui.add(self._hint, id="banner-hint", pin="top").id,
            self.tui.add(self._rule, id="banner-rule", pin="top").id,
        )

    def _banner_labels(self) -> None:
        """Repaint the header for the current page (and theme).

        The title names the exhibit, the strip below it marks the exhibit's
        tab (``active`` moves with the page), and the hint says what the
        page's focus ring answers to -- the ring's own ``\u2191\u2193`` and
        ``enter`` -- plus the shell's keys: the strip's click, the exhibit
        keys, the focus keys, the composer's submit and the quit.  The pane
        focus (``c-o``) is deliberately not in the line -- ``/help``, the
        ``keys`` exhibit and the README carry it, and the line is one row by
        contract, so the shell truncates its own copy to the pane's content
        width instead of letting it wrap (and the widest page keeps a margin
        under that ceiling).
        """
        keys = ("click a tab \u00b7 c-n / c-p exhibits \u00b7 tab focus "
                "\u00b7 enter sends \u00b7 c-c quits")
        body = self.body
        focus = None if body is None else body.focus
        if focus is not None and body.hint:
            keys = f"\u2191\u2193/enter: {body.hint} \u00b7 {keys}"
        name = "" if self.page is None else f" \u00b7 {self.page.name}"
        self._title.text = f"mocode-tui showcase{name}"
        self._title.style = self.theme.accent
        self._nav.select(self._page_index())
        self._hint.text = ellipsize_tail(keys, max(self.tui.screen.width - BANNER_CHROME, 20))
        self._rule.style = self.theme.border
        self._show_status()

    # -- the loop ---------------------------------------------------------------

    async def run(self, _tui: TUI) -> None:
        """The host loop: read, route, repaint -- until quit or end of input.

        The driver calls its body with its own instance; the showcase is built
        on that same driver, so the argument is only the contract's shape.
        """
        tui = self.tui
        while True:
            if not tui.interactive:
                # The replay never sleeps, so it outruns the pump's repaint
                # throttle: compose between events, or a scripted click would
                # hit-test against the frame as it stood two commands ago.
                tui.paint()
            event = await tui.read_key()
            if event is None:
                break  # source exhausted (piped replay) or terminal closed
            # The documented dispatch order -- chrome, then overlays, then the
            # content gesture -- with each tier seeing the event only while the
            # one before it left it alone.  The short-circuit is load-bearing:
            # a press on the scrollbar strip belongs to the bar, and the gesture
            # must not also anchor a selection there (holding the bar and
            # dragging it would copy the rows it scrolls past).
            consumed = self.scrollbar.handle(event)
            if not consumed:
                consumed = self.toasts.handle(event)
            if not consumed:
                consumed = self.gesture.handle(event)
                if isinstance(event, MouseEvent):
                    self._page_click(event)  # a stationary click is the ring's; a drag is not
            if consumed:
                self.composer.anchor_cursor()
                tui.invalidate()
                continue
            composer = self.composer
            palette = composer.palette
            if palette.is_open and palette.handle(event):
                chosen = palette.chosen
                palette.chosen = None  # the host reads the pick exactly once
                if chosen is not None:
                    composer.editor.clear()
                    if not self._dispatch(str(chosen)):
                        break
                self.composer.anchor_cursor()  # /theme may have rebuilt the footer
                tui.invalidate()
                continue
            editor = composer.editor
            ring = None if self.body is None else self.body.focus
            # The ring plays only the non-printing keys, and only while the
            # composer is empty.  Printables always belong to the composer (a
            # page field holding the focus must never steal a typed "/"), and
            # with text in the box the arrows are its own (the cursor, the
            # wrapped rows, the submit) -- the one rule that keeps the two
            # from fighting over a keypress.  Tab, c-o and the exhibit keys
            # never reach the ring's routing table; the host branches below
            # own them.
            playing = (
                ring is not None
                and not editor.text
                and isinstance(event, Key)
                and not isinstance(event, MouseEvent)
                and not event.char
            )
            if playing and ring.handle(event):
                if event.name == "enter" and isinstance(ring.focused, Activable):
                    # The ring ran the focused target's activation verb: read the
                    # pick it took once, or the act when it had no pick to take.
                    # A target that is not Activable never gets here on an enter
                    # it consumed -- that key is its own (the editor breaks the
                    # line) -- so no activation, no record.
                    self._read_pick(activation=True)
            elif editor.handle(event):
                pass  # an editing key: the editor consumed it
            elif event.name == "c-c":
                break
            elif event.name == "c-n":
                self.show(PAGES[(self._page_index() + 1) % len(PAGES)])
            elif event.name == "c-p":
                self.show(PAGES[(self._page_index() - 1) % len(PAGES)])
            elif event.name == "tab":
                if ring is not None and ring.focus_next():
                    # tab is the focus ring's cycle; the move is logged, not
                    # toasted -- a toast on every tab would flood the screen.
                    self._report(f"focus \u2192 {_focus_name(ring.focused)}", toast=False)
                if ring is not None:
                    self._show_status()  # ... and the readout follows the focus
            elif event.name == "c-o":
                self._cycle_focus()  # c-o is the frame's pane cycle
            elif event.name == "escape":
                self._close_preview()
            elif event.name == "enter":
                text = editor.text.strip()
                editor.clear()
                if text.startswith("/"):
                    if not self._dispatch(text):
                        break
                elif text:
                    await self._ask(text)
            # The leading slash owns the palette; /theme may have rebuilt the
            # footer, so re-read its pieces before touching them.
            composer = self.composer
            editor, palette = composer.editor, composer.palette
            if editor.text.startswith("/") and not palette.is_open:
                palette.open()
            else:
                palette.set_query(editor.text)
            composer.anchor_cursor()  # every keypress re-pins the IME cursor
            tui.invalidate()

        if self.replies:
            # Let in-flight turns finish so the transcript (and the dump) ends whole.
            await asyncio.gather(*self.replies)
        tui.stop()

    # -- clicking into a page ---------------------------------------------------

    def _page_click(self, event: MouseEvent) -> None:
        """Route a stationary left click: the tab strip first, then the ring.

        A drag belongs to the selection gesture; only a press released on its
        own cell plays.  The hit resolves to a *block's* component: a click on
        the tab strip is the strip's -- ``Tabs.click`` resolves the cell
        against its own row, and a hit follows ``active`` to that page (the
        strip's padding and the dividers between its labels answer ``False``
        and do nothing).  Every other hit goes to the page's focus ring, whose
        click policy dispatches the cell, focuses the component it landed on
        and activates on the second click -- the second click on the focused
        target is the one activation the host reads a pick from.
        """
        if event.name != "left":
            return
        if event.kind == "press":
            self._press = (event.x, event.y)
            return
        if event.kind == "motion":
            self._press = None
            return
        stationary = self._press == (event.x, event.y)
        self._press = None
        if not stationary:
            return
        hit = self.tui.hit_test(event.x, event.y)
        if hit is None:
            return
        if hit.block.component is self._nav:
            if self._nav.click(hit.row, hit.col):
                self.show(PAGES[self._nav.active])
            return
        ring = None if self.body is None else self.body.focus
        if ring is None:
            return
        # What the ring's click policy is about to do, read before the call: a
        # target that does not hold the focus is the policy's *focus* step --
        # the same move `tab` makes, and the same record it leaves -- and the
        # target that does hold it is the policy's *activation* step, the
        # second click, and the one click that reads a pick.
        component = hit.block.component
        moves = component is not ring.focused and any(
            component is known for known in ring.targets
        )
        activates = component is ring.focused and isinstance(component, Activable)
        ring.click(hit)  # the ring dispatches, focuses, and activates (second click)
        if moves:
            self._report(f"focus \u2192 {_focus_name(ring.focused)}", toast=False)
        self._read_pick(activation=activates)
        self._show_status()  # the click may have moved the focus or the cursor
        self.tui.invalidate()

    def _read_pick(self, *, activation: bool = False) -> None:
        """Read the focused target's activation once, then report it.

        The host half of the ``chosen`` contract the widgets document (the
        component writes it, the host reads it exactly once and resets it to
        ``None``): the value the pick carries is what gets reported as
        ``chosen: <repr>`` -- and a pick whose value names a page opens that
        page, which is how the overview's live index walks the exhibits (the
        opening logs its own ``\u2192 <page>`` road; the pick itself is not a
        toast either, because a page switch is not a pick).  A value that
        names a theme variant (the styles exhibit's picker) instead re-skins
        through :meth:`set_theme`; every other pick only echoes.  An option
        that carries no payload reports the option itself, so a toast never
        reads a bare ``None``.

        ``activation`` says the ring just ran the target's ``activate()``
        verb (the keyboard's ``enter``, or the second click of the click
        policy).  An activation that produced no pick reports the act it
        performed instead of a value -- ``activate \u2192 <name>``, the shape
        ``focus \u2192 <name>`` already uses -- because a target like a
        ``Tree`` folds and has no ``chosen`` to carry at all, and ``chosen:
        None`` there would read like a failure rather than a fold.  One
        activation is therefore always exactly one record, whatever it
        produced; without ``activation`` a target with nothing to read
        reports nothing: no activation, no echo.
        """
        ring = None if self.body is None else self.body.focus
        target = None if ring is None else ring.focused
        if target is None:
            return  # no ring, or a ring with nothing focused: nothing can happen
        chosen = getattr(target, "chosen", None)
        if chosen is None:
            if activation:
                self._report(f"activate \u2192 {_focus_name(target)}")
            return
        target.chosen = None  # the host reads a pick exactly once
        value = getattr(chosen, "value", chosen)
        if value is None:
            value = chosen  # a payload-less option: report the option itself
        page = BY_NAME.get(str(value))
        if page is not None:
            self.show(page)  # the pick named an exhibit: open it (and log the road)
            return
        self._report(f"chosen: {value!r}")
        theme_index = THEME_INDEX.get(str(value))
        if theme_index is not None and self.page is STYLES:
            self.set_theme(theme_index)  # the pick named a theme: re-skin

    def _report(self, text: str, *, toast: bool = True) -> None:
        """Publish one report: the log it always leaves, then the loud half.

        The single outlet every path goes through -- an activation's pick,
        the ``focus \u2192 <name>`` of a ``tab``, the ``\u2192 <page>`` of a
        page opening -- so the session has one story of what just happened.
        ``self.log`` takes ``text`` first, keeping the last
        :data:`LOG_ROWS` reports with the newest in front: the record no
        report skips, whatever else it does.  ``toast=True`` (the default,
        the activation paths) is the loud half: the toast, and the current
        page's optional :attr:`~showcase.page.PageBody.note` hook -- whose
        contract is one *activation's* outcome -- so a page that draws the
        log echoes a pick the moment it is taken.  The quiet paths pass
        ``toast=False`` (a focus move, a page opening): the log keeps them
        and the screen is spared a toast per tab.  The page is read here,
        before anything else could switch it, so the echo lands on the
        exhibit that produced the pick.
        """
        self.log.insert(0, text)
        del self.log[LOG_ROWS:]
        if not toast:
            return
        self.toasts.show(text)
        body = self.body
        if body is not None and body.note is not None:
            body.note(text)

    def _dispatch(self, value: str) -> bool:
        """Run one chosen (or typed) command; ``False`` when it asks to quit."""
        name = value[1:] if value.startswith("/") else value
        command = BY_COMMAND.get(name)
        if command is None:
            self.transcript.append(Message("assistant", help_text(COMMANDS), theme=self.theme))
            self.tui.invalidate()
            return True
        keep_going = command.run(self)
        self.tui.invalidate()
        return keep_going

    # -- the action commands ----------------------------------------------------

    def cmd_split(self) -> bool:
        """``/split``: open the live preview pane, or close it again."""
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

        The one road to a new skin, taken by ``/theme`` (which asks for the
        next variant) and by the styles exhibit's picker (whose ``chosen``
        names the variant, read once by :meth:`_read_pick`).  The composer
        keeps whatever was typed -- it is detached and remounted, since its
        styles resolved at construction -- and so do the banner (the ``Tabs``
        strip bakes its own) and the current page, which is rebuilt from the
        new theme.  Answers ``True``: a theme switch never ends the session.
        """
        self.theme_index = index % len(THEMES)
        typed = self.composer.editor.text
        self.composer.detach()
        self._mount_footer()
        if typed:
            self.composer.editor.insert(typed)
        self._banner()  # the strip bakes its styles: rebuild it on the new theme
        if self.page is not None:
            self.show(self.page, announce=False)  # a re-skin is not a page opening
        return True

    def cmd_fps(self) -> bool:
        """``/fps``: toggle the frame-rate readout on the status line."""
        self.fps_on = not self.fps_on
        self._show_fps()
        return True

    def cmd_quit(self) -> bool:
        """``/quit``: leave the showcase."""
        return False

    # -- the footer and its readouts --------------------------------------------

    def _mount_footer(self) -> None:
        """Mount the ``Composer`` footer on the session's current theme."""
        composer = Composer(
            self.tui,
            theme=self.theme,
            placeholder=PLACEHOLDER,
            commands=palette_options(COMMANDS),
        )
        self.composer = composer
        self._show_fps()
        self._show_status()

    def _show_status(self) -> None:
        """Publish the exhibit and its focused object on the status line's left.

        ``<page> \u00b7 focus=<target>``: the page's authoritative name and the
        focused ring target's class name lower-cased (``table``, ``select``,
        ``tree``).  A page with no ring, or a ring with nothing focused, reads
        ``focus=-``; the frame-rate readout keeps the line's right side.
        """
        name = "-" if self.page is None else self.page.name
        ring = None if self.body is None else self.body.focus
        target = None if ring is None else ring.focused
        focus = _focus_name(target)
        self.composer.statusline.left = (f"{name} \u00b7 focus={focus}",)

    def _show_fps(self) -> None:
        """Publish the readout (or its off state) on the status line's right."""
        self.composer.statusline.right = (
            (f"{self.fps:.1f} fps",) if self.fps_on else ("fps off",)
        )

    def _fps_tick(self) -> None:
        """One sample: frames since the last tick over the wall interval; no
        invalidate, so the readout never measures its own repaints."""
        now, frames = self.tui.clock(), self.tui.painter.frames
        self.fps = (frames - self.fps_frames) / max(now - self.fps_at, 1e-6)
        self.fps_frames, self.fps_at = frames, now
        self._show_fps()

    def _page_tick(self) -> None:
        """The page beat: run the current page's animation, if it has one."""
        body = self.body
        if body is None or body.tick is None:
            return
        body.tick()
        self.tui.invalidate()

    # -- the chat page's turns --------------------------------------------------

    async def _ask(self, question: str) -> None:
        """Stream a canned answer: land on the chat page, then answer there."""
        if self.page is not CHAT:
            self.show(CHAT)
        if not self.tui.interactive:
            await self._answer(question)  # the replay awaits each turn in order
            return
        task = asyncio.create_task(self._answer(question))
        self.replies.add(task)
        task.add_done_callback(self.replies.discard)

    async def _answer(self, question: str) -> None:
        """One local turn: echo, think, stream the reply, seal; the first turn
        gets the long self-description, later turns the short one."""
        tui, transcript = self.tui, self.transcript
        transcript.append(Message("user", question, theme=self.theme))
        thinking = transcript.stream("thinking")
        for index, word in enumerate(THINKING.split(" ")):
            thinking.append(word if index == 0 else f" {word}")
            tui.invalidate()
            await self._beat(WORD_DELAY)
        thinking.seal()
        composer = self.composer
        composer.set_working(True)
        try:
            rich, self.answered = not self.answered, True
            markdown = Markdown("", theme=self.theme)
            block = transcript.append(markdown)
            await self._stream(markdown, REPLY_LONG if rich else REPLY_SHORT)
            block.seal()
        finally:
            composer.set_working(False)
        tui.paint()

    async def _stream(self, markdown: Markdown, text: str) -> None:
        """Grow ``markdown`` one source line per beat, invalidating at every prefix."""
        lines = text.split("\n")
        for end in range(1, len(lines) + 1):
            markdown.text = "\n".join(lines[:end])
            self.tui.invalidate()
            await self._beat(LINE_DELAY)
        self.tui.paint()

    async def _beat(self, delay: float) -> None:
        """Pace one chunk: the delay interactive, a bare yield headless --
        ``sleep(0)`` still yields to the pump, without any real time passing."""
        await asyncio.sleep(delay if self.tui.interactive else 0)

    # -- the preview pane -------------------------------------------------------

    def _open_preview(self) -> None:
        """``/split``'s opening half: a pane of live widgets beside the page.

        The pane opens over a fresh document with components ticked by
        ``tui.every``, plus filler rows for its own wheel scroll; the block
        stays unsealed so they re-render every frame.
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
            Tabs(["live", "row", "wheel"], active=0, theme=theme),
            line,
            bar,
            Spacer(1),
            Tree([TreeNode("frame", [TreeNode("Pane"), TreeNode("chrome")], expanded=True)],
                 theme=theme),
            Divider(theme=theme),
            Text("the wheel scrolls the pane under the pointer", style=DIM),
            *(Text(f"pane row {i:02d}") for i in range(20)),
        ]))
        self.preview_tick = self.tui.every(
            PAGE_TICK, lambda: self._tick_preview(spinner, bar, line)
        )
        self.tui.invalidate()

    def _tick_preview(self, spinner: Spinner, bar: ProgressBar, line: Text) -> None:
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

    def _cycle_focus(self) -> None:
        """``c-o``: focus the next pane in the frame's order (wrapping around)."""
        panes = self.tui.frame.panes
        focused = self.tui.frame.focused_pane
        if focused is None or not panes:
            return
        ids = [pane.id for pane in panes]
        if focused.id in ids:
            panes[(ids.index(focused.id) + 1) % len(panes)].focus()

    def _copy_to_toast(self, tui: TUI, selection: Selection) -> None:
        """The selection ``on_end``: copy the range through OSC 52 and toast the
        answer -- only when the screen answered ``True`` (a pipe has no clipboard)."""
        pane = tui.selection_pane
        document = tui.document if pane is None else pane.document
        region = None if pane is None else tui.frame.region(pane.id)
        width = tui.screen.width if region is None else region.width
        text = extract(document, selection, width=width)
        if tui.screen.copy(text):
            self.toasts.show(f"Copied {len(text.splitlines())} lines")


#: The page a typed question lands on.
CHAT = BY_NAME["chat"]

#: The exhibit whose picker picks a theme: its picks re-skin the session.
STYLES = BY_NAME["styles"]

#: Every palette entry: the registry's pages, then the session's own actions.
COMMANDS: tuple[Command, ...] = page_commands() + (
    Command("split", "Toggle the live preview pane", Showcase.cmd_split),
    Command("theme", "Cycle to the next theme variant", Showcase.cmd_theme),
    Command("fps", "Toggle the frame-rate readout", Showcase.cmd_fps),
    Command("quit", "Leave the showcase", Showcase.cmd_quit),
)

BY_COMMAND = {command.name: command for command in COMMANDS}
