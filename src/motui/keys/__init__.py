"""Keyboard events: the decoder, the keymaps, and the terminal source.

Three groups live here:

* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (the event model
  itself -- the :class:`~motui.kernel.events.Event` base and its
  :class:`~motui.kernel.events.KeyEvent`,
  :class:`~motui.kernel.events.MouseEvent`,
  :class:`~motui.kernel.events.PasteEvent`,
  :class:`~motui.kernel.events.ResizeEvent` and
  :class:`~motui.kernel.events.FocusEvent` values -- lives in the kernel,
  next to the :class:`~motui.kernel.events.EventSource` protocol);
* the **keymaps** -- :data:`Keymap` and the three default tables of
  :mod:`~motui.keys.keymap`: :data:`DEFAULT_INPUT_KEYMAP` for
  :class:`~motui.widgets.textfield.Input`,
  :data:`DEFAULT_EDITOR_KEYMAP` for
  :class:`~motui.widgets.textfield.Editor`, and
  :data:`EDITOR_SUBMIT_KEYMAP` for an editor whose host takes the return key
  back as its submit gesture (the three derive from one another in that
  order);
* the **sources** -- :class:`RawTerminalKeys` for a real terminal (POSIX
  ``termios`` raw mode or the Windows console record API, with a cooked-line
  fallback).

Each group lives in its own module -- ``decoder`` (the pure byte decoder),
``keymap`` (the key-name to editing-action tables), ``sources`` (the key
source, with the Windows-only plumbing in ``console``) -- and this package
re-exports its own public surface, so ``from motui.keys import KeyDecoder,
RawTerminalKeys, ...`` is the layer's single import face.

Nothing in this package builds an event loop, touches a screen, or writes to a
sink: decoding is synchronous and total, and sources only ever hand events to
their caller.
"""

from __future__ import annotations

from .decoder import KeyDecoder
from .keymap import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    EDITOR_SUBMIT_KEYMAP,
    Keymap,
)
from .sources import RawTerminalKeys

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "EDITOR_SUBMIT_KEYMAP",
    "KeyDecoder",
    "Keymap",
    "RawTerminalKeys",
]
