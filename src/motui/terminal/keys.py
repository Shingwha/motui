"""The key sources: RawTerminalKeys, the real terminal source.

A daemon reader thread feeds a queue that ``read()`` drains through an
executor, so the thread never touches asyncio; cooked-line fallback when
raw mode is impossible."""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import os
import queue
import select
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ..kernel.events import Event
from .decoder import KeyDecoder
from .win32 import (
    _FOCUS_EVENT,
    _KEY_EVENT,
    _MOUSE_EVENT,
    _WINDOW_BUFFER_SIZE_EVENT,
    _console_record_events,
    _console_record_fields,
    _InputRecord,
    _kernel32,
    windows_input_mode,
)

# ---------------------------------------------------------------------------
# Key sources
# ---------------------------------------------------------------------------


def _stdin_fd() -> int:
    """The stdin file descriptor; 0 when stdin has none (captured runs)."""
    try:
        return sys.stdin.fileno()
    except Exception:
        return 0


#: Console records pulled per batch read.  With VT input a whole escape
#: sequence arrives one byte per record, so a burst of key presses needs
#: many records.
_CONSOLE_BATCH = 32

#: How long the input must stay silent before a pending escape/CSI sequence
#: is settled (seconds).  One shared threshold for both reader paths: it is
#: long enough for a fast typist's split sequence, short enough that a lone
#: ESC key press still feels immediate.
_SETTLE_SECONDS = 0.050

#: The console record kinds that carry input (everything else is skipped).
_CONSOLE_INPUT_TYPES = (_KEY_EVENT, _MOUSE_EVENT, _FOCUS_EVENT, _WINDOW_BUFFER_SIZE_EVENT)


class RawTerminalKeys:
    """An event source reading a real terminal in near-raw mode.

    EOF is sticky, ``start()`` may follow ``close()``, and a partial escape
    sequence is settled after silence. ``hover`` enables button-free motion
    on the Windows record path."""

    def __init__(self, fd: int | None = None, *, hover: bool = False) -> None:
        self._fd = _stdin_fd() if fd is None else fd
        self._queue: queue.SimpleQueue[Event | None] = queue.SimpleQueue()
        self._decoder = KeyDecoder()
        self._hover = hover
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._started = False
        self._closed = False
        self._eof = False
        self._console = False  # Windows console-record path is active
        self._saved_attrs: list | None = None  # POSIX termios attributes
        self._saved_mode: tuple[int, int] | None = None  # Windows (handle, mode)
        self._cooked_fallback = False
        self._last_activity = time.monotonic()  # input-see clock for settle
        self._held_buttons = 0  # Windows: console mouse state for transitions
        self._wake_r: int | None = None  # POSIX self-pipe: close() wakes read()
        self._wake_w: int | None = None

    @property
    def cooked_fallback(self) -> bool:
        """Whether ``start()`` had to fall back to cooked line mode."""
        return self._cooked_fallback

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """Enter raw mode (or fall back) and launch the reader thread; a start
        while already running is a no-op."""
        if self._started:
            return
        self._started = True
        self._closed = False
        self._eof = False
        self._queue = queue.SimpleQueue()
        self._decoder = KeyDecoder()
        self._console = False
        self._saved_attrs = None
        self._saved_mode = None
        self._cooked_fallback = False
        self._held_buttons = 0
        self._last_activity = time.monotonic()
        if os.name == "nt":
            self._start_windows()
        else:
            self._start_posix()
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="motui-keys"
        )
        self._thread = threading.Thread(
            target=self._reader, name="motui-keys", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        """Stop the reader thread and restore the terminal mode; idempotent."""
        if self._closed:
            return
        self._closed = True
        self._started = False
        self._queue.put(None)  # wake every pending read()
        if self._wake_w is not None:
            with contextlib.suppress(OSError):
                os.write(self._wake_w, b"x")  # POSIX: wake the select()
        if os.name == "nt":
            self._restore_windows()
        else:
            self._restore_posix()
        if self._executor is not None:
            self._executor.shutdown(wait=False)

    async def read(self) -> Event | None:
        """The next event, or ``None`` at EOF / after ``close()``; EOF is sticky."""
        if self._executor is None or self._closed or self._eof:
            return None  # never started, closed, or the stream already ended
        loop = asyncio.get_running_loop()
        event = await loop.run_in_executor(self._executor, self._queue.get)
        if event is None:
            self._eof = True
            return None
        return event

    # -- platform setup -------------------------------------------------------

    def _start_posix(self) -> None:
        import termios
        import tty

        self._open_wake_pipe()
        try:
            self._saved_attrs = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
        except Exception:
            self._saved_attrs = None  # not a terminal: cooked fallback
            self._cooked_fallback = True

    def _open_wake_pipe(self) -> None:
        """The self-pipe :meth:`close` writes to so a blocked select returns."""
        try:
            self._wake_r, self._wake_w = os.pipe()
            os.set_blocking(self._wake_r, False)
            os.set_blocking(self._wake_w, False)
        except OSError:
            self._wake_r = self._wake_w = None

    def _start_windows(self) -> None:
        import msvcrt

        try:
            handle = msvcrt.get_osfhandle(self._fd)
            mode = ctypes.c_uint32()
            api = _kernel32()
            if not api.GetConsoleMode(handle, ctypes.byref(mode)):
                raise OSError("stdin is not a console handle")
            if not api.SetConsoleMode(handle, windows_input_mode(mode.value)):
                raise OSError("SetConsoleMode failed")
            self._saved_mode = (handle, mode.value)
            self._console = True
        except Exception:
            self._saved_mode = None  # pipe / no console: cooked fallback
            self._console = False
            self._cooked_fallback = True

    def _restore_posix(self) -> None:
        if self._saved_attrs is None:
            return
        import termios

        with contextlib.suppress(termios.error):
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved_attrs)

    def _restore_windows(self) -> None:
        if self._saved_mode is None:
            return
        handle, mode = self._saved_mode
        with contextlib.suppress(Exception):
            _kernel32().SetConsoleMode(handle, mode)

    # -- reader thread --------------------------------------------------------

    def _enqueue(self, events: list[Event]) -> None:
        """Queue events, dropping anything produced after close."""
        for event in events:
            if self._closed:
                return
            self._queue.put(event)

    def _settle_wait(self) -> float:
        """Seconds left in the settle window (0.0 once it has elapsed)."""
        return max(_SETTLE_SECONDS - (time.monotonic() - self._last_activity), 0.0)

    def _settle_due(self) -> bool:
        """Whether the input has been silent for the settle window."""
        return self._settle_wait() <= 0.0

    def _reader(self) -> None:
        """Daemon thread body: pump terminal input into the queue, flushing the
        decoder before the EOF sentinel."""
        try:
            if self._console:
                self._read_console_records()
            else:
                self._read_bytes()
        finally:
            # EOF: flush the decoder's pending paste/UTF-8/escape before the
            # sentinel, so no byte is lost when the stream ends.
            self._enqueue(self._decoder.finish())
            self._queue.put(None)  # EOF sentinel: wakes every pending read()

    def _read_console_records(self) -> None:
        """Windows: poll console records without blocking, feed the decoder and
        settle a pending sequence once the console has been silent long enough."""
        api = _kernel32()
        handle = self._saved_mode[0]
        records = (_InputRecord * _CONSOLE_BATCH)()
        count = ctypes.c_uint32()
        while not self._closed:
            if not api.PeekConsoleInputW(
                handle, records, _CONSOLE_BATCH, ctypes.byref(count)
            ):
                return  # console closed or peek error: EOF
            if count.value:
                self._last_activity = time.monotonic()
                if not api.ReadConsoleInputW(
                    handle, records, _CONSOLE_BATCH, ctypes.byref(count)
                ):
                    return  # console closed or read error: EOF
                if count.value == 0:
                    continue  # consumed elsewhere: re-poll
                for index in range(count.value):
                    if self._closed:
                        return
                    record = records[index]
                    if record.EventType not in _CONSOLE_INPUT_TYPES:
                        continue  # menu events and unknown records: not input
                    produced, self._held_buttons = _console_record_events(
                        _console_record_fields(record),
                        self._decoder,
                        self._held_buttons,
                        hover=self._hover,
                    )
                    self._enqueue(produced)
                continue
            # Nothing waiting: settle a pending sequence once the console has
            # been silent long enough, otherwise poll again shortly (close()
            # is noticed at the loop top, so it stays immediate).
            if self._decoder.pending() and self._settle_due():
                self._enqueue(self._decoder.settle())
            else:
                time.sleep(0.005)

    def _read_bytes(self) -> None:
        """POSIX and cooked paths: decode raw bytes; while a sequence is pending the
        read waits with a settle deadline instead of blocking forever."""
        while not self._closed:
            pending = self._decoder.pending()
            watch = [self._fd]
            if self._wake_r is not None:
                watch.append(self._wake_r)
            try:
                ready, _, _ = select.select(
                    watch, [], [], self._settle_wait() if pending else None
                )
            except (OSError, ValueError):
                ready = [self._fd]  # select refused this fd: blocking read
                if pending and self._settle_due():
                    self._enqueue(self._decoder.settle())
                    continue
            if self._wake_r is not None and self._wake_r in ready:
                return  # close() woke us
            if not ready:
                if pending and self._settle_due():
                    self._enqueue(self._decoder.settle())
                continue
            if self._fd not in ready:
                continue
            try:
                data = os.read(self._fd, 4096)
            except OSError:
                return
            if not data:
                return  # EOF: the reader's finally flushes the decoder
            self._last_activity = time.monotonic()
            self._enqueue(self._decoder.feed(data))
