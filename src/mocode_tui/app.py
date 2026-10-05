"""The TUI driver: full-screen lifecycle, document facade, pump, and dump.

:class:`TUI` ties the kernel together -- a
:class:`~mocode_tui.core.block.Document`, the
:class:`~mocode_tui.core.viewport.Viewport` over it, a
:class:`~mocode_tui.core.painter.Painter` and a
:class:`~mocode_tui.core.screen.Screen` -- and adds the runtime behaviour a
full-screen application needs:

* a **document facade** (``add``/``get``/``remove``/``print``) where every
  mutation invalidates the frame;
* **scroll facades** and the ``scroll_keys`` table -- the page keys and
  the mouse wheel intercepted into viewport scrolling in
  :meth:`TUI.read_key`;
* a **mouse hit test** (:meth:`TUI.hit_test`) that resolves a report's
  coordinates to the block and cell under them -- the host dispatches the
  click, never the driver;
* one optional **document-space selection** (:attr:`TUI.selection` /
  :meth:`TUI.set_selection`) overlaid onto the laid-out frame between layout
  and paint, so the highlight follows its text through scrolls (D1-D2);
* a **pump** (``_tick``/``_clock``/``_wake_up``/``_pump``) that repaints on a
  throttle and runs cancellable periodic callbacks, with the clock as a seam
  tests can inject -- the library itself never builds an event loop, never
  sleeps, and never touches a sink outside the painter;
* :meth:`TUI.run`, which brackets ``enter``/``leave`` around the body (even
  on exceptions and ``stop()``), stays completely silent on a non-live
  screen, and dumps the final screen as plain text when piped.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from .core.block import Block, Component, Document
from .core.events import Key, KeySource, Paste
from .core.lines import Line
from .core.painter import Painter
from .core.screen import Screen, TerminalScreen
from .core.selection import Selection, highlight
from .core.style import MUTED
from .core.text import Text
from .core.viewport import Viewport
from .keys import RawTerminalKeys

__all__ = ["EveryHandle", "Hit", "TUI"]


class EveryHandle:
    """Cancellable handle returned by :meth:`TUI.every`."""

    __slots__ = ("_cancelled",)

    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def cancel(self) -> None:
        """Stop future invocations (a callback already running finishes)."""
        self._cancelled = True

    def __repr__(self) -> str:
        return f"EveryHandle(cancelled={self._cancelled})"


@dataclass
class _Every:
    """One periodic callback: period, next due time, and its handle."""

    period: float
    next_run: float
    fn: Callable[[], object]
    handle: EveryHandle


def _stdin_isatty() -> bool:
    """Whether stdin is a TTY right now (never raises)."""
    try:
        stream = sys.stdin
        return stream is not None and bool(stream.isatty())
    except Exception:
        return False


@dataclass(frozen=True)
class Hit:
    """One hit-test result: the block under the cell, and the cell in it.

    ``row``/``col`` are 0-based *within the block's own rows*; ``col`` is the
    screen column mapped into ``[0, width-1]``.
    """

    block: Block
    row: int
    col: int


class TUI:
    """A full-screen application driver.

    ``screen`` defaults to a :class:`~mocode_tui.core.screen.TerminalScreen`
    (pass ``mouse=False`` to leave mouse tracking off), ``keys`` to no
    source at all (``read_key`` then returns ``None``).
    :attr:`scroll_keys` is the public table :meth:`read_key` intercepts
    on -- event name to signed row count, negative scrolling up -- copied
    from ``_DEFAULT_SCROLL_KEYS`` into each instance; a host may rebind a
    count or ``del`` an entry to hand that event back (``del
    tui.scroll_keys["wheel_up"]``).  ``mouse`` applies only to the default
    screen: a custom ``screen`` brings its own tracking settings.
    ``interactive`` overrides the derived value; when left ``None`` it is
    ``screen.live and sys.stdin.isatty()``.  An interactive live session
    without an explicit key source gets a :class:`RawTerminalKeys` attached
    (and closed) by :meth:`run`; an explicit ``keys=`` source is always used
    as given.
    """

    #: What :meth:`read_key` scrolls on: event name to signed row count
    #: (negative scrolls up).  Each instance copies it into its public
    #: ``scroll_keys`` attribute, which hosts may edit.
    _DEFAULT_SCROLL_KEYS = {
        "page_up": -1,
        "page_down": 1,
        "wheel_up": -3,
        "wheel_down": 3,
    }

    def __init__(
        self,
        *,
        screen: Screen | None = None,
        keys: KeySource | None = None,
        throttle: float = 0.030,
        interactive: bool | None = None,
        mouse: bool = True,
    ) -> None:
        self.screen = screen if screen is not None else TerminalScreen(mouse=mouse)
        self.document = Document()
        self.viewport = Viewport(self.document)
        self.painter = Painter(self.screen)
        self.keys = keys
        self.throttle = throttle
        self.scroll_keys = dict(self._DEFAULT_SCROLL_KEYS)
        self.interactive = bool(
            self.screen.live and _stdin_isatty() if interactive is None else interactive
        )
        self._dirty = True
        self._stopped = False
        self._last_paint = float("-inf")
        self._selection: Selection | None = None
        self._layout_width: int | None = None
        self._every: list[_Every] = []
        self._wake_event: asyncio.Event | None = None
        self._wake_loop: asyncio.AbstractEventLoop | None = None
        self._owns_keys = False

    # -- document facade ------------------------------------------------------

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        pin: str | None = None,
    ) -> Block:
        """Append a block and invalidate the frame.

        ``pin`` forwards to :meth:`~mocode_tui.core.block.Document.add`:
        ``"top"``/``"bottom"`` place the block in the matching fixed
        region, ``None`` (the default) leaves it in the scrollable body.
        """
        block = self.document.add(component, id=id, pin=pin)
        self.invalidate()
        return block

    def get(self, id: str) -> Block:
        """The block with ``id`` (KeyError when missing)."""
        return self.document.get(id)

    def remove(self, id: str) -> Block:
        """Detach the block with ``id`` and invalidate the frame."""
        block = self.document.remove(id)
        self.invalidate()
        return block

    def print(self, text: str) -> Block:
        """Append a system block: external output becomes document content.

        The text is added as a muted :class:`~mocode_tui.core.text.Text`
        block, so a full-screen application never writes to stdout behind the
        painter's back.
        """
        return self.add(Text(text, style=MUTED))

    # -- scroll facade --------------------------------------------------------

    def scroll_up(self, n: int = 1) -> None:
        """Scroll the viewport ``n`` rows toward the top."""
        self.viewport.scroll_up(n)
        self.invalidate()

    def scroll_down(self, n: int = 1) -> None:
        """Scroll the viewport ``n`` rows toward the bottom."""
        self.viewport.scroll_down(n)
        self.invalidate()

    def scroll_to_bottom(self) -> None:
        """Re-attach the viewport to the bottom of the document."""
        self.viewport.scroll_to_bottom()
        self.invalidate()

    # -- frames ---------------------------------------------------------------

    def invalidate(self) -> None:
        """Mark the frame dirty; the pump repaints once the throttle allows."""
        self._dirty = True
        self._wake()

    def paint(self) -> None:
        """Paint one frame right now, bypassing the throttle."""
        self._paint_at(self._clock())

    @property
    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows."""
        return self.painter.rows

    @property
    def selection(self) -> Selection | None:
        """The document-space selection overlay, ``None`` when there is none.

        The read half of the driver's selection surface (D3): the value is
        the kernel's :class:`~mocode_tui.core.selection.Selection`, written
        here whole by :meth:`set_selection` -- the driver stores it and owns
        no anchor or head arithmetic of its own (that is gesture policy).
        """
        return self._selection

    def set_selection(self, selection: Selection | None) -> None:
        """Replace the selection and repaint; ``None`` clears it.

        The one write on that surface: the stored overlay is applied by
        :func:`~mocode_tui.core.selection.highlight` between layout and
        paint (D2), so the next frame -- and everything that reads the
        presented frame, from ``tui.rows`` to headless assertions on the
        painted rows -- shows the marked rows.  Because the selection lives
        in document space (D1), scrolling moves the text under a stationary
        range and leaves the highlight exactly where it was set; a width
        change (reflow) clears it instead, since the columns of one width
        address different glyphs at another (D8).
        """
        self._selection = selection
        self.invalidate()

    def every(self, seconds: float, fn: Callable[[], object]) -> EveryHandle:
        """Call ``fn`` every ``seconds`` until the returned handle is cancelled.

        ``fn`` takes no arguments and decides for itself whether to
        invalidate the frame; the pump invokes it from ``_tick``.
        """
        handle = EveryHandle()
        self._every.append(
            _Every(period=seconds, next_run=self._clock() + seconds, fn=fn, handle=handle)
        )
        self._wake()
        return handle

    async def read_key(self) -> Key | Paste | None:
        """Read the next key, with the scroll keys bound to scrolling.

        An event whose name is in :attr:`scroll_keys` (by default
        ``page_up``/``page_down``/``wheel_up``/``wheel_down``) is
        intercepted: it scrolls the viewport (and invalidates the frame)
        by the table's row count -- negative up -- and the read continues,
        so the caller never sees it.  Every other key and every
        :class:`~mocode_tui.core.events.Paste` is returned untouched, a
        :class:`~mocode_tui.core.events.MouseEvent` whose binding was deleted
        included.  The result is ``None`` when there is no key source,
        when the source reports EOF, and -- per the toolkit's non-live
        contract -- always on a non-live screen, even when a source is
        attached.

        Escape hatch: ``await tui.keys.read()`` reads the raw source
        directly, bypassing both the scroll-key interception and the
        non-live guard.
        """
        if not self.screen.live:
            return None
        source = self.keys
        if source is None:
            return None
        while True:
            event = await source.read()
            if event is None:
                return None
            if isinstance(event, Key):
                rows = self.scroll_keys.get(event.name)
                if rows is not None:
                    if rows < 0:
                        self.scroll_up(-rows)
                    else:
                        self.scroll_down(rows)
                    continue
            return event

    def stop(self) -> None:
        """Ask :meth:`run` to finish: the pump exits and the session ends."""
        self._stopped = True
        self._wake()

    # -- mouse hit test ------------------------------------------------------------

    def hit_test(self, x: int, y: int) -> Hit | None:
        """Resolve a 0-based terminal cell to a block and a cell inside it.

        ``x``/``y`` are 0-based, exactly as a
        :class:`~mocode_tui.core.events.MouseEvent` reports them (the decoder
        subtracts 1 from the terminal's 1-based report fields), so an event's
        own ``x``/``y`` go straight in.  The result's ``row``/``col`` are
        0-based within the block's own rows.  A row no block owns (the
        blank fill below short content), a cell outside the last layout, and
        a block removed since that layout all resolve to ``None``.

        The driver never dispatches clicks itself: the host reads the
        :class:`~mocode_tui.core.events.MouseEvent` from :meth:`read_key`
        (button presses are not in :attr:`scroll_keys`), resolves it here, and
        calls the component itself -- e.g. a
        :class:`~mocode_tui.widgets.choice.Select` takes the block-internal
        row::

            event = await tui.read_key()
            if isinstance(event, MouseEvent):
                hit = tui.hit_test(event.x, event.y)
                if hit is not None:
                    hit.block.component.click(hit.row)  # for a Select
        """
        row = y  # every toolkit cell index is 0-based
        # The driver owns the resident viewport (the one holding scroll
        # state); its ownership table is rebuilt by every layout.
        table = self.viewport.row_blocks
        if not 0 <= row < len(table):
            return None  # outside the screen of the last layout
        entry = table[row]
        if entry is None:
            return None  # blank fill: no block owns this row
        try:
            block = self.document.get(entry[0])
        except KeyError:
            return None  # removed since the last layout
        col = max(0, min(x, self.screen.width - 1))
        return Hit(block, entry[1], col)

    # -- pump -----------------------------------------------------------------

    def _clock(self) -> float:
        """Monotonic clock seam; tests monkeypatch this to drive time."""
        return time.monotonic()

    def _paint_at(self, now: float) -> None:
        """Paint one frame and record ``now`` as the last flush time."""
        self.screen.refresh_size()
        if self.screen.width != self._layout_width:
            self._layout_width = self.screen.width
            self._selection = None  # reflow: columns no longer address the same glyphs (D8)
        layout = self.viewport.layout(self.screen.width, self.screen.height)
        layout = highlight(layout, self._selection)
        self.painter.paint(layout)
        self._last_paint = now
        self._dirty = False

    def _wake(self) -> None:
        """Wake the pump, from the loop thread or (safely) from another one."""
        event, loop = self._wake_event, self._wake_loop
        if event is None or loop is None:
            return  # no pump is waiting yet; the next _tick sees the flags
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            event.set()
        else:
            loop.call_soon_threadsafe(event.set)

    def _wake_up(self) -> asyncio.Event:
        """The pump's wake event, created lazily and bound to the running loop."""
        loop = asyncio.get_running_loop()
        if self._wake_event is None or self._wake_loop is not loop:
            self._wake_event = asyncio.Event()
            self._wake_loop = loop
        return self._wake_event

    def _tick(self, now: float) -> float | None:
        """Advance the pump one step; return the seconds until the next wake.

        Due ``every`` callbacks run first (they may invalidate the frame),
        then at most one frame is painted -- only when the document is dirty
        *and* the throttle has elapsed since the last flush.  The return
        value is the delay until the pump next needs to run, or ``None`` when
        nothing is pending and the pump should sleep until woken.
        """
        if self._every:
            alive: list[_Every] = []
            for entry in self._every:
                if entry.handle.cancelled:
                    continue
                if entry.next_run <= now:
                    entry.fn()
                    if entry.handle.cancelled:
                        continue
                    entry.next_run = now + entry.period
                alive.append(entry)
            self._every = alive
        if self._dirty and now - self._last_paint >= self.throttle:
            self._paint_at(now)
        wake_at: float | None = None
        if self._dirty:
            wake_at = self._last_paint + self.throttle
        for entry in self._every:
            wake_at = entry.next_run if wake_at is None else min(wake_at, entry.next_run)
        if wake_at is None:
            return None
        return max(0.0, wake_at - now)

    async def _pump(self) -> None:
        """Repaint on the throttle and run periodic callbacks until stopped."""
        while not self._stopped:
            delay = self._tick(self._clock())
            if self._stopped:
                break
            event = self._wake_up()
            event.clear()
            if delay is None:
                await event.wait()
            else:
                try:
                    await asyncio.wait_for(event.wait(), delay)
                except asyncio.TimeoutError:
                    pass

    # -- lifecycle ------------------------------------------------------------

    async def run(self, body: Callable[["TUI"], object]) -> None:
        """Run ``body(self)`` inside a full-screen session.

        The body is an ordinary coroutine function -- the library never
        builds an event loop of its own, so the caller owns ``asyncio.run``
        (or any other driver).  ``enter``/``leave`` bracket the session on a
        live screen (an exception or :meth:`stop` still leaves), a non-live
        screen sees neither and stays silent for the whole run, and a
        non-live run ends by dumping the final screen as plain text -- on the
        exception path too, before the error is re-raised.  A
        ``KeyboardInterrupt`` raised by the body is treated as :meth:`stop`.
        """
        self._stopped = False
        pump_task: asyncio.Task[None] | None = None
        body_error: BaseException | None = None
        try:
            try:
                if self.interactive and self.screen.live and self.keys is None:
                    source = RawTerminalKeys()
                    source.start()
                    self.keys = source
                    self._owns_keys = True
                if self.screen.live:
                    self.screen.enter()
                self._dirty = True
                pump_task = asyncio.create_task(self._pump(), name="mocode-tui-pump")
                await body(self)
            except KeyboardInterrupt:
                self.stop()
            except BaseException as exc:  # noqa: BLE001 - re-raised after teardown
                body_error = exc
        finally:
            pump_error = await self._teardown(pump_task)
        if body_error is not None:
            raise body_error
        if pump_error is not None:
            raise pump_error

    async def _teardown(self, pump_task: asyncio.Task[None] | None) -> BaseException | None:
        """Stop the pump and the keyboard, bracket the screen, dump if piped.

        Returns the pump's exception, if any, so :meth:`run` can re-raise it
        when the body itself finished cleanly.
        """
        self.stop()
        pump_error: BaseException | None = None
        if pump_task is not None:
            try:
                await pump_task
            except BaseException as exc:  # noqa: BLE001 - reported to run()
                pump_error = exc
        if self._owns_keys and self.keys is not None:
            self.keys.close()
            self._owns_keys = False
        if self.screen.live:
            self._paint_at(self._clock())  # final frame, painted before leave
            self.screen.leave()
            self.screen.flush()
        else:
            self._paint_at(self._clock())  # logical rows only: zero writes
            self._dump_final_screen()
        return pump_error

    def _dump_final_screen(self) -> None:
        """Write the final screen as plain text (non-live runs only)."""
        lines = [row.text for row in self.painter.rows]
        while lines and not lines[-1].strip():
            lines.pop()  # trailing all-blank rows are not content
        if not lines:
            return
        self.screen.write("\n".join(lines) + "\n")
        self.screen.flush()

    def __repr__(self) -> str:
        return (
            f"TUI(screen={self.screen!r}, blocks={len(self.document)}, "
            f"interactive={self.interactive})"
        )
