"""Keyboard events: the decoder, the keymaps, the terminal source, and the
recorder.

Four groups live here:

* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (the event model
  itself -- :class:`~mocode_tui.core.events.Key`,
  :class:`~mocode_tui.core.events.Paste` and
  :class:`~mocode_tui.core.events.MouseEvent` -- lives in the kernel, next to
  the :class:`~mocode_tui.core.events.KeySource` protocol and the
  :class:`~mocode_tui.core.events.ScriptedKeys` replay source);
* the **keymaps** -- :data:`Keymap` and the three default tables of
  :mod:`~mocode_tui.keys.keymap`: :data:`DEFAULT_INPUT_KEYMAP` for
  :class:`~mocode_tui.widgets.input.Input`,
  :data:`DEFAULT_EDITOR_KEYMAP` for
  :class:`~mocode_tui.widgets.editor.Editor`, and
  :data:`EDITOR_SUBMIT_KEYMAP` for an editor whose host takes the return key
  back as its submit gesture (the three derive from one another in that
  order);
* the **sources** -- :class:`RawTerminalKeys` for a real terminal (POSIX
  ``termios`` raw mode or the Windows console record API, with a cooked-line
  fallback);
* the **recorder** -- :class:`RecordingKeys` decorates any of the above and
  appends every event it serves to a JSONL file (the ``ms``-stamped event
  stream of a real session), and :class:`ReplayKeys` serves such a file back
  as a source -- paced by the stamps, or with ``speed=0`` and no wait at
  all, which is what a regression test drives.

Each group lives in its own module -- ``decoder`` (the pure byte decoder),
``keymap`` (the key-name to editing-action tables), ``sources`` (the key
source, with the Windows-only plumbing in ``console``) and ``recorder``
(the JSONL pair above) -- and this package re-exports its own public
surface, so ``from mocode_tui.keys import KeyDecoder,
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
from .recorder import RecordingKeys, ReplayKeys
from .sources import RawTerminalKeys

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "EDITOR_SUBMIT_KEYMAP",
    "KeyDecoder",
    "Keymap",
    "RawTerminalKeys",
    "RecordingKeys",
    "ReplayKeys",
]
