"""Keymap: the key-name to editing-action table ``Input``/``Editor`` consume.

A keymap is a plain ``dict`` mapping a key event's name (:attr:`Key.name
<mocode_tui.keys.events.Key.name>`) to the name of the editing method it
triggers -- ``"left" -> "move_left"`` says the left arrow calls the
component's ``move_left()``.  Action names are nothing but method names:
:meth:`~mocode_tui.widgets.input.Input.handle_key` looks the event's name up
and calls the same-named method, with no action registry in between.

Components resolve their keymap at construction: ``keymap=None`` uses the
component's default table (:data:`DEFAULT_INPUT_KEYMAP` for
:class:`~mocode_tui.widgets.input.Input`,
:data:`DEFAULT_EDITOR_KEYMAP` for
:class:`~mocode_tui.widgets.editor.Editor`).  A host rebinds single keys by
handing in a copy with one entry replaced
(``{**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}``) or removes a binding by
deleting its entry, so the component stops consuming that key and hands it
back to the host for its own routing (submit, palette, quit, ...).

Printable characters (a ``Key`` whose ``char`` is set) never go through the
keymap -- they are inserted directly -- and neither does a
:class:`~mocode_tui.keys.events.Paste`.
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "Keymap",
]

#: A keymap: key event name (:attr:`Key.name <mocode_tui.keys.events.Key.name>`)
#: to the name of the no-argument editing method it triggers.
Keymap = dict[str, str]

#: The default table for :class:`~mocode_tui.widgets.input.Input`: a
#: single-line field, so there is no ``enter`` binding (the host decides what
#: the return key does -- usually submit).
DEFAULT_INPUT_KEYMAP: Keymap = {
    "left": "move_left",
    "right": "move_right",
    "home": "home",
    "end": "end",
    "c-a": "home",
    "c-e": "end",
    "backspace": "backspace",
    "delete": "delete",
    "up": "move_up",
    "down": "move_down",
    "c-u": "clear",
}

#: The default table for :class:`~mocode_tui.widgets.editor.Editor`: everything
#: :data:`DEFAULT_INPUT_KEYMAP` binds, plus ``enter`` as ``newline`` -- the
#: editor itself consumes the return key to break lines, so a host that wants
#: a submit gesture binds its own (unconsumed) key, e.g. ``c-enter``.
DEFAULT_EDITOR_KEYMAP: Keymap = {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}
