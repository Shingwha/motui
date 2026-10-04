"""Keyboard events: the event model, the byte decoder, and the key sources.

Three layers live here:

* the **event model** -- :class:`Key` (a routable name plus the printable
  character, if any) and :class:`Paste` (a bracketed-paste payload);
* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (incremental
  UTF-8 and escape sequences assembled across feeds, control names, CSI
  navigation keys, bracketed paste);
* the **sources** -- :class:`ScriptedKeys` for tests and :class:`RawTerminalKeys`
  for a real terminal (POSIX ``termios`` raw mode or the Windows console
  record API, with a cooked-line fallback).

Nothing in this module builds an event loop, touches a screen, or writes to a
sink: decoding is synchronous and total, and sources only ever hand events to
their caller.
"""

from __future__ import annotations

import asyncio
import codecs
import ctypes
import os
import queue
import sys
import threading
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["Key", "KeyDecoder", "KeySource", "Paste", "RawTerminalKeys", "ScriptedKeys"]


@dataclass(frozen=True)
class Key:
    """One key press.

    ``name`` is the routing identity: a printable character's own text
    (``"a"``, ``"中"``), a control name (``"enter"``, ``"tab"``,
    ``"backspace"``, ``"escape"``, ``"space"``, ``"up"``, ``"page_up"``,
    ``"c-c"``, ...).  ``char`` is the printable character the key produced,
    empty for keys that produce no character.
    """

    name: str
    char: str = ""


@dataclass(frozen=True)
class Paste:
    """A bracketed-paste payload: literal text, never re-interpreted."""

    text: str


@runtime_checkable
class KeySource(Protocol):
    """Anything that can hand out key events: ``async read() -> event | None``.

    ``None`` means end of stream (EOF): a source that is exhausted, a closed
    terminal, or a source that was never started.
    """

    async def read(self) -> "Key | Paste | None":
        ...


# ---------------------------------------------------------------------------
# KeyDecoder
# ---------------------------------------------------------------------------

#: Bracketed paste start/end markers (CSI 200~ / 201~).
_PASTE_START = "\x1b[200~"
_PASTE_END = "\x1b[201~"

#: CSI final bytes that map to navigation keys (parameters, e.g. the modifier
#: fields of ``ESC [ 1;5 A``, are accepted and ignored -- the event model has
#: no modifiers, and the base key is the useful information).
_FINAL_KEYS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
}

#: CSI ``~`` family, keyed by the first parameter.
_TILDE_KEYS = {
    1: "home",
    7: "home",
    3: "delete",
    4: "end",
    8: "end",
    5: "page_up",
    6: "page_down",
}

#: First parameter that opens/closes a bracketed paste.
_PASTE_START_CODE = 200
_PASTE_END_CODE = 201


def _char_key(ch: str) -> Key | None:
    """Map a single decoded character to a key, or ``None`` to drop it.

    C0/C1 controls that carry no meaning in the event model (NUL, the four
    C1 separators, ...) are dropped: a lost key beats a crash.  Everything
    else -- ASCII printables and any non-ASCII code point, wide characters
    included -- is a key named after itself.
    """
    code = ord(ch)
    if ch in ("\r", "\n"):
        return Key("enter")
    if ch == "\t":
        return Key("tab")
    if code == 0x7F:
        return Key("backspace")
    if 0x01 <= code <= 0x1A:  # Ctrl-A .. Ctrl-Z
        return Key(f"c-{chr(ord('a') + code - 1)}")
    if code == 0x20:
        return Key("space", " ")
    if code < 0x20 or 0x7F <= code <= 0x9F:
        return None
    return Key(ch, ch)


class KeyDecoder:
    """Turns a raw byte stream into :class:`Key` / :class:`Paste` events.

    The decoder is incremental over ``feed`` calls: the stream may be split
    anywhere -- one byte per call is fine -- and escape state is carried
    across feeds rather than resolved at every boundary:

    * a ``feed`` ending inside ``ESC`` or ``ESC [ ...`` leaves the partial
      sequence pending (see :meth:`pending`); the next feed's bytes continue
      assembling it (``feed(b"\\x1b")`` then ``feed(b"[A")`` yields ``up``);
    * an ``ESC`` followed by another ``ESC`` resolves immediately to one
      escape key and restarts;
    * an ``ESC`` followed by any non-``[`` byte, and a ``CSI`` aborted by a
      byte outside the parameter/final ranges, resolve as soon as the
      disambiguating byte arrives: *escape* followed by the collected
      characters re-read literally (the ``[`` introducer is consumed);
    * a complete but unrecognized sequence (unknown final byte, unknown
      ``~`` parameter) is dropped;
    * a *pending* sequence is adjudicated by :meth:`settle` after a silence
      period: a bare ``ESC`` becomes the *escape* key, a pending ``CSI``
      degrades to *escape* plus its parameters re-read literally.  The
      caller owns that deadline (see ``RawTerminalKeys``);
    * paste aggregation is different: it spans any number of feeds until
      the end marker arrives.

    Nothing raises: unknown input is dropped or degraded, never fatal.
    """

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._paste: list[str] | None = None  # accumulator while pasting
        self._esc: str | None = None  # pending "escape" / "csi" state
        self._csi_params: list[str] = []  # collected while in "csi"

    # -- public API ----------------------------------------------------------

    def feed(self, data: bytes) -> list[Key | Paste]:
        """Decode ``data`` (possibly a partial UTF-8 sequence) into events.

        Bytes continue any pending escape/CSI sequence; state left pending
        at the end of this feed stays pending for the next one.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"feed() takes bytes, got {type(data).__name__}")
        text = self._utf8.decode(bytes(data))
        return self._emit(text)

    def pending(self) -> bool:
        """Whether an escape/CSI sequence is still being assembled.

        A paste in progress is never pending -- its payload is simply
        text until the end marker arrives.
        """
        return self._esc is not None

    def settle(self) -> list[Key | Paste]:
        """Adjudicate a pending escape/CSI sequence after a silence period.

        A pending bare ``ESC`` becomes the *escape* key; a pending ``CSI``
        degrades to *escape* followed by its collected parameter
        characters re-read literally.  Pastes are untouched.
        """
        events: list[Key | Paste] = []
        if self._esc == "escape":
            events.append(Key("escape"))
            self._esc = None
        elif self._esc == "csi":
            events.extend(self._degrade_csi())
        return events

    def flush(self) -> list[Key | Paste]:
        """Finish the stream: settle, flush pending UTF-8, close any paste.

        A truncated UTF-8 sequence surfaces as U+FFFD; an unclosed bracketed
        paste is delivered verbatim as one final :class:`Paste`.
        """
        events = self.settle()
        events.extend(self._emit(self._utf8.decode(b"", final=True)))
        if self._paste is not None:
            events.append(Paste("".join(self._paste)))
            self._paste = None
        return events

    # -- internals -----------------------------------------------------------

    def _emit(self, text: str) -> list[Key | Paste]:
        """Scan decoded ``text`` left to right, emitting events."""
        events: list[Key | Paste] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if self._paste is not None:
                end = text.find(_PASTE_END, i)
                if end < 0:
                    self._paste.append(text[i:])
                    break  # wait for the end marker in a later feed
                self._paste.append(text[i:end])
                events.append(Paste("".join(self._paste)))
                self._paste = None
                i = end + len(_PASTE_END)
                continue
            if self._esc is not None:
                i = self._advance_escape(text, i, events)
                continue
            if ch == "\x1b":
                self._esc = "escape"  # wait for the next byte to disambiguate
                i += 1
                continue
            key = _char_key(ch)
            if key is not None:
                events.append(key)
            i += 1
        return events

    def _advance_escape(self, text: str, i: int, events: list[Key | Paste]) -> int:
        """Continue the pending escape/CSI sequence with ``text[i]``.

        Returns the index to continue scanning from.  Every path either
        completes the sequence, resolves it outright, or leaves it pending
        for a later feed -- resolution never happens merely because a feed
        ended.
        """
        ch = text[i]
        if self._esc == "escape":
            if ch == "[":
                self._esc = "csi"
                self._csi_params = []
                return i + 1
            # ESC ESC, or ESC followed by a byte that cannot extend the
            # sequence: the escape resolves now.  A restarting ESC keeps
            # the pending state; any other byte is re-read as ground.
            events.append(Key("escape"))
            if ch == "\x1b":
                return i + 1
            self._esc = None
            return i
        # CSI: parameter/intermediate bytes, then one final byte.
        code = ord(ch)
        if 0x20 <= code <= 0x3F:
            self._csi_params.append(ch)
            return i + 1
        if 0x40 <= code <= 0x7E:
            params = "".join(self._csi_params)
            self._esc = None
            self._csi_params = []
            self._emit_csi(params, ch, events)
            return i + 1
        # Aborted by an invalid byte: the sequence degrades and the byte is
        # re-read as ground (a CR becomes enter, and so on).
        events.extend(self._degrade_csi())
        return i

    def _degrade_csi(self) -> list[Key | Paste]:
        """Emit the escape part of a degraded CSI and clear the csi state.

        The collected parameter characters are re-read literally as ground
        keys, preserving the historical degrade semantics; the ``[``
        introducer stays consumed.
        """
        events: list[Key | Paste] = [Key("escape")]
        for param in self._csi_params:
            key = _char_key(param)
            if key is not None:
                events.append(key)
        self._esc = None
        self._csi_params = []
        return events

    def _emit_csi(self, params: str, final: str, events: list[Key | Paste]) -> None:
        """Dispatch a complete CSI sequence; unknown sequences are dropped."""
        if final == "~":
            first = params.split(";", 1)[0]
            try:
                code = int(first) if first else 0
            except ValueError:
                return  # e.g. "ESC [ 3;5-~": unknown, dropped
            if code == _PASTE_START_CODE:
                self._paste = []
                return
            if code == _PASTE_END_CODE:
                self._close_paste(events)
                return
            name = _TILDE_KEYS.get(code)
            if name is not None:
                events.append(Key(name))
            return
        name = _FINAL_KEYS.get(final)
        if name is not None:
            events.append(Key(name))

    def _close_paste(self, events: list[Key | Paste]) -> None:
        """Deliver the accumulated paste, or drop a stray end marker."""
        if self._paste is None:
            return  # end marker without a start: dropped
        events.append(Paste("".join(self._paste)))
        self._paste = None


# ---------------------------------------------------------------------------
# Key sources
# ---------------------------------------------------------------------------


class ScriptedKeys:
    """A key source that replays a fixed sequence of events, then EOFs.

    Handy for tests and demos: hand it ``Key``/``Paste`` events and every
    ``read()`` returns the next item in order, until the sequence is
    exhausted -- after which ``read()`` returns ``None`` forever.  A ``None``
    item inside the sequence is delivered as a one-shot end-of-stream signal,
    exactly like a real source reporting EOF before more input arrives.
    """

    def __init__(self, events: Iterable[Key | Paste | None] = ()) -> None:
        self._events = list(events)
        self._index = 0

    async def read(self) -> Key | Paste | None:
        if self._index >= len(self._events):
            return None
        event = self._events[self._index]
        self._index += 1
        return event


# Windows console input mode bits (wincon.h).
_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

#: Ctrl is held (LEFT_CTRL_PRESSED | RIGHT_CTRL_PRESSED).
_CTRL_PRESSED = 0x000C

#: Virtual-key codes the console-record path maps (winuser.h).
_VK_KEYS = {
    0x08: "backspace",  # VK_BACK
    0x09: "tab",  # VK_TAB
    0x0D: "enter",  # VK_RETURN
    0x1B: "escape",  # VK_ESCAPE
    0x21: "page_up",  # VK_PRIOR
    0x22: "page_down",  # VK_NEXT
    0x23: "end",  # VK_END
    0x24: "home",  # VK_HOME
    0x25: "left",  # VK_LEFT
    0x26: "up",  # VK_UP
    0x27: "right",  # VK_RIGHT
    0x28: "down",  # VK_DOWN
    0x2E: "delete",  # VK_DELETE
}

#: INPUT_RECORD.EventType for a keyboard record; every other type is skipped.
_KEY_EVENT = 1


def windows_input_mode(old: int) -> int:
    """The console input mode for raw-ish reading, derived from ``old``.

    Clears ``ENABLE_LINE_INPUT`` and ``ENABLE_ECHO_INPUT`` (the toolkit does
    its own line editing and echoing) and sets
    ``ENABLE_VIRTUAL_TERMINAL_INPUT`` (so navigation keys reach the console
    record path).  Every other bit passes through untouched -- notably
    ``ENABLE_PROCESSED_INPUT``, which a console normally has set and which
    keeps Ctrl-C raising a real ``KeyboardInterrupt`` as a second line of
    defence.
    """
    return (old & ~(_ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT)) | _ENABLE_VIRTUAL_TERMINAL_INPUT


# Windows console input structures.  They are defined portably (``ctypes`` is
# stdlib everywhere) so this module imports identically on every platform and
# the field offsets can be asserted in tests; the field widths follow the
# Windows SDK, so on Windows these are exactly KEY_EVENT_RECORD (16 bytes)
# and INPUT_RECORD (20 bytes).  Elsewhere the sizes differ and nothing here is
# ever touched: the record path only runs when ``os.name == "nt"``.
class _CharUnion(ctypes.Union):
    """The ``uChar`` member of KEY_EVENT_RECORD."""

    _fields_ = [("UnicodeChar", ctypes.c_wchar), ("AsciiChar", ctypes.c_char)]


class _KeyEventRecord(ctypes.Structure):
    """KEY_EVENT_RECORD: 16 bytes on Windows."""

    _fields_ = [
        ("bKeyDown", ctypes.c_int32),  # BOOL
        ("wRepeatCount", ctypes.c_uint16),  # WORD
        ("wVirtualKeyCode", ctypes.c_uint16),
        ("wVirtualScanCode", ctypes.c_uint16),
        ("uChar", _CharUnion),
        ("dwControlKeyState", ctypes.c_uint32),  # DWORD
    ]


class _InputRecord(ctypes.Structure):
    """INPUT_RECORD: 20 bytes on Windows."""

    _fields_ = [
        ("EventType", ctypes.c_uint16),
        ("Event", _KeyEventRecord),
    ]


def _kernel32() -> "ctypes.WinDLL":
    """kernel32 with the console-mode and console-input prototypes set."""
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetConsoleMode.restype = ctypes.c_int
    api.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    api.SetConsoleMode.restype = ctypes.c_int
    api.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.ReadConsoleInputW.restype = ctypes.c_int
    api.ReadConsoleInputW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_InputRecord),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    api.PeekConsoleInputW.restype = ctypes.c_int
    api.PeekConsoleInputW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_InputRecord),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    return api


def _key_from_console_event(record: object) -> Key | None:
    """Map one Windows KEY_EVENT_RECORD to a key event, or ``None``.

    ``record`` is anything exposing the KEY_EVENT_RECORD fields --
    ``bKeyDown``, ``wVirtualKeyCode``, ``uChar.UnicodeChar``,
    ``dwControlKeyState`` -- which the real ctypes structure satisfies and a
    test double can imitate.  Key-up events and unrecognizable records
    return ``None``; the repeat count is ignored.

    Resolution order: the virtual-key table first (so Enter/Tab/Escape keep
    their names even though their characters collide with Ctrl codes), then
    Ctrl combinations, then the plain Unicode character -- wide characters
    pass through untouched, bypassing any code page.
    """
    if not record.bKeyDown:
        return None
    return _key_from_values(
        record.wVirtualKeyCode, record.uChar.UnicodeChar, record.dwControlKeyState
    )


def _key_from_values(vk: int, char: str, ctrl: int) -> Key | None:
    """Map a record's virtual key, character and control state to a key.

    The virtual-key resolution of :func:`_key_from_console_event`, shared
    with the record-to-byte-stream path so both agree on names.
    """
    name = _VK_KEYS.get(vk)
    if name is not None:
        return Key(name)
    code = ord(char) if char else 0
    if 0x01 <= code <= 0x1A:  # the console delivered the control byte
        return Key(f"c-{chr(ord('a') + code - 1)}")
    if ctrl and ("a" <= char <= "z" or "A" <= char <= "Z"):
        return Key(f"c-{char.lower()}")
    if code >= 0x20 and not 0x7F <= code <= 0x9F:
        return Key(char, char)
    return None


def _console_record_events(
    record: tuple[bool, int, str, int], decoder: KeyDecoder
) -> list[Key | Paste]:
    """Decode one console key record -- ``(bKeyDown, vk, char, ctrl)``.

    The character wins.  With ``ENABLE_VIRTUAL_TERMINAL_INPUT`` set (see
    :func:`windows_input_mode`) the console delivers input as a VT byte
    stream: each record carries one byte of the sequence -- ESC, CR, BS,
    printables, code points -- in ``UnicodeChar``, so every non-NUL
    character is UTF-8 encoded and fed to ``decoder``, which assembles
    sequences across records.  Only a NUL character falls back to the
    virtual-key mapping, the delivery another console semantics uses for
    keys that produce no character (arrows, page keys) and for Ctrl
    combinations reported through the control state alone.

    Exactly one branch runs per record, so the two semantics never
    double-enqueue a key.
    """
    down, vk, char, ctrl = record
    if not down:
        return []
    if char != "\x00":
        return decoder.feed(char.encode("utf-8"))
    key = _key_from_values(vk, char, ctrl)
    if key is not None:
        return [key]
    if ctrl & _CTRL_PRESSED and 0x41 <= vk <= 0x5A:  # VK_A..VK_Z, no character
        return [Key(f"c-{chr(vk + (ord('a') - ord('A')))}")]
    return []


def keys_from_console_events(
    events: Iterable[tuple[bool, int, str, int]],
) -> list[Key | Paste]:
    """Replay a console-record stream through the byte-stream decoder.

    Pure and console-free, so both console delivery semantics are testable
    without a Windows console: each event is a ``(bKeyDown, virtual_key,
    char, control_state)`` tuple and the mapping logic is the very same
    ``_console_record_events`` the live reader uses.  A fresh decoder is
    created per call and no settle/flush is applied -- a replay ending
    mid-sequence leaves that state inside the throwaway decoder, exactly
    where the live reader would settle it after a silence period.
    """
    decoder = KeyDecoder()
    out: list[Key | Paste] = []
    for record in events:
        out.extend(_console_record_events(record, decoder))
    return out


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
    """

    def __init__(self, fd: int | None = None) -> None:
        self._fd = _stdin_fd() if fd is None else fd
        self._queue: "queue.SimpleQueue[Key | Paste | None]" = queue.SimpleQueue()
        self._decoder = KeyDecoder()
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._closed = False
        self._console = False  # Windows console-record path is active
        self._saved_attrs: list | None = None  # POSIX termios attributes
        self._saved_mode: tuple[int, int] | None = None  # Windows (handle, mode)
        self._cooked_fallback = False
        self._last_activity = time.monotonic()  # input-see clock for settle

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
            max_workers=1, thread_name_prefix="mocode-tui-keys"
        )
        self._thread = threading.Thread(
            target=self._reader, name="mocode-tui-keys", daemon=True
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

    def _settle_due(self) -> bool:
        """Whether the input has been silent for the settle window."""
        return time.monotonic() - self._last_activity >= _SETTLE_SECONDS

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
        records are then pulled in one batch, delivered as VT bytes to the
        decoder, and a pending sequence is settled once the console has
        been silent for the settle window.
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
                    if record.EventType != _KEY_EVENT:
                        continue  # mouse, resize, focus, menu: carry no key
                    self._enqueue(
                        _console_record_events(
                            (
                                record.Event.bKeyDown,
                                record.Event.wVirtualKeyCode,
                                record.Event.uChar.UnicodeChar,
                                record.Event.dwControlKeyState,
                            ),
                            self._decoder,
                        )
                    )
                continue
            # Nothing waiting: settle a pending sequence once the console has
            # been silent long enough, otherwise poll again shortly (close()
            # is noticed at the loop top, so it stays immediate).
            if self._decoder.pending() and self._settle_due():
                self._enqueue(self._decoder.settle())
            else:
                time.sleep(0.005)

    def _read_bytes(self) -> None:
        """POSIX raw mode and every cooked fallback: decode raw bytes."""
        while not self._closed:
            try:
                data = os.read(self._fd, 4096)
            except OSError:
                return
            if not data:
                return  # EOF
            for event in self._decoder.feed(data):
                self._queue.put(event)
