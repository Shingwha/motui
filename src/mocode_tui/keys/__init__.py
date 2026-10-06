"""Keyboard events: the decoder, the keymaps, and the terminal source.

Three groups live here:

* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (the event model
  itself -- :class:`~mocode_tui.core.events.Key`,
  :class:`~mocode_tui.core.events.Paste` and
  :class:`~mocode_tui.core.events.MouseEvent` -- lives in the kernel, next to
  the :class:`~mocode_tui.core.events.KeySource` protocol and the
  :class:`~mocode_tui.core.events.ScriptedKeys` replay source);
* the **keymaps** -- :data:`Keymap` and the default tables of
  :mod:`~mocode_tui.keys.keymap`: :data:`DEFAULT_INPUT_KEYMAP` for
  :class:`~mocode_tui.widgets.input.Input`,
  :data:`DEFAULT_EDITOR_KEYMAP` for
  :class:`~mocode_tui.widgets.editor.Editor`, and
  :data:`~mocode_tui.keys.keymap.COMPOSER_KEYMAP` for the chat composer's
  editor (this facade re-exports the two editing tables; the composer's
  table is re-exported by the chat layer);
* the **sources** -- :class:`RawTerminalKeys` for a real terminal (POSIX
  ``termios`` raw mode or the Windows console record API, with a cooked-line
  fallback).

Each group lives in its own module -- ``decoder`` (the pure byte decoder),
``keymap`` (the key-name to editing-action tables) and ``sources`` (the key
source, with the Windows-only plumbing in ``console``) -- and this package
re-exports its own public surface, so ``from mocode_tui.keys import KeyDecoder,
RawTerminalKeys, ...`` is the layer's single import face.

Nothing in this package builds an event loop, touches a screen, or writes to a
sink: decoding is synchronous and total, and sources only ever hand events to
their caller.
"""

from __future__ import annotations

from .decoder import KeyDecoder
from .keymap import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, Keymap
from .sources import RawTerminalKeys

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "KeyDecoder",
    "Keymap",
    "RawTerminalKeys",
]
