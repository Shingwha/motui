"""Modal: the blocking layer -- a panel over the frame with a scrim behind.

It owns the overlay registration, placement, unified routing and
click-outside dismissal. A panel is a structural duck: render, typed
hooks and a one-shot ``take``."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ..kernel.cell import Line, overlay
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.frame import Rect, splice_row
from ..kernel.geom import Pos
from ..kernel.layout import Constraints, ScreenLayout
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import DEFAULT_THEME, Theme
from ..widgets.base import Widget
from .focus import FocusManager

if TYPE_CHECKING:
    from .runtime import Runtime

__all__ = ["Modal"]

#: The marker :class:`Modal` uses while one event routes through a panel:
#: any decision the routing makes -- a button's value, ``None`` for a
#: cancel -- shows as something else, so a decision is told from a cursor
#: move whatever value the decision carries.
_PENDING = object()


class Modal:
    """A centered (or anchored) panel over the frame: the blocking layer.

    ``anchor`` pins the top-left instead of centering. ``take`` reads the
    result once; a closed modal paints and consumes nothing. ``focus`` makes
    :meth:`open` push a focus trap."""

    __slots__ = (
        "_anchor",
        "_detached",
        "_dialog",
        "_dismiss_outside",
        "_explicit_scrim",
        "_focus",
        "_open",
        "_result",
        "_scrim",
        "_scrim_style",
        "_theme",
        "_trap",
        "_tui",
    )

    def __init__(
        self,
        tui: Runtime,
        dialog,
        *,
        anchor: tuple[int, int] | None = None,
        scrim: bool = True,
        scrim_style: Style | None = None,
        dismiss_on_click_outside: bool = True,
        theme: Theme | None = None,
        focus: FocusManager | None = None,
    ) -> None:
        self._tui = tui
        self._dialog = dialog
        self._anchor = None if anchor is None else (anchor[0], anchor[1])
        self._scrim = scrim
        theme = DEFAULT_THEME if theme is None else theme
        self._theme = theme
        self._explicit_scrim = scrim_style is not None
        self._scrim_style = (
            scrim_style if scrim_style is not None else theme.overlays.scrim
        )
        self._dismiss_outside = dismiss_on_click_outside
        self._open = False
        self._detached = False
        self._focus = focus
        self._trap = False
        #: The pending result: written by :meth:`close`; read once through
        #: :meth:`take`, which clears it.
        self._result: object | None = None
        # The driver's frame seam (module docstring): the overlay registers
        # here for the frame's life, exactly as the toasts' controller does.
        tui.frame.add_overlay(self, layer="modal")

    def __repr__(self) -> str:
        return (
            f"Modal({type(self._dialog).__name__}, open={self._open}, "
            f"result={self._result!r})"
        )

    # -- the lifecycle ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the panel is showing (and therefore consuming events)."""
        return self._open

    def open(self) -> None:
        """Show the panel: clear the pending result, register when needed, push the
        focus trap and repaint."""
        self._result = None
        if self._detached:
            return  # detaching is final: a detached modal never reopens
        self._open = True
        if not self._detached and self not in self._tui.frame.overlays:
            self._tui.frame.add_overlay(self, layer="modal")
        self._push_trap()
        self._tui.refresh()

    def close(self, value: object = None) -> None:
        """Hide the panel, landing ``value`` as the one-shot result and popping the
        focus trap."""
        self._result = value
        self._open = False
        self._pop_trap()
        self._tui.refresh()

    def detach(self) -> None:
        """Unregister the overlay and close the panel; detaching is final and
        idempotent."""
        if self._detached:
            return
        self._detached = True
        self._open = False
        self._result = None
        self._pop_trap()
        if self in self._tui.frame.overlays:
            self._tui.frame.remove_overlay(self)

    def take(self) -> object | None:
        """Read the pending result once and clear it; ``None`` is a legal value."""
        value = self._result
        self._result = None
        return value

    def _push_trap(self) -> None:
        """Push the dialog as the configured focus manager's trap (once)."""
        if self._focus is not None and not self._trap:
            self._focus.push_trap([self._dialog])
            self._trap = True

    def _pop_trap(self) -> None:
        """Pop the focus trap this modal pushed, restoring the layer below."""
        if self._focus is not None and self._trap:
            self._focus.pop_trap()
            self._trap = False

    def set_theme(self, theme: Theme) -> None:
        """Re-skin the scrim and the dialog in place, unless the scrim style was
        pinned explicitly."""
        self._theme = theme
        if not self._explicit_scrim:
            self._scrim_style = theme.overlays.scrim
        if isinstance(self._dialog, Widget):
            self._dialog.theme = theme
        body = getattr(self._dialog, "body", None)
        if isinstance(body, Widget):
            body.theme = theme
        self._tui.refresh()

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Route ``event`` into the panel; every event is consumed while the modal
        is open and declined while closed."""
        if self._detached or not self._open:
            return False
        if isinstance(event, MouseEvent):
            self._mouse(event)
            return True
        return self._key(event)

    def _mouse(self, event: MouseEvent) -> None:
        """A left press inside the panel is its click, outside it dismisses; every
        other report is swallowed."""
        self._result = None
        if event.kind != "press" or event.button != "left":
            return
        placed = self._placed()
        if placed is None:
            return  # a frame with no room for the panel has no cells to decide on
        panel, _rows = placed
        if panel.x <= event.x < panel.right and panel.y <= event.y < panel.bottom:
            self._arm()
            on_click = getattr(self._dialog, "on_click", None)
            if on_click is not None:
                on_click(Pos(x=event.x - panel.x, y=event.y - panel.y))
            decision = self._collect()
            if decision is not _PENDING:
                self.close(decision)
            return
        if self._dismiss_outside:
            self.close()

    def _key(self, event: Event) -> bool:
        """Route a key or paste body-first, then the panel's own hook; a decision
        closes the modal. An unclaimed ``escape`` cancels."""
        dialog = self._dialog
        body = getattr(dialog, "body", None)
        keys = isinstance(event, KeyEvent)
        self._arm()
        consumed = False
        if body is not None:
            consumed = self._route(body, event)
        if not consumed and (keys or body is None):
            consumed = self._route(dialog, event)
        decision = self._collect()
        if decision is not _PENDING:
            self.close(decision)
            return True
        # No decision: a routing that decided nothing clears a pending
        # result (navigation clears a stale pick -- the CommandPalette's old rule).
        self._result = None
        if not consumed and keys and event.key == "escape":
            self.close()
        return True

    # -- the write detector ------------------------------------------------------

    @staticmethod
    def _route(target: object, event: Event) -> bool:
        """Send ``event`` to ``target``'s typed hook; ``True`` when consumed."""
        if isinstance(event, KeyEvent):
            hook = getattr(target, "on_key", None)
        elif isinstance(event, PasteEvent):
            hook = getattr(target, "on_paste", None)
        else:
            return False
        return bool(hook(event)) if hook is not None else False

    def _arm(self) -> None:
        """Discard any pending panel result before one routing."""
        take_decision = getattr(self._dialog, "_take_decision", None)
        if take_decision is not None:
            take_decision()
            return
        take = getattr(self._dialog, "take", None)
        if take is not None:
            take()

    def _collect(self) -> object:
        """The routing's decision, or ``_PENDING``; a panel that can decide ``None``
        implements ``_take_decision``."""
        take_decision = getattr(self._dialog, "_take_decision", None)
        if take_decision is not None:
            made, value = take_decision()
            return value if made else _PENDING
        take = getattr(self._dialog, "take", None)
        if take is not None:
            value = take()
            return value if value is not None else _PENDING
        return _PENDING

    # -- the placement -----------------------------------------------------------

    def _placed(self) -> tuple[Rect, list[Line]] | None:
        """The panel's rectangle and rows, centered or anchored and clamped -- one
        derivation shared by paint and routing."""
        rect = self._tui.frame.rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return None
        rows = [
            row.clip(WrapMode.ELLIPSIS, rect.width)
            for row in self._dialog.render(Constraints(width=rect.width))
        ]
        height = min(len(rows), rect.height)
        width = min(max((row.width for row in rows), default=0), rect.width)
        if height <= 0 or width <= 0:
            return None  # nothing to show: an empty panel paints no box
        if self._anchor is None:
            left = rect.x + max(0, (rect.width - width) // 2)
            top = rect.y + max(0, (rect.height - height) // 2)
        else:
            top = min(max(self._anchor[0], rect.y), max(rect.y, rect.bottom - height))
            left = min(max(self._anchor[1], rect.x), max(rect.x, rect.right - width))
        return Rect(x=left, y=top, width=width, height=height), rows

    # -- the paint ---------------------------------------------------------------

    def paint(self, frame) -> ScreenLayout:
        """The panel over the scrimmed frame, spliced into its rectangle; the layout
        comes back unchanged while closed."""
        layout = frame.layout
        rect = frame.rect
        if rect is None or not self._open:
            return layout
        placed = self._placed()
        if placed is None:
            return layout
        panel, rows = placed
        out = list(layout.rows)
        if self._scrim:
            out = [Line(overlay(self._scrim_style, row.segments)) for row in out]
        for index, row in enumerate(rows[: panel.height]):
            target = panel.y + index
            if not 0 <= target < len(out):
                continue  # clipped at the frame's far edge
            out[target] = splice_row(out[target], row, panel.x, panel.width, rect.width)
        return replace(layout, rows=out)
