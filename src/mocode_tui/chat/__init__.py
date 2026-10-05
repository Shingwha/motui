"""chat: the pi-style coding-agent component layer.

This package is the mocode-specific top of the toolkit.  The
:class:`~mocode_tui.chat.message.Message` role bands and the
:class:`~mocode_tui.chat.tools.ToolBlock` /
:class:`~mocode_tui.chat.tools.EditBlock` band frames -- the pi-style
transcript blocks -- live here, moved out of the generic ``widgets``
library that used to host them, together with the
:class:`~mocode_tui.chat.statusline.StatusLine` two-sided status row, the
:class:`~mocode_tui.chat.slash.SlashPalette` command palette and the
:class:`~mocode_tui.chat.composer.Composer` input-box controller.

Unlike the pure ``render(width)`` components, the
:class:`~mocode_tui.chat.composer.Composer` is a controller: it touches
the TUI's document and driver (pinned blocks, ``TUI.every``, the painter's
IME cursor anchor) -- that assembly is what this layer exists for.  The
transcript controller lands in the next commit of this wave.

Everything resolves styles as explicit parameter > theme field >
:data:`~mocode_tui.core.theme.DEFAULT_THEME`, the rule the whole toolkit
follows.  The package facade below re-exports the layer's public symbols;
the final curation of the root and layer facades belongs to the
restructure's last wave.
"""

from .composer import Composer
from .message import Message
from .slash import SlashPalette
from .statusline import StatusLine
from .tools import EditBlock, ToolBlock

__all__ = [
    "Composer",
    "EditBlock",
    "Message",
    "SlashPalette",
    "StatusLine",
    "ToolBlock",
]
