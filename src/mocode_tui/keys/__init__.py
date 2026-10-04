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

# The seven public names above, plus two kinds of transitional seam kept out
# of ``__all__`` until R6 decides their final shape:
#
# * the console module's stable test seams -- ``windows_input_mode`` (the pure
#   mode mapper) and ``keys_from_console_events`` (the pure record replay) --
#   which the Windows-plumbing tests address through this package;
# * the private seams those tests still use through the old module namespace
#   (``_key_from_console_event``, ``_console_record_events``,
#   ``_SETTLE_SECONDS``, ``_CONSOLE_BATCH``) together with the fragile-tier
#   scaffolding (``_InputRecord``, ``_KeyEventRecord``, ``_KEY_EVENT``,
#   ``_kernel32``, the ``time`` module import) that goes away in T4 when the
#   ratified fragile tests are deleted.
import time  # noqa: F401  # transitional fragile-tier scaffolding (see above)

from .console import (
    _console_record_events,
    _InputRecord,
    _key_from_console_event,
    _KeyEventRecord,
    _KEY_EVENT,
    _kernel32,
    keys_from_console_events,
    windows_input_mode,
)
from .decoder import KeyDecoder
from .events import Key, KeySource, MouseEvent, Paste
from .sources import (
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
