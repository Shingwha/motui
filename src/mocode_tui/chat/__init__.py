"""chat: the pi-style coding-agent component layer.

This package is the mocode-specific top of the toolkit.  The
:class:`~mocode_tui.chat.message.Message` role bands and the
:class:`~mocode_tui.chat.tools.ToolBlock` /
:class:`~mocode_tui.chat.tools.EditBlock` band frames -- the pi-style
transcript blocks -- live here, moved out of the generic ``widgets``
library that used to host them.  The rest of the layer (the status line,
the slash palette, and the composer/transcript controllers) lands in the
following commits of this wave.

Everything resolves styles as explicit parameter > theme field >
:data:`~mocode_tui.core.theme.DEFAULT_THEME`, the rule the whole toolkit
follows.  The package facade below re-exports the layer's public symbols;
the final curation of the root and layer facades belongs to the
restructure's last wave.
"""

from .message import Message
from .tools import EditBlock, ToolBlock

__all__ = ["EditBlock", "Message", "ToolBlock"]
