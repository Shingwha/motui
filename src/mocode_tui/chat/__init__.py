"""chat: the pi-style coding-agent component layer.

This package is the mocode-specific top of the toolkit.  The
:class:`~mocode_tui.chat.message.Message` role bands and the
:class:`~mocode_tui.chat.tools.ToolBlock` /
:class:`~mocode_tui.chat.tools.EditBlock` band frames -- the pi-style
transcript blocks -- live here, moved out of the generic ``widgets``
library that used to host them, together with the
:class:`~mocode_tui.chat.statusline.StatusLine` two-sided status row, the
:class:`~mocode_tui.chat.slash.SlashPalette` command palette and the
:class:`~mocode_tui.chat.composer.Composer` /
:class:`~mocode_tui.chat.transcript.Transcript` controllers.

Two of these are controllers, not pure ``render(width)`` components: the
Composer and the Transcript touch the TUI's document and driver (pinned
blocks, ``TUI.every``, the painter's IME anchor) -- that assembly is what
this layer exists for.

Everything resolves styles as explicit parameter > theme field >
:data:`~mocode_tui.core.theme.DEFAULT_THEME`, the rule the whole toolkit
follows.  The package facade below re-exports the layer's public
symbols; :data:`~mocode_tui.chat.composer.COMPOSER_KEYMAP` is the editor
keymap a :class:`Composer` installs (everything
:data:`~mocode_tui.keys.keymap.DEFAULT_EDITOR_KEYMAP` binds except
``enter``, which stays the host's submit gesture).
"""

from .composer import COMPOSER_KEYMAP, Composer
from .message import Message
from .slash import SlashPalette
from .statusline import StatusLine
from .tools import EditBlock, ToolBlock
from .transcript import StreamHandle, Transcript

__all__ = [
    "COMPOSER_KEYMAP",
    "Composer",
    "EditBlock",
    "Message",
    "SlashPalette",
    "StatusLine",
    "StreamHandle",
    "ToolBlock",
    "Transcript",
]
