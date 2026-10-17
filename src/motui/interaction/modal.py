"""Modal: the blocking layer -- a panel over the frame, a scrim behind it.

:class:`Modal` packages everything a modal *is* around any panel component:
the overlay registration, the full-frame scrim, the placement of the panel
(centered, or pinned to an anchor cell), the unified event routing and the
click-outside dismissal.  It is the controller
:class:`~motui.widgets.dialog.Dialog` was built for -- the pure component
paints a box, the modal decides where it sits, what is dimmed behind it and
which keys reach the body first -- and the same door serves every panel
that renders rows: the :class:`~motui.interaction.palette.Palette`'s own
query-over-list panel, a ComboBox dropdown, a context menu.

The panel is a structural duck, not a class: anything with
``render(width) -> list[Line]``, a ``click(row, col) -> bool`` over its own
rendered cells, a ``handle(event) -> bool`` for the keyboard and the
library's one-shot ``chosen`` (writable -- a decision is a **write**, so a
``None``-valued button is a decision too) fits the socket.  A panel that
carries a ``body`` with its own ``handle`` gets the keyboard **first** --
the Textual reading: an input field owns its editing keys and its own
``enter`` where it binds one, and an unclaimed ``enter`` falls through to
the dialog's buttons.  That is exactly why a prompted field works:
:class:`~motui.widgets.textfield.Input` never binds ``enter``, so the key
reaches the dialog row.

**The lifecycle.**  ``tui`` is the driver whose frame the overlay registers
on at construction (the :class:`~motui.interaction.overlays.Toasts`
lifecycle: the registry lives for the frame's life, and a retile re-divides
the panes in place).  :meth:`detach` unregisters by identity and is
idempotent; :meth:`open` shows the panel (resetting ``chosen``) and
registers the overlay when it is not held, :meth:`close` hides it and lands
the result.  A **closed** modal paints nothing -- :meth:`paint` hands the
composed layout straight back -- so a host may keep one mounted for the
session and route it unconditionally; :attr:`is_open` is the guard that
makes that cheap, and ``open`` never re-initializes the panel: a fresh
visit is the panel's own ``open`` (or the host rebuilding it).

**The paint.**  While open, every row of the composed frame goes through
:func:`~motui.kernel.lines.overlay` against the scrim style -- attribute
``dim`` by default: the colors keep their own values and only the weight
drops (D4) -- and then the panel's rows are spliced into the frame at the
panel's rectangle.  The panel renders at the frame's width and its box is
as wide as its widest row, as tall as its rows; both are clamped to the
frame, and the panel is either centered in the frame or pinned so its
top-left cell is ``anchor`` (clamped into the frame -- an anchor row past
the bottom parks the panel against the bottom edge, the anchored-panel
door).  The rectangle the paint splices through is the very one
:meth:`handle` routes a press with: one derivation, two readers.

**The routing.**  ``handle(event) -> bool`` consumes while open, the
library's contract, and a modal consumes **everything**: a left press
outside the panel is a dismissal (``dismiss_on_click_outside``, default
``True``) that closes with ``None``, every other pointer report is
swallowed so the background never sees a click; a key the panel takes is
the panel's, an ``escape`` nobody takes cancels, and every other key is
consumed and dropped -- a modal owns the keyboard, so the host's own
shortcuts (``c-c``'s quit) are the host's to handle *before* the modal in
its dispatch order.  :attr:`chosen` is the panel's result, read once by the
host and reset to ``None``: the value of the button taken (``None`` is a
legal value), or ``None`` for ``escape``, a click outside or a programmatic
:meth:`close`.

The theme resolves the scrim through the charter -- explicit
``scrim_style`` > ``theme.dim`` > :data:`DEFAULT_THEME
<motui.kernel.theme.DEFAULT_THEME>` -- so the default is
``Style(dim=True)`` and a themed host restyles the veil with one field.
``set_theme`` is deliberately not offered: a re-skin rebuilds the panel and
its modal (the :class:`~motui.interaction.find.Find` lesson -- rebuilding
is simpler than re-skinning in place).
"""

from __future__ import annotations

from dataclasses import replace

from ..app import TUI
from ..kernel.events import Key, MouseEvent, Paste
from ..kernel.frame import Rect, splice_row
from ..kernel.lines import Line, overlay
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..kernel.viewport import ScreenLayout

__all__ = ["Modal"]

#: The marker :class:`Modal` hides in the panel's ``chosen`` while one event
#: routes through it: any write the routing makes -- a button's value,
#: ``None`` for a cancel -- shows as a difference from this sentinel, so a
#: decision is told from a cursor move whatever value the decision carries.
_PENDING = object()


class Modal:
    """A centered (or anchored) panel over the frame: the blocking layer.

    ``tui`` is the driver whose frame the overlay registers on (at
    construction, the ``Toasts`` lifecycle); ``dialog`` the pure component
    painted in the box (``Dialog``, ``Prompt``, any ``Component`` with a
    ``handle`` for the keyboard); ``anchor=(y, x)`` pins the panel's
    top-left cell (clamped into the frame) instead of centering it -- the
    ComboBox / context-menu door.  ``dismiss_on_click_outside`` (default
    ``True``) consumes a press outside the panel and closes with ``None``.

    ``chosen`` is the panel's result, read once by the host and reset to
    ``None``: the value of the button the user took, or ``None`` for
    ``escape`` / a click outside / ``close()``.  A closed modal paints
    nothing and consumes nothing (:attr:`is_open`), so a host may keep one
    mounted for the session and route it unconditionally.

    ``scrim=False`` turns the veil off; ``scrim_style`` is its explicit
    style and ``theme`` the rest, resolved at construction through the
    charter -- explicit > ``theme.dim`` > :data:`DEFAULT_THEME
    <motui.kernel.theme.DEFAULT_THEME>` -- so the default veil is the
    attribute ``dim`` of D4 (colors kept, weight dropped).
    """

    __slots__ = (
        "_anchor",
        "_detached",
        "_dialog",
        "_dismiss_outside",
        "_open",
        "_scrim",
        "_scrim_style",
        "_tui",
        "chosen",
    )

    def __init__(
        self,
        tui: TUI,
        dialog,
        *,
        anchor: tuple[int, int] | None = None,
        scrim: bool = True,
        scrim_style: Style | None = None,
        dismiss_on_click_outside: bool = True,
        theme: Theme | None = None,
    ) -> None:
        self._tui = tui
        self._dialog = dialog
        self._anchor = None if anchor is None else (anchor[0], anchor[1])
        self._scrim = scrim
        theme = DEFAULT_THEME if theme is None else theme
        self._scrim_style = scrim_style if scrim_style is not None else theme.dim
        self._dismiss_outside = dismiss_on_click_outside
        self._open = False
        self._detached = False
        #: The pending result: written by :meth:`close`; read once by the
        #: host, which resets it to ``None``.
        self.chosen: object | None = None
        # The driver's frame seam (module docstring): the overlay registers
        # here for the frame's life, exactly as the toasts' controller does.
        tui.frame.add_overlay(self)

    def __repr__(self) -> str:
        return (
            f"Modal({type(self._dialog).__name__}, open={self._open}, "
            f"chosen={self.chosen!r})"
        )

    # -- the lifecycle ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the panel is showing (and therefore consuming events)."""
        return self._open

    def open(self) -> None:
        """Show the panel: nothing chosen, registered when needed, repaint.

        The panel's own state is the panel's: a Palette resets its query and
        its list before calling this, and ``Modal`` never re-initializes the
        dialog -- it clears :attr:`chosen` and flips the state the paint and
        the routing read.  A host that mounted the modal afresh needs
        nothing else the registration has not already done; a modal whose
        overlay was never registered (a host that detached and reopened)
        stays unregistered: ``detach`` is final, the ``Toasts`` stance.
        """
        self.chosen = None
        self._open = True
        if not self._detached and self not in self._tui.frame.overlays:
            self._tui.frame.add_overlay(self)
        self._tui.invalidate()

    def close(self, value: object = None) -> None:
        """Hide the panel, landing ``value`` as the result.

        The registration rides (a closed modal paints zero bytes), and the
        frame is invalidated so the panel and its scrim leave the screen.
        """
        self.chosen = value
        self._open = False
        self._tui.invalidate()

    def detach(self) -> None:
        """Unregister the overlay (the ``EveryHandle`` convention).

        By identity, and idempotent: nothing is unregistered when the frame
        no longer holds the modal, so a second detach is a no-op.  A
        detached modal stops painting; its state is the host's to leave
        alone (the tier's routing is the host's own dispatch to leave out).
        """
        if self._detached:
            return
        self._detached = True
        if self in self._tui.frame.overlays:
            self._tui.frame.remove_overlay(self)

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Key | Paste) -> bool:
        """Route ``event`` into the panel; ``True`` whenever the modal is open.

        The consume-a-key contract every controller of the tier follows,
        with the modal's own answer: open, the event is the modal's whatever
        it is -- a left press decides (inside the panel it is the panel's
        click, outside it is a dismissal), every other report is swallowed,
        a key goes to the exchanging routing below and a ``Paste`` to the
        body.  Closed, the answer is ``False`` and nothing is touched.
        """
        if not self._open:
            return False
        if isinstance(event, MouseEvent):
            self._mouse(event)
            return True
        return self._key(event)

    def _mouse(self, event: MouseEvent) -> None:
        """Route one pointer report: a left press decides, everything is eaten.

        A press inside the panel is the panel's click at its own coordinates
        -- a pressed button writes a decision and closes with it (the value
        is read through the same write detector the keyboard uses, so a
        ``None``-valued button decides too); a press outside dismisses when
        ``dismiss_on_click_outside``, closing with ``None``, and is consumed
        either way.  Release, motion and the wheel reports are swallowed
        with the panel's state untouched: behind a modal there is nothing to
        drag, hover or scroll.
        """
        self.chosen = None
        if event.kind != "press" or event.name != "left":
            return
        placed = self._placed()
        if placed is None:
            return  # a frame with no room for the panel has no cells to decide on
        panel, _rows = placed
        if panel.x <= event.x < panel.right and panel.y <= event.y < panel.bottom:
            self._arm()
            self._dialog.click(event.y - panel.y, event.x - panel.x)
            decision = self._collect()
            if decision is not _PENDING:
                self.close(decision)
            return
        if self._dismiss_outside:
            self.close()

    def _key(self, event: Key | Paste) -> bool:
        """Route one key or paste into the panel; always consumed (the modal).

        Body-first: a panel's ``body`` with a ``handle`` gets the event and,
        taking it, keeps it -- an input field's editing keys and its own
        ``enter`` where it binds one.  A key the body left alone goes to the
        panel's own ``handle`` (the dialog's button row).  A decision either
        of them writes into ``chosen`` closes the modal with it (the value,
        ``None`` included); otherwise a key nobody took is the panel's
        ``escape`` -- the cancel -- and every other key is consumed and
        dropped, so the host's shortcuts never fire under an open modal.
        Nothing here can answer ``False``: the modal owns the keyboard.
        """
        body = getattr(self._dialog, "body", None)
        self._arm()
        consumed = False
        if body is not None and hasattr(body, "handle"):
            consumed = bool(body.handle(event))
        if not consumed and isinstance(event, Key):
            handle = getattr(self._dialog, "handle", None)
            if handle is not None:
                consumed = bool(handle(event))
        decision = self._collect()
        if decision is not _PENDING:
            self.close(decision)
            return True
        # No decision: a routing that decided nothing clears a pending
        # result (navigation clears a stale pick -- the Palette's old rule).
        self.chosen = None
        if not consumed and isinstance(event, Key) and event.name == "escape":
            self.close()
        return True

    # -- the write detector ------------------------------------------------------

    def _arm(self) -> None:
        """Hide the sentinel in the panel's ``chosen`` for one routing."""
        self._dialog.chosen = _PENDING

    def _collect(self) -> object:
        """What the routing wrote into ``chosen``: the decision, or ``_PENDING``."""
        value = self._dialog.chosen
        self._dialog.chosen = None
        return value

    # -- the placement -----------------------------------------------------------

    def _placed(self) -> tuple[Rect, list[Line]] | None:
        """The panel's rectangle and rows, ``None`` when the frame hosts none.

        The panel renders at the frame's width, the box is as wide as its
        widest row and as tall as its rows, and both are clamped to the
        frame.  Centered -- ``(rect.width - w) // 2`` floors the left
        offset, so an odd remainder goes to the right -- or anchored at
        ``(y, x)``, clamped into ``[rect.y, rect.bottom - h] x
        [rect.x, rect.right - w]``: an anchor past an edge parks the panel
        against it.  One derivation, two readers: :meth:`paint` splices
        through the rectangle this answers and :meth:`handle` routes a press
        with it, so a click can never land on another cell than it paints.
        """
        rect = self._tui.frame.rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return None
        rows = [row.fit(rect.width) for row in self._dialog.render(rect.width)]
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
        return Rect(left, top, width, height), rows

    # -- the paint ---------------------------------------------------------------

    def paint(self, frame) -> ScreenLayout:
        """The panel over the scrimmed frame; the layout itself while closed.

        Pure -- the frame's rows, its rectangle and the panel's rendered
        rows are the only inputs -- and the identity when the modal is
        closed on an empty frame: the zero-byte case the overlay registry
        runs on.  Otherwise every composed row is re-segmented through
        ``overlay(scrim_style, ...)`` (the colors keep their own values and
        only the weight drops, D4) and the panel's rows are spliced in at
        its rectangle, cut and padded by the splice, never past the frame.
        """
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
