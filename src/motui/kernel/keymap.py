"""Key-name to editing-method tables for Input/Editor.

``DEFAULT_INPUT_KEYMAP`` binds no ``enter`` (the host keeps it);
``DEFAULT_EDITOR_KEYMAP`` adds it as newline; ``EDITOR_SUBMIT_KEYMAP``
gives it back and binds ``c-j``."""

from __future__ import annotations

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "EDITOR_SUBMIT_KEYMAP",
    "Keymap",
]

#: A keymap: key event key (:attr:`KeyEvent.key <motui.kernel.events.KeyEvent.key>`)
#: to the name of the no-argument editing method it triggers.
Keymap = dict[str, str]

#: The default table for :class:`~motui.widgets.textfield.Input`: a
#: single-line field, so there is no ``enter`` binding (the host decides what
#: the return key does -- usually submit).  ``c-z``/``c-y`` are the history
#: keys (the buffer's bounded undo/redo); the shift chords extend the
#: text-internal selection, whose ``c-a`` selects the whole buffer (the
#: line start is the plain ``home``).
DEFAULT_INPUT_KEYMAP: Keymap = {
    "left": "move_left",
    "right": "move_right",
    "home": "home",
    "end": "end",
    "c-a": "select_all",
    "c-e": "end",
    "backspace": "backspace",
    "delete": "delete",
    "up": "move_up",
    "down": "move_down",
    "c-u": "clear",
    "c-z": "undo",
    "c-y": "redo",
    "s-left": "select_left",
    "s-right": "select_right",
    "s-home": "select_home",
    "s-end": "select_end",
    "s-up": "select_up",
    "s-down": "select_down",
}

#: The default table for :class:`~motui.widgets.textfield.Editor`: everything
#: :data:`DEFAULT_INPUT_KEYMAP` binds, plus ``enter`` as ``newline`` -- the
#: editor itself consumes the return key to break lines, so a host that wants
#: a submit gesture binds its own (unconsumed) key, e.g. ``c-enter``.
DEFAULT_EDITOR_KEYMAP: Keymap = {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}

#: The table for an :class:`~motui.widgets.textfield.Editor` whose host takes
#: the submit gesture: :data:`DEFAULT_EDITOR_KEYMAP` without ``enter`` -- the
#: return key stays unconsumed so the host's submit sees it -- with ``c-j``
#: bound to ``newline`` in its place (a line feed decodes to the ``c-j``
#: chord, so Ctrl-J breaks a line while the plain return key submits).
EDITOR_SUBMIT_KEYMAP: Keymap = {
    **{name: action for name, action in DEFAULT_EDITOR_KEYMAP.items() if name != "enter"},
    "c-j": "newline",
}
