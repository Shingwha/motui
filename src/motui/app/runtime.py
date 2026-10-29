"""The runtime: the session lifecycle, the pump, the clock and the painter.

It owns the terminal, the timers and the dirty flag; the document, frame
and panes live on :attr:`workspace`. A paint is one composition plus the
frame's overlays."""

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
    """One periodic callback on the driver's clock.

    ``next_run`` is an absolute deadline advanced by whole periods, so a late
    tick never shifts the phase; ``catch_up`` chooses skip or coalesce. The
    timer is its own cancellable handle."""

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

    ``terminal`` is the one configuration door (screen, input, clipboard).
    The workspace -- document, frame, panes, selection and docks -- is
    constructed here."""

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
        """The terminal endpoint this runtime enters, leaves and reads through."""
        return self._terminal

    # -- clipboard ---------------------------------------------------------------

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard (OSC 52); a non-live screen
        answers ``False`` without touching the stream."""
        return self._terminal.clipboard.copy(text)

    # -- protocol surface ---------------------------------------------------------

    def set_title(self, text: str) -> None:
        """Set the terminal window title (OSC 2); not gated on liveness, so a
        headless screen records it."""
        self.screen.write(set_window_title(text))
        self.screen.flush()

    def set_cursor_shape(self, shape: str) -> None:
        """Ask the terminal for a cursor shape (DECSCUSR); an unknown shape raises
        ``KeyError``."""
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
        """Call ``fn`` every ``period`` seconds from a deadline-based schedule;
        ``catch_up`` is ``skip`` or ``coalesce``."""
        timer = Timer(period, fn, self.clock() + period, catch_up=catch_up)
        self._timers.append(timer)
        self._wake()
        return timer

    def animation(self, hz: float, draw: Callable[[], object]) -> Timer:
        """Call ``draw`` at ``hz`` frames per second, deadline-based; a
        non-positive rate raises ``ValueError``."""
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

        A pure read with no scroll or focus policy. ``None`` on a non-live
        screen, with no source, at EOF, and when :meth:`exit` runs."""
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
        """End the session now: unblock reads, stop the pump and let teardown run."""
        self._stopped = True
        if self._exit_event is None:
            self._exit_event = asyncio.Event()
        self._exit_event.set()
        self._wake()

    # -- pump -----------------------------------------------------------------

    def clock(self) -> float:
        """The driver's monotonic clock -- the one seam time enters through;
        :meth:`advance` adds a virtual offset."""
        return self._clock() + self._clock_offset

    def advance(self, dt: float) -> None:
        """Move the virtual clock by ``dt``, running a tick at every deadline
        crossed, so a replay is deterministic and never sleeps."""
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
        """Paint one frame: sample the size, retile, compose, run the overlays and
        paint the diff.

        The retile re-divides in place, so panes keep their viewports and scroll
        state. A new width clears the selection (reflow); a new height does not."""
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
        """Wake the pump, from the loop thread or safely from another one."""
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
        """Advance the pump one step; return seconds until the next wake, or
        ``None``.

        Due timers run first, then at most one frame when dirty and the throttle
        has elapsed. Each due timer fires once from its own deadline."""
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
        """Move ``timer`` past ``now`` by whole periods according to its catch-up
        posture, preserving the phase for ``coalesce``."""
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
        """Reset per-run state, keeping timers registered before the run."""
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
        """Enter, pump, await ``body`` and tear down once, re-raising a body error
        after teardown."""
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
        """Run ``body(self)`` inside a full-screen session; entering resets the
        painter's diff base because the alternate screen starts blank."""
        await self._run(lambda: body(self))

    async def run_async(self) -> None:
        """Run until :meth:`exit`: enter, pump, wait for the exit signal, teardown."""
        await self._run(lambda: self._exit_event.wait())

    def run(self) -> None:
        """The synchronous entry: own an event loop around :meth:`run_async`; a
        Ctrl+C interrupt is a quit, not a crash."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass

    async def _teardown(self, pump_task: asyncio.Task[None] | None) -> BaseException | None:
        """Stop the pump and keyboard, bracket the screen and dump the final screen
        when piped; returns any pump error."""
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
        """Write the final screen as text for non-live runs, degrading unencodable
        glyphs to the stream's replacement instead of failing on exit."""
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
