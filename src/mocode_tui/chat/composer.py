"""Composer: the pinned input box of a coding-agent UI, as a controller.

Unlike every module in ``widgets`` and the other ``chat`` components, this
one is **not a pure ``render(width)`` component**: a
:class:`~mocode_tui.app.TUI` session owns exactly one input box, and
assembling it means touching a document (the box's own blocks) and the
driver (a ``TUI.every`` spinner cycle for the working label, the painter's
IME cursor anchor).  :class:`Composer` is therefore a *controller*: build
it, :meth:`~Composer.attach` it to the TUI once, then drive
:attr:`~Composer.editor`, :attr:`~Composer.palette` and
:attr:`~Composer.statusline` from the host's key loop.  Keeping that
assembly here -- instead of in every host -- is the point of the wave:
the demo's footer plumbing becomes one library object.

Since the split wave (D6) the footer is **not pinned into the transcript**:
:meth:`~Composer.attach` opens the box's own document and viewport and parks
that viewport in the driver's frame-level **bottom band**
(:meth:`~mocode_tui.app.TUI.add_band`).  The band is a region the frame
reserves beneath the pane area -- it spans the full frame width whatever the
pane tiling is, so a split never cuts the footer in half -- and the box
renders exactly as it did pinned: same five blocks, same order, same rows.
One pane and no split renders identically to the pinned footer (the chat
tests pin those rows); with a split the band sits beneath both panes and the
transcript keeps its window height for its own content.

The five blocks are laid out, top rule first, exactly the set the pi demo
builds by hand:

* ``composer-top`` -- the rule that carries the working label
  (``── ⠋ Working ───``) while any turn works;
* ``composer-input`` -- the multi-line :class:`~mocode_tui.widgets.editor.Editor`,
  keymapped so **enter is the host's submit gesture**: the editor does not
  consume it (``COMPOSER_KEYMAP`` drops the binding) and ``c-j`` breaks
  lines in its place -- the decoder emits no ``c-enter`` name, so a submit
  gesture cannot be bound to one;
* ``composer-bottom`` -- the rule that closes the box;
* ``composer-palette`` -- the palette slot: zero rows at rest, the
  :class:`~mocode_tui.chat.slash.SlashPalette`'s filtered rows while it is
  open, hanging entirely below the closed box;
* ``composer-status`` -- the two-sided :class:`StatusLine`.

The working status rides the top rule's label, so the tail never changes
height: at rest and while working alike the box is exactly top rule +
editor rows + bottom rule, and the open palette is the only thing that
grows it (downward, from the bottom rule).  ``set_working`` is
ref-counted because turns may overlap; the first working turn starts the
spinner's ``TUI.every`` cycle and the last one clears the label and
cancels the handle.

The rules take the theme's ``border`` and the working label its
``accent`` -- a host wanting the demo's brighter neutral restyles
``composer.document.get("composer-top").component`` in place (``Divider.style`` /
``label_style`` are plain attributes).  The library never sleeps: the
spinner is driven by the pump's clock.
"""

from __future__ import annotations

from ..app import TUI
from ..core.block import Block, Component, Document
from ..core.lines import Line
from ..core.theme import DEFAULT_THEME, Theme
from ..core.viewport import Viewport
from ..keys.keymap import COMPOSER_KEYMAP
from ..widgets.chrome import Divider
from ..widgets.choice import Option
from ..widgets.editor import Editor
from ..widgets.spinner import Spinner
from .slash import SlashPalette
from .statusline import StatusLine

__all__ = ["COMPOSER_KEYMAP", "Composer"]


class _PaletteSlot:
    """The palette's pinned slot: zero rows closed, its rows while open.

    The block is never sealed -- the demo's slot rule -- so every layout
    re-renders it and an open palette simply hangs its filtered rows
    below the input box, above the status line, without the pinned tail
    ever being reordered.  Delegating to the palette (rather than
    swapping the block's component on open/close) keeps the two in step
    by construction: there is no second place a host has to remember to
    update, so the slot can never show a stale palette or hide an open
    one.  The palette itself stays reachable as :attr:`palette`.
    """

    __slots__ = ("palette",)

    def __init__(self, palette: SlashPalette) -> None:
        self.palette = palette

    def render(self, width: int) -> list[Line]:
        return self.palette.render(width)

    def __repr__(self) -> str:
        return f"_PaletteSlot({self.palette!r})"


class Composer:
    """The input box: rules, editor, palette slot, status line.

    ``theme`` flows into every piece (the editor, the palette, the status
    line, the rules).  ``placeholder`` is the editor's empty-text hint
    (empty by default: pi's at-rest box shows only the cursor block);
    ``prompt`` is carried for hosts that draw one around the editor -- the
    editor itself renders no prompt, exactly as pi shows none, so the
    attribute is the same signature-symmetry affordance :class:`Editor`
    offers.  ``commands`` seed the :class:`SlashPalette`.

    :attr:`document` is the box's own document -- the five blocks live
    there, in the frame's bottom band, never in the host's transcript --
    and :attr:`viewport` the window that lays them out at the screen's
    width.
    """

    #: The spinner's frame period in seconds (the demo's ``SPINNER_INTERVAL``);
    #: a host may retune it before the first ``set_working``.
    SPINNER_INTERVAL = 0.08

    #: The label the working spinner paints onto the top rule.
    WORKING_LABEL = "Working"

    __slots__ = (
        "_blocks",
        "_busy",
        "_handle",
        "_palette_slot",
        "_spinner",
        "_top",
        "_tui",
        "document",
        "editor",
        "palette",
        "prompt",
        "statusline",
        "theme",
        "viewport",
    )

    def __init__(
        self,
        theme: Theme | None = None,
        *,
        prompt: str = "",
        placeholder: str = "",
        commands: list[Option] = (),
    ) -> None:
        self.theme = theme
        self.prompt = prompt
        self.editor = Editor(
            placeholder=placeholder,
            theme=theme,
            keymap=COMPOSER_KEYMAP,
        )
        self.palette = SlashPalette(commands, theme=theme)
        self.statusline = StatusLine(theme=theme)
        self._tui: TUI | None = None
        # The box's own document and the window over it: a frame-level band,
        # not a set of blocks pinned into the host's transcript (D6).
        self.document = Document()
        self.viewport = Viewport(self.document)
        self._blocks: tuple[Block, ...] = ()
        self._top: Divider | None = None
        self._palette_slot: _PaletteSlot | None = None
        self._spinner = Spinner(self.WORKING_LABEL)
        self._busy = 0
        self._handle = None

    # -- assembly -----------------------------------------------------------

    def attach(self, tui: TUI) -> "Composer":
        """Park the five-piece footer in ``tui``'s frame band; return self.

        One-time: attaching a composer that is already attached raises
        ``RuntimeError`` (a second call would otherwise surface as a
        duplicate-id error from the document, and a silent no-op would
        hide a host bug).
        """
        if self._tui is not None:
            raise RuntimeError("composer is already attached")
        theme = self.theme or DEFAULT_THEME
        self._tui = tui
        self._top = Divider(theme=self.theme, label_style=theme.accent)
        self._palette_slot = _PaletteSlot(self.palette)
        tui.add_band(self.viewport)
        self._blocks = (
            self._add(self._top, id="composer-top"),
            self._add(self.editor, id="composer-input"),
            self._add(Divider(theme=self.theme), id="composer-bottom"),
            self._add(self._palette_slot, id="composer-palette"),
            self._add(self.statusline, id="composer-status"),
        )
        return self

    def _add(self, component: Component, *, id: str) -> Block:
        """Append one of the box's blocks, closing the tag, and wake the frame."""
        block = self.document.add(component, id=id, pin="bottom")
        self._tui.invalidate()
        return block

    def detach(self) -> None:
        """Unpark the footer and stop the spinner; the composer can re-attach.

        The editor, palette and status line objects survive (a host keeps
        its references and the text the user typed); only the band's blocks
        and the spinner cycle go away.
        """
        if self._tui is None:
            return
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._busy = 0
        self._spinner = Spinner(self.WORKING_LABEL)
        if self._top is not None:
            self._top.label = ""
        for block in reversed(self._blocks):
            self.document.remove(block.id)
        self._blocks = ()
        self._top = None
        self._palette_slot = None
        self._tui.remove_band()
        self._tui = None

    # -- the working spinner -------------------------------------------------

    def set_working(self, on: bool) -> None:
        """Ref-count the working state; paint the spinner while it is on.

        Turns may overlap (a submit never blocks), so each working turn
        calls ``set_working(True)`` and its ``finally`` calls
        ``set_working(False)``.  The first ``True`` paints the label and
        starts the ``TUI.every`` cycle that steps the braille frames; the
        last ``False`` clears the label and cancels the handle.
        """
        if self._tui is None:
            raise RuntimeError("attach the composer before set_working")
        if on:
            self._busy += 1
            if self._busy == 1:
                self._label()
                self._handle = self._tui.every(self.SPINNER_INTERVAL, self._advance)
            return
        self._busy = max(0, self._busy - 1)
        if self._busy == 0 and self._top is not None:
            self._top.label = ""
            self._tui.invalidate()
            if self._handle is not None:
                self._handle.cancel()
                self._handle = None

    def _label(self) -> None:
        """Paint the spinner's current frame into the top rule's label."""
        if self._top is not None:
            self._top.label = f"{self._spinner.frame} {self._spinner.text}"
        if self._tui is not None:
            self._tui.invalidate()

    def _advance(self) -> None:
        """Step the braille cycle and re-label the rule (pump callback)."""
        self._spinner.advance()
        self._label()

    # -- the IME anchor -------------------------------------------------------

    def anchor_cursor(self, tui: TUI) -> None:
        """Pin the terminal cursor -- the IME candidate window -- to the input.

        The painter leaves the cursor on the last row it rewrote, which
        mid-stream is the transcript's middle, so a host calls this before
        the first frame and after every keypress.  The pinned tail counts
        bottom-up as status / palette slot / bottom rule / editor / top
        rule: the editor's last visual row is always ``height - 3`` (the
        open palette hangs below the box and pushes it up by its own
        rows), its first row ``height - 2 - editor_rows - palette_rows``.
        """
        if self._tui is None:
            raise RuntimeError("attach the composer before anchor_cursor")
        width = tui.screen.width
        vrow, vcol = self.editor.cursor_position(width)
        rows = len(self.editor.render(width))
        palette_rows = len(self._palette_slot.render(width)) if self._palette_slot else 0
        tui.painter.set_cursor(
            tui.screen.height - 2 - rows - palette_rows + vrow, vcol
        )

    def __repr__(self) -> str:
        return f"Composer(attached={self._tui is not None}, busy={self._busy})"
