"""Keyboard events: the event model, the byte decoder, and the key sources.

Three layers live here:

* the **event model** -- :class:`Key` (a routable name plus the printable
  character, if any), :class:`Paste` (a bracketed-paste payload) and
  :class:`MouseEvent` (a :class:`Key` subclass carrying a mouse report's
  button and coordinates);
* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (incremental
  UTF-8 and escape sequences assembled across feeds, control names, CSI
  navigation keys, bracketed paste);
* the **sources** -- :class:`ScriptedKeys` for tests and :class:`RawTerminalKeys`
  for a real terminal (POSIX ``termios`` raw mode or the Windows console
  record API, with a cooked-line fallback).

Each layer lives in its own module -- ``events`` (the event model),
``decoder`` (the pure byte decoder), ``sources`` (the key sources) and
``console`` (the Windows-only plumbing) -- and this package re-exports the
public surface, so ``from mocode_tui.keys import Key, KeyDecoder, ...`` is
unchanged.

Nothing in this package builds an event loop, touches a screen, or writes to a
sink: decoding is synchronous and total, and sources only ever hand events to
their caller.
"""

from __future__ import annotations

import time  # noqa: F401  # transitional: see the note below

from mocode_tui.keys.console import (
    _console_record_events,
    _InputRecord,
    _key_from_console_event,
    _KeyEventRecord,
    _KEY_EVENT,
    _kernel32,
    keys_from_console_events,
    windows_input_mode,
)
from mocode_tui.keys.decoder import KeyDecoder
from mocode_tui.keys.events import Key, KeySource, MouseEvent, Paste
from mocode_tui.keys.sources import (
    _CONSOLE_BATCH,
    _SETTLE_SECONDS,
    RawTerminalKeys,
    ScriptedKeys,
)

__all__ = [
    "Key",
    "KeyDecoder",
    "KeySource",
    "MouseEvent",
    "Paste",
    "RawTerminalKeys",
    "ScriptedKeys",
]

# Transitional seams: the Windows-plumbing tests still address
# ``_InputRecord``/``_KeyEventRecord``/``_kernel32`` and the ``time`` module
# through this package until the ratified fragile tests are trimmed (T4);
# the rest are re-exported so consumers need no edits while R6 designs the
# final packaging.
