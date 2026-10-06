"""The showcase session: one controller over one :class:`~mocode_tui.app.TUI`.

:class:`Showcase` assembles the shell (the pinned banner, the transcript, the
composer footer, the scrollbar, the copy gesture), owns the session's state
(the theme variant, the frame-rate readout, the preview pane, the current
page) and runs the host loop.

**Playing with a page.** While the composer is empty, the page's
:class:`~mocode_tui.focus.FocusRing` owns the interaction: ``tab`` cycles the
focus, the arrows move the focused widget and ``enter`` activates it, and a
stationary left click runs the ring's click policy (dispatch the cell, focus
the component it landed on, activate on the second click).  Anything typed
goes to the composer; a submit runs a command (a leading ``/``) or streams a
canned reply on the chat page.

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

from .content import PLACEHOLDER, REPLY_LONG, REPLY_SHORT, THEMES, THINKING
from .page import Page, PageBody
from .registry import BY_NAME, Command, PAGES, help_text, page_commands, palette_options

# Pacing in seconds (interactive sessions only -- the headless replay yields).
WORD_DELAY = 0.03   # per streamed word of the thinking preamble
LINE_DELAY = 0.04   # per streamed Markdown source line
FPS_INTERVAL = 0.5  # the frame-rate sampling period
PAGE_TICK = 0.1     # the page animation beat (live bars, spinners)


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
        self.preview: Pane | None = None
        self.preview_tick: EveryHandle | None = None
        self.replies: set[asyncio.Task[None]] = set()
        self.page: Page | None = None
        self.body: PageBody | None = None
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

    def show(self, page: Page) -> None:
        """Switch to ``page``: replace the body, land it at the top, refocus.

        The transcript is emptied first, so a page never inherits the last
        one's blocks; the body's blocks are appended in order, each its own
        block -- which is what lets a click reach a widget.  The blocks stay
        **open** (never sealed): a sealed block caches its rows, and a page's
        widgets must re-render when the focus and click paths move them.
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
        self.tui.invalidate()

    def _banner(self) -> None:
        """The header, pinned top: it survives scrolling and a page switch."""
        self._title = Text("", style=self.theme.accent)
        self._hint = Text("", style=DIM)
        self._rule = Divider(theme=self.theme)
        self.tui.add(self._title, pin="top")
        self.tui.add(self._hint, pin="top")
        self.tui.add(self._rule, pin="top")

    def _banner_labels(self) -> None:
        """Repaint the header for the current page (and theme).

        The hint says what a page's focus ring answers to: the ring's own
        ``tab`` (focus), the frame's ``c-o`` (pane), and what ``\u2191\u2193``
        and ``enter`` will drive while the composer is empty.
        """
        # One row at the pane width (109 of the 110-column headless screen):
        # the page hint first, then the shell's keys.  "/ pages" is left to
        # the composer's own placeholder, which is visible at every keystroke.
        keys = ("tab focus \u00b7 c-o pane \u00b7 enter sends \u00b7 c-j newline "
                "\u00b7 drag copies \u00b7 ctrl-c quits")
        body = self.body
        focus = None if body is None else body.focus
        if focus is not None and body.hint:
            keys = f"\u2191\u2193/enter: {body.hint} \u00b7 {keys}"
        name = "" if self.page is None else f" \u00b7 {self.page.name}"
        self._title.text = f"mocode-tui showcase{name}"
        self._title.style = self.theme.accent
        self._hint.text = keys
        self._rule.style = self.theme.border

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
            # from fighting over a keypress.  Tab and c-o never reach the
            # ring's routing table; the host branches below own them.
            playing = (
                ring is not None
                and not editor.text
                and isinstance(event, Key)
                and not isinstance(event, MouseEvent)
                and not event.char
            )
            if playing and ring.handle(event):
                pass  # the page's focus ring consumed the key
            elif editor.handle(event):
                pass  # an editing key: the editor consumed it
            elif event.name == "c-c":
                break
            elif event.name == "tab":
                if ring is not None:
                    ring.focus_next()  # tab is the focus ring's cycle
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
        """Route a stationary left click into the page's focus ring.

        A drag belongs to the selection gesture; only a press released on its
        own cell plays.  The hit resolves to a *block's* component, and the
        ring decides what it means: dispatch the cell, focus the component it
        landed on, activate on the second click.
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
        ring = None if self.body is None else self.body.focus
        if ring is None:
            return
        hit = self.tui.hit_test(event.x, event.y)
        if hit is None:
            return
        ring.click(hit)  # the ring dispatches, focuses, and activates (second click)
        self.tui.invalidate()

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
        """``/theme``: cycle the theme variants and rebuild shell and page."""
        self.theme_index = (self.theme_index + 1) % len(THEMES)
        typed = self.composer.editor.text
        self.composer.detach()
        self._mount_footer()
        if typed:
            self.composer.editor.insert(typed)
        if self.page is not None:
            self.show(self.page)  # the page is built from the theme: rebuild it
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
        composer.statusline.left = ("mocode-tui showcase \u00b7 local, no network",)
        self.composer = composer
        self._show_fps()

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

#: Every palette entry: the registry's pages, then the session's own actions.
COMMANDS: tuple[Command, ...] = page_commands() + (
    Command("split", "Toggle the live preview pane", Showcase.cmd_split),
    Command("theme", "Cycle the replacement themes", Showcase.cmd_theme),
    Command("fps", "Toggle the frame-rate readout", Showcase.cmd_fps),
    Command("quit", "Leave the showcase", Showcase.cmd_quit),
)

BY_COMMAND = {command.name: command for command in COMMANDS}
