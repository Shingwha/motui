"""The runtime: the session lifecycle, the pump, the clock and the painter.

:class:`Runtime` owns the pieces a full-screen session needs around the
:class:`~motui.app.workspace.Workspace`: the
:class:`~motui.terminal.terminal.Terminal` it enters, leaves and reads
through, the :class:`~motui.terminal.paint.Painter` that writes the diff,
the :class:`Timer` schedule, the dirty flag and the run lifecycle.  It owns
no document, frame, pane, selection or dock of its own -- those live on
:attr:`workspace` -- and its paint step is one composition of that
workspace::

    layout = workspace.frame.compose(width, height)
    layout = workspace.frame.apply_overlays(layout)
    painter.paint(layout.surface)

**The clock and the pump.**  :meth:`clock` is the one seam time enters
through; :meth:`advance` moves a virtual offset over it so a replay is
deterministic.  :meth:`tick` runs due timers first (they may invalidate the
frame), then paints at most one frame when the workspace is dirty and the
throttle has elapsed.  A timer's deadline advances by whole periods
(``next_run += period``), so a late tick never shifts the phase; the
``catch_up`` posture decides whether missed deadlines are skipped or
coalesced.  The library never sleeps and never builds an event loop of its
own.

**The protocol surface.**  :meth:`set_title` (OSC 2),
:meth:`set_cursor_shape` (DECSCUSR) and :meth:`copy_to_clipboard` (OSC 52)
are the three host-owned terminal gestures, written through the terminal;
the library declares, the host decides.

:meth:`read_event` is a **pure read**: it returns the next event or
``None`` and owns no scroll or focus policy.  The default orchestration
lives one level up in :class:`~motui.app.application.App`; a host driving
``Runtime`` directly keeps its own loop.

:meth:`run_session` / :meth:`run_async` / :meth:`run` bracket
``enter``/``leave`` around the body (even on exceptions and ``exit()``),
stay completely silent on a non-live screen, and dump the final screen as
plain text when piped.

**The dispatch order**, one rule everywhere: a composition paints each
pane's chrome budget first, then that pane's content rows, then the granted
chrome strips over them, then the docks, then the overlay registry over
everything (:mod:`motui.kernel.frame`); a host routes an event the same way
-- chrome, then overlays, then the panes' content, then its own dispatch
(:mod:`motui.app.overlays`).
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable

from ..kernel.events import Event, EventSource
from ..kernel.theme import DEFAULT_THEME, Theme
from ..terminal.ansi import cursor_shape, set_window_title
from ..terminal.paint import Painter
from ..terminal.screen import MouseMode, Screen
from ..terminal.terminal import Terminal
from ..terminal import RawTerminalKeys
from .workspace import Workspace

__all__ = ["Runtime"]


class Timer:
    """One periodic callback scheduled on the driver's clock.

    ``next_run`` is an **absolute deadline**, not a delay: each firing adds
    exactly one ``period`` to it, so a callback that takes time to run does
    not push the schedule out.  When a tick arrives late, ``catch_up`` picks
    the posture -- ``"skip"`` runs the callback once and realigns the next
    deadline to ``now + period`` when the deadline already passed, while
    ``"coalesce"`` runs once and advances the deadline by whole periods until
    it is in the future, preserving the phase.  Either way one tick invokes a
    callback at most once.

    The value is its own cancellable handle: ``cancelled`` answers whether
    :meth:`cancel` has run, and a cancelled timer never fires again.  The
    1.x separate handle class is gone; ``every`` is the only constructor a
    host needs.
    """

    __slots__ = ("_cancelled", "catch_up", "fn", "next_run", "period")

    def __init__(
        self,
        period: float,
        fn: Callable[[], object],
        next_run: float = 0.0,
        *,
        catch_up: str = "skip",
    ) -> None:
        if period <= 0:
            raise ValueError(f"timer period must be positive, got {period!r}")
        if catch_up not in ("skip", "coalesce"):
            raise ValueError(
                f"catch_up must be 'skip' or 'coalesce', got {catch_up!r}"
            )
        self._cancelled = False
        self.period = period
        self.fn = fn
        self.next_run = next_run
        self.catch_up = catch_up

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def cancel(self) -> None:
        """Stop future invocations (a callback already running finishes)."""
        self._cancelled = True

    def __repr__(self) -> str:
        return (
            f"Timer(period={self.period!r}, next_run={self.next_run!r}, "
            f"catch_up={self.catch_up!r}, cancelled={self.cancelled})"
        )


def _stdin_isatty() -> bool:
    """Whether stdin is a TTY right now (never raises)."""
    try:
        stream = sys.stdin
        return stream is not None and bool(stream.isatty())
    except Exception:
        return False


class Runtime:
    """A full-screen session driver over one workspace.

    ``terminal`` is the one configuration door: a
    :class:`~motui.terminal.terminal.Terminal` brings its own screen (with
    the mouse mode already mapped), input source and clipboard, and the
    driver enters, leaves and reads through it.  The input source defaults
    to none (``read_event`` then returns ``None``); a screen's tracking
    switches live on its :class:`~motui.terminal.screen.TerminalOptions`,
    never here.

    ``interactive`` says whether :meth:`run` may attach a
    :class:`RawTerminalKeys` source when the session is live and no source
    was supplied; it is off by default, so a test-driven runtime never
    touches the real input.  ``throttle`` is the pump's flush interval.
    ``theme`` is handed to the workspace (its chrome and the selection
    highlight); widgets are never themed from here, they each take
    ``theme=`` themselves.

    The workspace -- its document, viewport, frame, panes, selection and
    docks -- is constructed here and exposed as :attr:`workspace`; every
    content mutation goes through it, while the runtime keeps the session
    around it.
    """

    def __init__(
        self,
        terminal: Terminal,
        *,
        throttle: float = 0.030,
        interactive: bool = False,
        theme: Theme | None = None,
    ) -> None:
        self._terminal = terminal
        self._screen = terminal.screen
        #: The event source the runtime reads; :meth:`run` may replace it with
        #: a server-owned raw source when the session is interactive.
        self.keys = terminal.input
        #: The hover switch the attached raw source opens: the terminal's
        #: mouse mode is the one configuration point.
        self._hover = terminal.options.mouse is MouseMode.MOVE
        self.painter = Painter(self._screen, sync=terminal.options.sync)
        self.throttle = throttle
        self.interactive = interactive
        self._dirty = True
        self._stopped = False
        self._last_paint = float("-inf")
        self._timers: list[Timer] = []
        #: The workspace this runtime paints: it owns the document, the frame
        #: and every interaction surface; the runtime owns the session around
        #: it and calls ``workspace.frame`` / ``workspace.rows`` at paint time.
        self.workspace = Workspace(
            self, theme=DEFAULT_THEME if theme is None else theme
        )
        #: The clock the driver adds its virtual offset to.  A test may swap
        #: this (or replace ``clock`` outright) to control time.
        self._clock: Callable[[], float] = time.monotonic
        #: The virtual time :meth:`advance` has added to the clock.
        self._clock_offset = 0.0
        self._wake_event: asyncio.Event | None = None
        self._wake_loop: asyncio.AbstractEventLoop | None = None
        #: The source this driver attached itself (never one the caller handed
        #: in): teardown closes exactly this, whatever ``self.keys`` says then.
        self._owned_source: EventSource | None = None
        #: Set by :meth:`exit` and awaited by :meth:`read_event`: a pending
        #: read returns ``None`` the moment the session ends.
        self._exit_event: asyncio.Event | None = None

    # -- read-only views ---------------------------------------------------------

    @property
    def screen(self) -> Screen:
        """The driver's screen; a host never replaces it mid-run."""
        return self._screen

    @property
    def terminal(self) -> Terminal:
        """The terminal endpoint this runtime enters, leaves and reads through.

        The one configuration door: the terminal owns the screen, its input
        source and its clipboard, so the runtime never builds or replaces a
        screen by itself.
        """
        return self._terminal

    # -- clipboard ---------------------------------------------------------------

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard through the terminal (OSC 52).

        The terminal's :class:`~motui.terminal.clipboard.ScreenClipboard`
        writes the bytes; a non-live screen answers ``False`` without
        touching the stream, exactly as :meth:`Screen.copy_to_clipboard
        <motui.terminal.screen.Screen.copy_to_clipboard>` does.
        """
        return self._terminal.clipboard.copy(text)

    # -- protocol surface ---------------------------------------------------------

    def set_title(self, text: str) -> None:
        """Set the terminal window title (OSC 2), control bytes scrubbed.

        A host-owned gesture -- the driver never titles a window by itself
        (the demo titles one per page in its ``show``).  The bytes go
        through ``screen.write`` and a flush, and they are **not** gated on
        liveness: a headless screen or a test double records them, so the
        call is assertable without a terminal (only the session bracket and
        :meth:`Screen.copy` are live-gated).
        """
        self.screen.write(set_window_title(text))
        self.screen.flush()

    def set_cursor_shape(self, shape: str) -> None:
        """Ask the terminal for a cursor shape (DECSCUSR).

        ``block`` / ``beam`` / ``underline`` / ``default``; an unknown shape
        raises ``KeyError``.  The library only *declares* which shape a
        component wants -- ``Input`` and ``Editor`` carry
        ``cursor_shape="beam"`` -- and the host reads the focused leaf
        (``getattr(leaf, "cursor_shape", "block")``) and calls this; written
        like :meth:`set_title`, non-live screens included.
        """
        self.screen.write(cursor_shape(shape))
        self.screen.flush()

    # -- frames ---------------------------------------------------------------

    def refresh(self) -> None:
        """Mark the frame dirty; the pump repaints once the throttle allows."""
        self._dirty = True
        self._wake()

    def paint(self) -> None:
        """Paint one frame right now, bypassing the throttle."""
        self._paint_at(self.clock())

    def every(
        self,
        period: float,
        fn: Callable[[], object],
        *,
        catch_up: str = "skip",
    ) -> Timer:
        """Call ``fn`` every ``period`` seconds until the timer is cancelled.

        The schedule is deadline-based: the first run is one ``period``
        after registration and every run adds exactly one ``period`` to
        ``next_run`` (see :class:`Timer`).  ``fn`` takes no arguments and
        decides for itself whether to invalidate the frame; the pump invokes
        it from :meth:`tick`.  ``catch_up`` selects the missed-deadline
        posture (``"skip"`` or ``"coalesce"``).
        """
        timer = Timer(period, fn, self.clock() + period, catch_up=catch_up)
        self._timers.append(timer)
        self._wake()
        return timer

    def animation(self, hz: float, draw: Callable[[], object]) -> Timer:
        """Call ``draw`` at ``hz`` frames per second, deadline-based.

        The convenience over :meth:`every` an animated host wants: one
        callback per frame, with the same cancellation handle and catch-up
        policy.  A non-positive rate raises ``ValueError``.
        """
        if hz <= 0:
            raise ValueError(f"animation rate must be positive, got {hz!r}")
        return self.every(1.0 / hz, draw)

    def invalidate(self) -> None:
        """Mark the frame dirty (the 2.0 name for :meth:`refresh`)."""
        self.refresh()

    def paint_now(self) -> None:
        """Paint one frame right now, bypassing the throttle (see :meth:`paint`)."""
        self.paint()

    async def read_event(self) -> Event | None:
        """Read the next event, or ``None``.

        A **pure read**: the event comes back exactly as the source
        reported it -- a wheel report, a page key and a button press are
        all the host's to route.  The driver runs no scroll or focus policy
        here (the default orchestration is
        :class:`~motui.app.application.App`'s; a host driving ``Runtime`` directly owns
        its loop).  The result is ``None`` when there is no key source,
        when the source reports EOF, and -- per the toolkit's non-live
        contract -- always on a non-live screen, even when a source is
        attached.

        Escape hatch: ``await runtime.keys.read()`` reads the raw source
        directly, bypassing the non-live guard.  A pending read returns
        ``None`` immediately when :meth:`exit` runs: the read task is
        cancelled and the source itself is closed by teardown.
        """
        if not self.screen.live:
            return None
        if self._terminal.input is None:
            return None
        read = self._terminal.read_event
        exit_event = self._exit_event
        if exit_event is None:
            self._exit_event = exit_event = asyncio.Event()
        while True:
            if self._stopped or exit_event.is_set():
                return None
            read_task = asyncio.ensure_future(read())
            exit_task = asyncio.ensure_future(exit_event.wait())
            try:
                done, _ = await asyncio.wait(
                    (read_task, exit_task), return_when=asyncio.FIRST_COMPLETED
                )
            except asyncio.CancelledError:
                read_task.cancel()
                exit_task.cancel()
                await asyncio.gather(read_task, exit_task, return_exceptions=True)
                raise
            if exit_task in done:
                read_task.cancel()
                await asyncio.gather(read_task, return_exceptions=True)
                return None
            exit_task.cancel()
            await asyncio.gather(exit_task, return_exceptions=True)
            return read_task.result()

    def exit(self) -> None:
        """End the session now: unblock reads, stop the pump, let teardown run.

        Safe from any task: :meth:`read_event` returns ``None`` immediately,
        the pump wakes and leaves, and the run's teardown closes an owned
        source and leaves the screen.
        """
        self._stopped = True
        if self._exit_event is None:
            self._exit_event = asyncio.Event()
        self._exit_event.set()
        self._wake()

    # -- pump -----------------------------------------------------------------

    def clock(self) -> float:
        """The driver's monotonic clock: the one seam time enters through.

        It answers ``_clock() + offset``: ``_clock`` is
        :func:`time.monotonic` unless a host replaces it, and the offset is
        the virtual time :meth:`advance` has added, so a replay script can
        move time without touching the system clock.  Timestamps (``every``
        schedules, toast expiries, double-click windows) read it, and a host
        or a test may also replace this method with its own reading.
        """
        return self._clock() + self._clock_offset

    def advance(self, dt: float) -> None:
        """Move the virtual clock by ``dt`` and run every deadline it crosses.

        The driver steps from due deadline to due deadline, running
        :meth:`tick` at each one -- timers fire exactly as they would have
        under a pump that never slept -- and lands on the target time with a
        final tick.  No real time is sampled between the steps and nothing
        sleeps, so a scripted interval replays deterministically.  A
        non-positive ``dt`` does nothing.
        """
        if dt <= 0:
            return
        target = self.clock() + dt
        while True:
            deadline = self._next_deadline()
            if deadline is None or deadline > target:
                break
            now = self.clock()
            if deadline > now:
                self._clock_offset += deadline - now
            self.tick(self.clock())
        now = self.clock()
        if target > now:
            self._clock_offset += target - now
        self.tick(self.clock())

    def _next_deadline(self) -> float | None:
        """The earliest scheduled deadline, ``None`` when no live timer exists."""
        deadlines = [
            timer.next_run for timer in self._timers if not timer.cancelled
        ]
        return min(deadlines) if deadlines else None

    def _paint_at(self, now: float) -> None:
        """Paint one frame and record ``now`` as the last flush time.

        Sample the screen size, retile the workspace to it (the pane area
        minus the docks' rows, the docks at their edges), compose the
        workspace's frame, run the frame's overlay pipeline over the
        composition (the selection highlight is overlay #1), and paint the
        diff.  A retile re-divides the recorded split tree instead of
        rebuilding the panes, so every pane keeps its viewport, its chrome
        registry and its scroll state, the frame keeps its overlays and its
        focus, and nothing has to be carried across.  A single-pane frame
        with no dock composes to its pane's own layout, so the row stream is
        the one the viewport laid out -- not a re-derivation of it.  A new
        width clears the selection (reflow), a new height does not.

        The sampling here is the driver's own: the retile and the reflow
        test both need the size *before* the composition runs, while
        :meth:`~motui.terminal.paint.Painter.paint` samples again for
        its full-repaint test, per the :class:`~motui.terminal.screen.Screen`
        protocol's "the painter calls it before every frame".  Neither
        sample can move to the other side without composing one frame at a
        stale size.
        """
        self.screen.refresh_size()
        width, height = self.screen.width, self.screen.height
        workspace = self.workspace
        workspace._retile()
        if width != workspace._layout_width:
            workspace._layout_width = width
            # reflow: the columns of one width address other glyphs (D8)
            workspace._set_selection(None, None)
        layout = workspace.frame.compose(width, height)
        layout = workspace.frame.apply_overlays(layout)
        self.painter.paint(layout.surface)
        self._last_paint = now
        self._dirty = False

    def _wake(self) -> None:
        """Wake the pump, from the loop thread or (safely) from another one."""
        event, loop = self._wake_event, self._wake_loop
        if event is None or loop is None:
            return  # no pump is waiting yet; the next tick sees the flags
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            event.set()
        elif not loop.is_closed():
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                pass  # the loop closed between the check and the call

    def _wake_up(self) -> asyncio.Event:
        """The pump's wake event, created lazily and bound to the running loop."""
        loop = asyncio.get_running_loop()
        if self._wake_event is None or self._wake_loop is not loop:
            self._wake_event = asyncio.Event()
            self._wake_loop = loop
        return self._wake_event

    def tick(self, now: float) -> float | None:
        """Advance the pump one step; return the seconds until the next wake.

        The pump's manual seam: due timers run first (they may invalidate the
        frame), then at most one frame is painted -- only when the document
        is dirty *and* the throttle has elapsed since the last flush.  Each
        due timer fires at most once and reschedules from its own deadline
        (see :class:`Timer`), so a late tick never shifts the phase.  The
        return value is the delay until the pump next needs to run, or
        ``None`` when nothing is pending and the pump should sleep until
        woken.
        """
        if self._timers:
            alive: list[Timer] = []
            for timer in self._timers:
                if timer.cancelled:
                    continue
                if now >= timer.next_run:
                    timer.fn()
                    if timer.cancelled:
                        continue
                    self._reschedule(timer, now)
                alive.append(timer)
            self._timers = alive
        if self._dirty and now - self._last_paint >= self.throttle:
            self._paint_at(now)
        wake_at: float | None = None
        if self._dirty:
            wake_at = self._last_paint + self.throttle
        for timer in self._timers:
            wake_at = timer.next_run if wake_at is None else min(wake_at, timer.next_run)
        if wake_at is None:
            return None
        return max(0.0, wake_at - now)

    @staticmethod
    def _reschedule(timer: Timer, now: float) -> None:
        """Move ``timer`` past ``now`` according to its catch-up posture.

        The deadline advances by whole periods in both postures.  ``skip``
        gives up on the missed ones and realigns to ``now + period`` as soon
        as the next deadline is still in the past; ``coalesce`` keeps
        stepping by periods until the deadline is in the future, so the
        schedule's phase survives a late tick.
        """
        timer.next_run += timer.period
        if timer.catch_up == "skip":
            if timer.next_run <= now:
                timer.next_run = now + timer.period
        else:
            while timer.next_run <= now:
                timer.next_run += timer.period

    async def _pump(self) -> None:
        """Repaint on the throttle and run periodic callbacks until stopped."""
        while not self._stopped:
            # Clear before ticking: a refresh() that lands during tick() sets
            # the event, and the wait below then returns instead of sleeping
            # through the change (the lost-wakeup this order fixes).
            event = self._wake_up()
            event.clear()
            delay = self.tick(self.clock())
            if self._stopped:
                break
            if delay is None:
                if self._dirty:
                    continue  # never leave a dirty frame waiting forever
                await event.wait()
            else:
                try:
                    await asyncio.wait_for(event.wait(), delay)
                except asyncio.TimeoutError:
                    pass

    # -- lifecycle ------------------------------------------------------------

    def _reset_run(self) -> None:
        """Reset per-run state, keeping timers registered before the run.

        A host builds its shell before it calls ``run_session`` -- the demo
        registers its animation beat there -- so ``every`` callbacks made
        before entering survive the reset and are rescheduled from this
        run's clock.  Only cancelled timers are dropped; a timer lasts
        until its handle is cancelled, across runs.
        """
        self._stopped = False
        self._exit_event = asyncio.Event()
        now = self.clock()
        self._timers = [timer for timer in self._timers if not timer.cancelled]
        for timer in self._timers:
            timer.next_run = now + timer.period
        self.workspace._reset()
        self._dirty = True

    def _enter_run(self) -> None:
        """Reset the run, attach an owned key source, enter and clear the diff base."""
        self._reset_run()
        if self.interactive and self.screen.live and self.keys is None:
            source = RawTerminalKeys(hover=self._hover)
            source.start()
            self.keys = source
            self._owned_source = source
            self._terminal.attach(source)
        if self.screen.live:
            self._terminal.enter()
        # Every run starts from a blank screen: the alternate screen starts
        # blank, and a non-live run still paints its final frame from scratch.
        self.painter.reset()

    async def _run(self, body: Callable[[], Awaitable[None]]) -> None:
        """Enter, pump, await ``body``, and tear down exactly once.

        The one lifecycle both public entries share: ``_enter_run`` resets the
        per-run state and enters the screen, the pump task starts, and
        ``body`` runs inside the bracket.  ``KeyboardInterrupt`` from the body
        is a session end (:meth:`exit`), any other ``BaseException`` is
        recorded and re-raised **after** teardown, and a pump error is
        re-raised only when the body finished cleanly -- teardown runs once,
        whatever path ended the session.
        """
        pump_task: asyncio.Task[None] | None = None
        body_error: BaseException | None = None
        try:
            try:
                self._enter_run()
                pump_task = asyncio.create_task(self._pump(), name="motui-pump")
                await body()
            except KeyboardInterrupt:
                self.exit()
            except BaseException as exc:  # noqa: BLE001 - re-raised after teardown
                body_error = exc
        finally:
            pump_error = await self._teardown(pump_task)
        if body_error is not None:
            raise body_error
        if pump_error is not None:
            raise pump_error

    async def run_session(self, body: Callable[["Runtime"], Awaitable[None]]) -> None:
        """Run ``body(self)`` inside a full-screen session.

        The body is an ordinary coroutine function -- the library never
        builds an event loop of its own, so the caller owns ``asyncio.run``
        (or any other driver).  ``enter``/``leave`` bracket the session on a
        live screen (an exception or :meth:`exit` still leaves), a non-live
        screen sees neither and stays silent for the whole run, and a
        non-live run ends by dumping the final screen as plain text -- on the
        exception path too, before the error is re-raised.  A
        ``KeyboardInterrupt`` raised by the body is treated as :meth:`exit`.

        Entering **resets the painter's diff base**: the alternate screen
        starts blank, so a host that painted before the session (the demo
        builds its shell, then runs it) would otherwise see the first frames
        diffed against rows that are no longer anywhere -- an empty screen
        until some row happens to change.
        """
        await self._run(lambda: body(self))

    async def run_async(self) -> None:
        """Run until :meth:`exit`: enter, pump, wait for the exit signal, teardown."""
        await self._run(lambda: self._exit_event.wait())

    def run(self) -> None:
        """The synchronous entry: own an event loop around :meth:`run_async`."""
        asyncio.run(self.run_async())

    async def _teardown(self, pump_task: asyncio.Task[None] | None) -> BaseException | None:
        """Stop the pump and the keyboard, bracket the screen, dump if piped.

        Returns the pump's exception, if any, so the run methods can re-raise
        it when the body itself finished cleanly.
        """
        self.exit()
        pump_error: BaseException | None = None
        if pump_task is not None:
            try:
                await pump_task
            except BaseException as exc:  # noqa: BLE001 - reported to the run method
                pump_error = exc
        # The pump's loop is history: a post-run refresh must not poke a
        # closed loop when a host detaches its last overlay after the session.
        self._wake_event = None
        self._wake_loop = None
        if self._owned_source is not None:
            self._owned_source.close()
            if self.keys is self._owned_source:
                self.keys = None  # the next run attaches a fresh source
            self._terminal.attach(None)
            self._owned_source = None
        # The final frame: painted rows before the live screen leaves, a
        # zero-write logical frame (the dump reads it) on a piped one.
        self._paint_at(self.clock())
        if self.screen.live:
            self._terminal.leave()
            self.screen.flush()
        else:
            self._dump_final_screen()
        return pump_error

    def _dump_final_screen(self) -> None:
        """Write the final screen as plain text (non-live runs only).

        A frame carries box characters the stream's codepage may not hold --
        a legacy-codepage Windows console, a pipe opened in the locale's
        encoding -- and a run that worked all the way to its last line must
        not fail on the way out.  Such a character degrades to the stream's
        own replacement instead; a host that wants the frames intact puts
        the stream in UTF-8 (the demo does).
        """
        lines = [row.text for row in self.painter.rows]
        while lines and not lines[-1].strip():
            lines.pop()  # trailing all-blank rows are not content
        if not lines:
            return
        text = "\n".join(lines) + "\n"
        try:
            self.screen.write(text)
        except UnicodeEncodeError:
            encoding = getattr(self.screen, "encoding", None) or "utf-8"
            self.screen.write(text.encode(encoding, "replace").decode(encoding))
        self.screen.flush()

    def __repr__(self) -> str:
        return (
            f"Runtime(terminal={self._terminal!r}, "
            f"blocks={len(self.workspace.document)}, "
            f"interactive={self.interactive})"
        )
