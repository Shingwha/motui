"""The key sources: :class:`ScriptedKeys` and :class:`RawTerminalKeys`.

``ScriptedKeys`` (in :mod:`motui.core.events`, zero dependencies) replays
a fixed event list for tests and demos; ``RawTerminalKeys`` reads a real
terminal -- POSIX ``termios`` raw mode or the Windows console-record path (see
:mod:`motui.keys.console`) -- with a daemon reader thread feeding an
executor-backed queue, so ``read()`` stays async without the thread touching
asyncio, and a cooked-line fallback when the terminal cannot be switched to
raw mode.
"""

from __future__ import annotations

import asyncio
import ctypes
import os
import queue
import select
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ..core.events import Key, Paste
from .console import (
    _console_record_events,
    _console_record_fields,
    _InputRecord,
    _KEY_EVENT,
    _kernel32,
    _MOUSE_EVENT,
    windows_input_mode,
)
from .decoder import KeyDecoder

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


class RawTerminalKeys:
    """A key source reading a real terminal in (near) raw mode.

    ``start()`` switches the terminal to raw-ish mode -- POSIX
    ``tty.setraw``, or on Windows a console mode with line input and echo
    cleared and VT input enabled -- and launches a daemon reader thread that
    decodes input and queues events.  ``read()`` (async) drains that queue
    through a single-thread executor, so the reader thread never touches an
    asyncio object.  ``close()`` stops the reader and restores the original
    terminal mode; it is idempotent and must eventually be called.

    When the terminal cannot be switched to raw mode -- a pipe, a redirected
    stream, no console -- the source falls back to cooked line mode
    (:attr:`cooked_fallback` is ``True``): whole lines arrive from the OS and
    are delivered character by character plus a trailing ``enter``.

    A partial escape/CSI sequence left pending by the decoder is settled
    after ``_SETTLE_SECONDS`` of input silence, so a lone ESC key press is
    delivered as the escape key rather than swallowed or deferred forever.

    ``hover`` feeds the Windows console-record path: the record path has no
    DECSET tracking of its own (the screen writes those bytes on both
    platforms), so with ``hover`` set a bare pointer move -- the VT path's
    1003 motion -- becomes a button-free motion report, and with the
    default off it stays dropped, exactly as under the default 1002.
    """

    def __init__(self, fd: int | None = None, *, hover: bool = False) -> None:
        self._fd = _stdin_fd() if fd is None else fd
        self._queue: "queue.SimpleQueue[Key | Paste | None]" = queue.SimpleQueue()
        self._decoder = KeyDecoder()
        self._hover = hover
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._closed = False
        self._console = False  # Windows console-record path is active
        self._saved_attrs: list | None = None  # POSIX termios attributes
        self._saved_mode: tuple[int, int] | None = None  # Windows (handle, mode)
        self._cooked_fallback = False
        self._last_activity = time.monotonic()  # input-see clock for settle
        self._held_buttons = 0  # Windows: console mouse state for transitions

    @property
    def cooked_fallback(self) -> bool:
        """Whether ``start()`` had to fall back to cooked line mode."""
        return self._cooked_fallback

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """Enter raw mode (or fall back) and launch the reader thread."""
        if self._thread is not None or self._closed:
            return
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
        """Stop the reader thread and restore the terminal mode."""
        if self._closed:
            return
        self._closed = True
        self._queue.put(None)  # wake every pending read()
        if os.name == "nt":
            self._restore_windows()
        else:
            self._restore_posix()
        if self._executor is not None:
            self._executor.shutdown(wait=False)

    async def read(self) -> Key | Paste | None:
        """The next event, or ``None`` at EOF / after ``close()``."""
        if self._executor is None or self._closed:
            return None  # never started, or closed: nothing will ever arrive
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._queue.get)

    # -- platform setup -------------------------------------------------------

    def _start_posix(self) -> None:
        import termios
        import tty

        try:
            self._saved_attrs = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
        except Exception:
            self._saved_attrs = None  # not a terminal: cooked fallback
            self._cooked_fallback = True

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

        try:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved_attrs)
        except termios.error:
            pass  # the fd went away; nothing to restore

    def _restore_windows(self) -> None:
        if self._saved_mode is None:
            return
        handle, mode = self._saved_mode
        try:
            _kernel32().SetConsoleMode(handle, mode)
        except Exception:
            pass  # the console went away; nothing to restore

    # -- reader thread --------------------------------------------------------

    def _enqueue(self, events: list[Key | Paste]) -> None:
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
        """Daemon thread body: pump terminal input into the queue."""
        try:
            if self._console:
                self._read_console_records()
            else:
                self._read_bytes()
        finally:
            self._queue.put(None)  # EOF sentinel: wakes every pending read()

    def _read_console_records(self) -> None:
        """Windows: poll console records, feed the decoder, settle on silence.

        ``PeekConsoleInputW`` probes for records without blocking: a
        blocking ``ReadConsoleInputW`` would hold the reader hostage
        mid-sequence, so a lone ESC could never be settled.  Available
        records are then pulled in one batch -- key records delivered as VT
        bytes to the decoder, mouse records synthesized into SGR-1006
        reports by the console mappers (see :mod:`motui.keys.console`)
        -- and a pending sequence is settled once the console has been
        silent for the settle window.
        """
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
                    if record.EventType not in (_KEY_EVENT, _MOUSE_EVENT):
                        continue  # resize, focus, menu: carry no input
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
        """POSIX raw mode and every cooked fallback: decode raw bytes.

        While the decoder holds a pending escape/CSI sequence the read waits
        with a deadline instead of blocking forever: ``select`` reports the
        fd readable, or the settle window expires and the pending sequence
        is settled.  Outside a pending state the read blocks as usual.
        ``select`` supports sockets only on Windows, so where it refuses the
        fd the blocking read stands (a cooked line arrives whole, and a
        pending tail is still backstopped at EOF/close).  EOF settles the
        decoder so a trailing ESC keeps surfacing exactly as it did when
        feeds resolved sequences at their boundary.
        """
        while not self._closed:
            if self._decoder.pending():
                try:
                    ready, _, _ = select.select([self._fd], [], [], self._settle_wait())
                except OSError:
                    ready = [self._fd]  # select refused this fd: blocking read
                if not ready:
                    if self._settle_due():
                        self._enqueue(self._decoder.settle())
                    continue
            try:
                data = os.read(self._fd, 4096)
            except OSError:
                return
            if not data:
                self._enqueue(self._decoder.settle())
                return  # EOF: the pending sequence can never complete
            self._last_activity = time.monotonic()
            self._enqueue(self._decoder.feed(data))
