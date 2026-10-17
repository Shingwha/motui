"""Keymap: the key-name to editing-action tables ``Input``/``Editor`` consume.

A keymap is a plain ``dict`` mapping a key event's name (:attr:`Key.name
<motui.core.events.Key.name>`) to the name of the editing method it
triggers -- ``"left" -> "move_left"`` says the left arrow calls the
component's ``move_left()``.  Action names are nothing but method names:
:meth:`~motui.widgets.input.Input.handle` looks the event's name up
and calls the same-named method, with no action registry in between.

The three default tables live here, one derivation chain in one place:

* :data:`DEFAULT_INPUT_KEYMAP` is the base: the arrows, home/end,
  backspace/delete and the ``c-a``/``c-e``/``c-u`` relatives, with the two
  wrapped-row moves for up/down, ``c-z``/``c-y`` as the buffer's
  undo/redo, and the ``s-*`` shift chords extending the text-internal
  selection (``c-a`` selects the whole buffer).  It binds no ``enter``, so
  the return key stays with the host as its submit gesture;
* :data:`DEFAULT_EDITOR_KEYMAP` is the input table plus ``enter`` as
  ``newline``: the editor itself consumes the return key;
* :data:`EDITOR_SUBMIT_KEYMAP` is the editor table minus ``enter`` -- the
  host takes the return key back as its submit gesture -- plus ``c-j`` as
  ``newline``: an editor whose return key submits needs another way to break
  a line.

Components resolve their keymap at construction: ``keymap=None`` uses the
component's default table (:data:`DEFAULT_INPUT_KEYMAP` for
:class:`~motui.widgets.input.Input`,
:data:`DEFAULT_EDITOR_KEYMAP` for
:class:`~motui.widgets.editor.Editor`).  A host rebinds
single keys by handing in a copy with one entry replaced
(``{**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}``) or removes a binding by
deleting its entry, so the component stops consuming that key and hands it
back to the host for its own routing (submit, palette, quit, ...).

Printable characters (a ``Key`` whose ``char`` is set) never go through the
keymap -- they are inserted directly -- and neither does a
:class:`~motui.core.events.Paste`.
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "EDITOR_SUBMIT_KEYMAP",
    "Keymap",
]

#: A keymap: key event name (:attr:`Key.name <motui.core.events.Key.name>`)
#: to the name of the no-argument editing method it triggers.
Keymap = dict[str, str]

#: The default table for :class:`~motui.widgets.input.Input`: a
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

#: The default table for :class:`~motui.widgets.editor.Editor`: everything
#: :data:`DEFAULT_INPUT_KEYMAP` binds, plus ``enter`` as ``newline`` -- the
#: editor itself consumes the return key to break lines, so a host that wants
#: a submit gesture binds its own (unconsumed) key, e.g. ``c-enter``.
DEFAULT_EDITOR_KEYMAP: Keymap = {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}

#: The table for an :class:`~motui.widgets.editor.Editor` whose host takes
#: the submit gesture: :data:`DEFAULT_EDITOR_KEYMAP` without ``enter`` -- the
#: return key stays unconsumed so the host's submit sees it -- with ``c-j``
#: bound to ``newline`` in its place (the decoder emits no ``c-enter`` name,
#: so the plain return key is the only submit gesture available).
EDITOR_SUBMIT_KEYMAP: Keymap = {
    **{name: action for name, action in DEFAULT_EDITOR_KEYMAP.items() if name != "enter"},
    "c-j": "newline",
}
