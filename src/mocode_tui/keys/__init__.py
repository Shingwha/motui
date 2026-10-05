"""Keyboard events: the event model, the decoder, the keymaps, the sources.

Four layers live here:

* the **event model** -- :class:`Key` (a routable name plus the printable
  character, if any), :class:`Paste` (a bracketed-paste payload) and
  :class:`MouseEvent` (a :class:`Key` subclass carrying a mouse report's
  button and coordinates);
* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (incremental
  UTF-8 and escape sequences assembled across feeds, control names, CSI
  navigation keys, bracketed paste);
* the **keymaps** -- :data:`Keymap` and the two shipped default tables
  (:data:`DEFAULT_INPUT_KEYMAP` for :class:`~mocode_tui.widgets.input.Input`,
  :data:`DEFAULT_EDITOR_KEYMAP` for
  :class:`~mocode_tui.widgets.editor.Editor`);
* the **sources** -- :class:`ScriptedKeys` for tests and :class:`RawTerminalKeys`
  for a real terminal (POSIX ``termios`` raw mode or the Windows console
  record API, with a cooked-line fallback).

Each layer lives in its own module -- ``events`` (the event model),
``decoder`` (the pure byte decoder), ``keymap`` (the key-name to
editing-action tables) and ``sources`` (the key sources, with the
Windows-only plumbing in ``console``) -- and this package re-exports the
public surface, so ``from mocode_tui.keys import Key, KeyDecoder, ...``
is the layer's single import face.

The console module's two pure seams (:func:`windows_input_mode` and
:func:`keys_from_console_events`, public functions of
:mod:`mocode_tui.keys.console`) are re-exported here for the
Windows-plumbing tests that address them through this package; library
code imports them from their own module.

Nothing in this package builds an event loop, touches a screen, or writes to a
sink: decoding is synchronous and total, and sources only ever hand events to
their caller.
"""

from __future__ import annotations

from .console import keys_from_console_events, windows_input_mode
from .decoder import KeyDecoder
from .events import Key, KeySource, MouseEvent, Paste
from .keymap import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, Keymap
from .sources import RawTerminalKeys, ScriptedKeys

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "Key",
    "KeyDecoder",
    "KeySource",
    "Keymap",
    "MouseEvent",
    "Paste",
    "RawTerminalKeys",
    "ScriptedKeys",
]
