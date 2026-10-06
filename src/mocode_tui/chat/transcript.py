"""Transcript: the scrollable message stream of a coding-agent UI.

The controller that owns the body of a chat session: every message, tool
call and thinking aside goes through :meth:`Transcript.append`, which
pins the transcript rhythm -- each block is followed by exactly one blank
row (a :class:`~mocode_tui.widgets.layout.Spacer`), so blocks never touch
and no two blanks ever stack.  :meth:`Transcript.stream` grows a
:class:`~mocode_tui.chat.message.Message` chunk by chunk through a
:class:`StreamHandle`, and :meth:`Transcript.clear` empties the body while
leaving the pinned regions (the input box, a header) alone.

Like :class:`~mocode_tui.chat.composer.Composer` -- and unlike the pure
components -- this is a controller, not a ``render(width)`` object: it
adds and removes document blocks on a live :class:`TUI`.
"""

from __future__ import annotations

from ..app import TUI
from ..core.block import Block, Component
from ..widgets.layout import Spacer
from .message import Message

__all__ = ["StreamHandle", "Transcript"]


class StreamHandle:
    """One streaming message: the open block plus its text buffer.

    :meth:`append` here means *append a chunk of streamed text* -- not
    :meth:`Transcript.append`, which adds a whole component to the
    transcript.  A chunk grows the message's text and invalidates the
    frame; the host streams at whatever pace its model answers, the
    library never sleeps.  ``seal`` freezes the block: the viewport
    caches its rows from then on, which is what a finished message wants
    (the buffer stops being re-rendered every frame), so streaming after
    a seal is a host bug -- the rows are already frozen.
    """

    __slots__ = ("_tui", "block", "message")

    def __init__(self, tui: TUI, message: Message, block: Block) -> None:
        self._tui = tui
        self.message = message
        self.block = block

    def append(self, text: str) -> None:
        """Append one chunk of streamed text and invalidate the frame."""
        self.message.text += text
        self._tui.invalidate()

    def seal(self) -> None:
        """Freeze the block; the viewport caches its rendered rows."""
        self.block.seal()

    def __repr__(self) -> str:
        return f"StreamHandle({self.message!r}, sealed={not self.block.is_open})"


class Transcript:
    """The body message stream of a session, block by block.

    ``theme`` flows into the messages :meth:`stream` creates (a host that
    appends its own components keeps styling them itself).  With
    ``spacer=True`` -- the default, the uniform transcript rhythm -- every
    appended block is followed by one blank row; ``spacer=False`` packs
    the blocks tight for hosts that want their own spacing.
    """

    __slots__ = ("_tui", "spacer", "theme")

    def __init__(self, tui: TUI, *, theme=None, spacer: bool = True) -> None:
        self._tui = tui
        self.theme = theme
        self.spacer = spacer

    def append(self, component: Component, *, id: str | None = None) -> Block:
        """Append one transcript block (plus the blank row that follows).

        This is the whole-component append; :meth:`StreamHandle.append`
        appends one *chunk of text* to an open streaming message.  Returns
        the new block, so a host can seal it or keep writing to its
        component.  The blank row is a block of its own -- the transcript
        is a document, so the rhythm lives in the document rather than in
        a component's padding.
        """
        block = self._tui.add(component, id=id)
        if self.spacer:
            self._tui.add(Spacer(1))
        return block

    def stream(self, role: str) -> StreamHandle:
        """Append an empty ``role`` message and return its stream handle."""
        message = Message(role, "", theme=self.theme)
        return StreamHandle(self._tui, message, self.append(message))

    def clear(self) -> None:
        """Remove every body block; the pinned regions stay put.

        Blocks with a pin (``"top"``/``"bottom"``) are skipped, so the
        input box and any header survive a ``/clear`` while the
        scrollback empties.
        """
        for block in self._tui.document.blocks():
            if block.pin is None:
                self._tui.remove(block.id)

    def __repr__(self) -> str:
        return f"Transcript(blocks={len(self._tui.document)}, spacer={self.spacer})"
