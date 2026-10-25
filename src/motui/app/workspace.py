"""The workspace facade: the runtime's document, frame, hit and selection surface.

:class:`Workspace` is the assembly tier's view of one
:class:`~motui.app.runtime.Runtime`.  It groups the operations that describe
*what is on screen* -- the document facade (``add``/``get``/``remove``), the
frame tiling (``split``/``dock``), the panes, the scroll facades, the hit
test and the document-space selection -- behind one object.

Every member delegates to the runtime it was made from.  The facade owns no
document, frame, pane, viewport or selection of its own, so both views can
never disagree: ``workspace.document is runtime.document`` and a mutation
through either path is visible through the other.  :attr:`Runtime.workspace
<motui.app.runtime.Runtime.workspace>` caches one facade per runtime.

The split is deliberately shallow in this wave.  The state and the method
bodies still live on :class:`Runtime`; W4b moves the document/frame members
here one group at a time, keeping these signatures.  The private names are
delegated too because the App's own bookkeeping (mount/theme/focus) reads the
pane and holder tables internally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..kernel.cell import Line
from ..kernel.document import Component, Document, Section, Sizing
from ..kernel.frame import Frame, Pane, Rect
from ..kernel.hit import Hit, RowRange
from ..kernel.layout import Viewport
from ..kernel.selection import Selection

if TYPE_CHECKING:
    from .runtime import Runtime

__all__ = ["Workspace"]


class Workspace:
    """The document/frame/hit/selection facade over one runtime.

    Construct it through :attr:`Runtime.workspace
    <motui.app.runtime.Runtime.workspace>`; the facade is stateless and
    binds to exactly one runtime for its lifetime.
    """

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    # -- read-only views ---------------------------------------------------------

    @property
    def document(self) -> Document:
        """The main pane's document (the runtime's primary document)."""
        return self._runtime.document

    @property
    def viewport(self) -> Viewport:
        """The main pane's viewport (the runtime's primary viewport)."""
        return self._runtime.viewport

    @property
    def frame(self) -> Frame:
        """The runtime's frame: its tiling, docks, overlays and focus."""
        return self._runtime.frame

    @property
    def panes(self) -> tuple[Pane, ...]:
        """Every content pane in paint order (docks excluded)."""
        return self._runtime.frame.panes

    @property
    def selection(self) -> Selection | None:
        """The stored document-space selection, ``None`` when there is none."""
        return self._runtime.selection

    @property
    def selection_pane(self) -> Pane | None:
        """The pane the stored selection's addresses live in."""
        return self._runtime.selection_pane

    @property
    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows."""
        return self._runtime.rows

    # -- document facade ---------------------------------------------------------

    def pane(self, pane_id: str) -> Pane:
        """The pane with ``pane_id`` (content pane or dock); unknown raises."""
        return self._runtime.pane(pane_id)

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        pin: str | None = None,
        placement=None,
        sizing: Sizing = Sizing.NATURAL,
        pane: Pane | str | None = None,
    ) -> Section:
        """Append a block to a pane's document; answer its section.

        :meth:`Runtime.add <motui.app.runtime.Runtime.add>` still answers the
        block id -- the low-level handle -- and this facade resolves it to
        the :class:`~motui.kernel.document.Section` the caller keeps.  The
        section is looked up through its owning pane, so a ``pane=`` write
        answers a section from that pane's document, not the main one.
        """
        block_id = self._runtime.add(
            component,
            id=id,
            pin=pin,
            placement=placement,
            sizing=sizing,
            pane=pane,
        )
        return self._section(block_id)

    def fill(self, component: Component, *, pane: Pane | str | None = None) -> Section:
        """Make ``component`` the fill of a pane; answer the section."""
        return self._runtime.fill(component, pane=pane)

    def get(self, id: str) -> Section:
        """The section with ``id``, resolved frame-wide."""
        return self._section(id)

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` and answer its section.

        The section is read before the detach (the document drops it), so
        the caller still holds the value and the component it wraps.
        """
        section = self._section(id)
        self._runtime.remove(id)
        return section

    def _section(self, id: str) -> Section:
        """The section ``id`` in whichever pane's document holds it."""
        return self._runtime._holder(id).viewport.document.get(id)

    # -- split / dock / scroll surface -------------------------------------------

    def split(
        self,
        orientation: str,
        *,
        ratios: tuple[float, ...] = (1, 1),
        min_size: int = 1,
        separator: bool = True,
        pane: Pane | str | None = None,
    ) -> tuple[Pane, ...]:
        """Split a pane; return the panes it became, in paint order."""
        return self._runtime.split(
            orientation,
            ratios=ratios,
            min_size=min_size,
            separator=separator,
            pane=pane,
        )

    def dock(
        self,
        component: Component,
        *,
        edge: str = "bottom",
        size: int | None = None,
    ) -> Pane:
        """Pin ``component`` against ``edge``; return its pane."""
        return self._runtime.dock(component, edge=edge, size=size)

    def undock(self, edge: str = "bottom") -> Pane | None:
        """Release the dock on ``edge``; return its pane (``None`` when empty)."""
        return self._runtime.undock(edge)

    def dock_region(self, edge: str = "bottom") -> Rect | None:
        """The rectangle the last composition laid the dock on ``edge`` in."""
        return self._runtime.dock_region(edge)

    def pane_at(self, x: int, y: int) -> Pane | None:
        """The pane a 0-based screen cell falls in, or ``None``."""
        return self._runtime.pane_at(x, y)

    def visible_range(self, pane: Pane | str | None = None) -> RowRange | None:
        """A pane's visible body rows as screen rows."""
        return self._runtime.visible_range(pane)

    def reveal(self, bid: str, row: int) -> bool:
        """Bring the document address ``bid``/``row`` on screen."""
        return self._runtime.reveal(bid, row)

    # -- selection / hit ---------------------------------------------------------

    def set_selection(
        self, selection: Selection | None, *, pane: Pane | str | None = None
    ) -> None:
        """Replace the selection and repaint; ``None`` clears it."""
        self._runtime.set_selection(selection, pane=pane)

    def hit(self, x: int, y: int) -> Hit | None:
        """Resolve a 0-based terminal cell to a pane, a block and a cell."""
        return self._runtime.hit(x, y)

    def hit_leaf(self, x: int, y: int) -> tuple[Component, int, int] | None:
        """The deepest component owning a cell, with its own coordinates."""
        return self._runtime.hit_leaf(x, y)

    # -- internal delegates (the App's bookkeeping reads these) -------------------

    def _document_panes(self) -> tuple[tuple[Pane, Document], ...]:
        """Every pane and the document it shows, in paint order (docks last)."""
        return self._runtime._document_panes()

    def _content_pane(self, pane: Pane | str | None) -> Pane:
        """Resolve a content target: an explicit pane, or the main one."""
        return self._runtime._content_pane(pane)

    def _focus_pane(self, pane: Pane | str | None) -> Pane:
        """Resolve a structural target: an explicit pane, or the focused one."""
        return self._runtime._focus_pane(pane)

    def _focused_viewport(self) -> Viewport:
        """The viewport the scroll facades move: the focused pane's window."""
        return self._runtime._focused_viewport()

    def _holder(self, id: str) -> Pane:
        """The one pane whose document holds ``id``."""
        return self._runtime._holder(id)

    def _panes_holding(self, id: str) -> tuple[Pane, ...]:
        """Every pane whose document holds a block with ``id``."""
        return self._runtime._panes_holding(id)

    def _next_block_id(self) -> str:
        """The first ``bN`` id no document in the frame holds."""
        return self._runtime._next_block_id()

    def _focused_id(self) -> str | None:
        """The focused pane's id, ``None`` on a frame that holds none."""
        return self._runtime._focused_id()

    def _pane_id(self, pane: Pane | str) -> str:
        """The id of ``pane``, which the frame must hold."""
        return self._runtime._pane_id(pane)

    def _retile(self) -> None:
        """Lay the tiling out for the screen as it stands right now."""
        self._runtime._retile()

    def _dock_height(self, edge: str, width: int, height: int) -> int:
        """The dock height on ``edge`` at ``width``."""
        return self._runtime._dock_height(edge, width, height)

    def _set_selection(
        self, selection: Selection | None, pane_id: str | None
    ) -> None:
        """The one write on the runtime's selection surface."""
        self._runtime._set_selection(selection, pane_id)
