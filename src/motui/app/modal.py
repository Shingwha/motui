"""Modal: the blocking layer -- a panel over the frame, a scrim behind it.

:class:`Modal` packages everything a modal *is* around any panel component:
the overlay registration, the full-frame scrim, the placement of the panel
(centered, or pinned to an anchor cell), the unified event routing and the
click-outside dismissal.  It is the controller
:class:`~motui.widgets.dialog.Dialog` was built for -- the pure component
paints a box, the modal decides where it sits, what is dimmed behind it and
which keys reach the body first -- and the same door serves every panel
that renders rows: the :class:`~motui.app.command_palette.CommandPalette`'s own
query-over-list panel, a ComboBox dropdown, a context menu.

The panel is a structural duck, not a class: anything with
``render(c) -> Surface``, a ``click(row, col) -> bool`` over its own
rendered cells, a ``handle(event) -> bool`` for the keyboard and the
library's one-shot result (``take_result()`` -- a decision is a take, so a
``None``-valued button is a decision too; a panel that can decide ``None``
also implements the private ``_take_decision()`` the routing reads) fits
the socket.  A panel that
carries a ``body`` with its own ``handle`` gets the keyboard **first** --
the Textual reading: an input field owns its editing keys and its own
``enter`` where it binds one, and an unclaimed ``enter`` falls through to
the dialog's buttons.  That is exactly why a prompted field works:
:class:`~motui.widgets.textfield.Input` never binds ``enter``, so the key
reaches the dialog row.

**The lifecycle.**  ``tui`` is the driver whose frame the overlay registers
on at construction (the :class:`~motui.app.overlays.Toasts`
lifecycle: the registry lives for the frame's life, and a retile re-divides
the panes in place).  :meth:`detach` unregisters by identity and is
idempotent; :meth:`open` shows the panel (clearing the pending result) and
registers the overlay when it is not held, :meth:`close` hides it and lands
the result.  A **closed** modal paints nothing -- :meth:`paint` hands the
composed layout straight back -- so a host may keep one mounted for the
session and route it unconditionally; :attr:`is_open` is the guard that
makes that cheap, and ``open`` never re-initializes the panel: a fresh
visit is the panel's own ``open`` (or the host rebuilding it).

**The paint.**  While open, every row of the composed frame goes through
:func:`~motui.kernel.cell.overlay` against the scrim style -- attribute
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
its dispatch order.  :meth:`take_result` reads the panel's result once and
clears it: the value of the button taken (``None`` is a legal value), or
``None`` for ``escape``, a click outside or a programmatic
:meth:`close`.

The theme resolves the scrim through the charter -- explicit
``scrim_style`` > ``theme.overlays.scrim`` > :data:`DEFAULT_THEME
<motui.kernel.theme.DEFAULT_THEME>` -- so the default is
``Style(dim=True)`` and a themed host restyles the veil with one field.
``set_theme`` re-skins in place: a theme's scrim is resolved again (unless
an explicit ``scrim_style`` was given) and a dialog that is a
:class:`~motui.widgets.base.Widget` takes the new theme, so the App's theme
propagation reaches the app-owned palette and any open panel.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ..kernel.events import Event, KeyEvent, MouseEvent
from ..kernel.frame import Rect, splice_row
from ..kernel.cell import Line, overlay
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..kernel.layout import ScreenLayout
from ..widgets.base import Widget
from .focus import FocusManager
from ..kernel.layout import Constraints

if TYPE_CHECKING:
    from .driver import TUI

__all__ = ["Modal"]

#: The marker :class:`Modal` uses while one event routes through a panel:
#: any decision the routing makes -- a button's value, ``None`` for a
#: cancel -- shows as something else, so a decision is told from a cursor
#: move whatever value the decision carries.
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

    :meth:`take_result` reads the panel's result once and clears it: the
    value of the button the user took, or ``None`` for ``escape`` / a click
    outside / ``close()``.  A closed modal paints nothing and consumes
    nothing (:attr:`is_open`), so a host may keep one mounted for the
    session and route it unconditionally.

    ``focus`` is an optional :class:`~motui.app.focus.FocusManager`:
    :meth:`open` pushes the dialog as its focus trap and :meth:`close` /
    :meth:`detach` pop it, so two stacked modals restore the layer below.

    ``scrim=False`` turns the veil off; ``scrim_style`` is its explicit
    style and ``theme`` the rest, resolved at construction through the
    charter -- explicit > ``theme.overlays.scrim`` > :data:`DEFAULT_THEME
    <motui.kernel.theme.DEFAULT_THEME>` -- so the default veil is the
    attribute ``dim`` of D4 (colors kept, weight dropped).
    """

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
        tui: TUI,
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
        #: :meth:`take_result`, which clears it.
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
        """Show the panel: nothing pending, registered when needed, repaint.

        The panel's own state is the panel's: a CommandPalette resets its query and
        its list before calling this, and ``Modal`` never re-initializes the
        dialog -- it clears the one-shot result and flips the state the paint
        and the routing read.  A host that mounted the modal afresh needs
        nothing else the registration has not already done; a modal whose
        overlay was never registered (a host that detached and reopened)
        stays unregistered: ``detach`` is final, the ``Toasts`` stance.
        A configured :class:`~motui.app.focus.FocusManager` gets the
        dialog pushed as a focus trap, so the panel owns the focus while it
        is up.
        """
        self._result = None
        if self._detached:
            return  # detaching is final: a detached modal never reopens
        self._open = True
        if not self._detached and self not in self._tui.frame.overlays:
            self._tui.frame.add_overlay(self, layer="modal")
        self._push_trap()
        self._tui.refresh()

    def close(self, value: object = None) -> None:
        """Hide the panel, landing ``value`` as the one-shot result.

        The registration rides (a closed modal paints zero bytes), the focus
        trap pops back to the layer below, and the frame is invalidated so
        the panel and its scrim leave the screen.
        """
        self._result = value
        self._open = False
        self._pop_trap()
        self._tui.refresh()

    def detach(self) -> None:
        """Unregister the overlay and close the panel (the ``EveryHandle`` convention).

        By identity, and idempotent: nothing is unregistered when the frame
        no longer holds the modal, so a second detach is a no-op.  Unlike
        :meth:`close`, detach also clears the open state and the pending
        result -- a detached modal paints nothing, consumes nothing
        (:meth:`handle` answers ``False``) and has no result left to read --
        and it pops the focus trap it pushed.  Detaching is final:
        ``open()`` never re-registers.
        """
        if self._detached:
            return
        self._detached = True
        self._open = False
        self._result = None
        self._pop_trap()
        if self in self._tui.frame.overlays:
            self._tui.frame.remove_overlay(self)

    def take_result(self) -> object | None:
        """Read the pending result once and clear it.

        The one-shot result door every panel of the tier speaks: ``None``
        for a cancel, a dismissal or a programmatic :meth:`close`, and the
        value a button took otherwise (``None`` is a legal value, so the
        routing tells a decision from no decision before it lands here).
        """
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
        """Re-skin the scrim and the dialog in place.

        The scrim follows the new theme unless the host pinned an explicit
        ``scrim_style``; a dialog that is a :class:`Widget` takes the theme
        (its subtree keeps whatever explicit themes it was built with).
        A closed modal paints nothing, so the repaint cue is harmless.
        """
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
        """Route ``event`` into the panel; ``True`` whenever the modal is open.

        The consume-a-key contract every controller of the tier follows,
        with the modal's own answer: open, the event is the modal's whatever
        it is -- a left press decides (inside the panel it is the panel's
        click, outside it is a dismissal), every other report is swallowed,
        a key goes to the exchanging routing below and a
        :class:`~motui.kernel.events.PasteEvent` to the body.  Closed, the
        answer is ``False`` and nothing is touched.
        """
        if self._detached or not self._open:
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
        self._result = None
        if event.kind != "press" or event.button != "left":
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

    def _key(self, event: Event) -> bool:
        """Route one key or paste into the panel; always consumed (the modal).

        Body-first: a panel's ``body`` with a ``handle`` gets the event and,
        taking it, keeps it -- an input field's editing keys, its pastes and
        its own ``enter`` where it binds one.  What the body left alone goes
        to the panel's own ``handle``: a **key** always (the dialog's button
        row), a **paste** only when the panel is its own whole keyboard (no
        ``body`` -- the CommandPalette's panel; a dialog's own handle is the button
        row's surface and reads keys alone).  A decision either of them
        leaves in the panel's one-shot result closes the modal with it (the
        value, ``None`` included); otherwise a key nobody took is the
        panel's ``escape`` --
        the cancel -- and every other event is consumed and dropped, so the
        host's shortcuts never fire under an open modal.  Nothing here can
        answer ``False``: the modal owns the keyboard.
        """
        dialog = self._dialog
        body = getattr(dialog, "body", None)
        keys = isinstance(event, KeyEvent)
        self._arm()
        consumed = False
        if body is not None and hasattr(body, "handle"):
            consumed = bool(body.handle(event))
        if not consumed and (keys or body is None):
            handle = getattr(dialog, "handle", None)
            if handle is not None:
                consumed = bool(handle(event))
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

    def _arm(self) -> None:
        """Discard any pending panel result before one routing."""
        take_decision = getattr(self._dialog, "_take_decision", None)
        if take_decision is not None:
            take_decision()
            return
        take_result = getattr(self._dialog, "take_result", None)
        if take_result is not None:
            take_result()

    def _collect(self) -> object:
        """The routing's decision, or ``_PENDING`` when it made none.

        A panel that can decide a ``None`` value implements the private
        ``_take_decision()`` (the dialog does); every other ``Resultful``
        panel answers through ``take_result()``, whose ``None`` is "nothing
        pending" -- a menu's take is always an option.
        """
        take_decision = getattr(self._dialog, "_take_decision", None)
        if take_decision is not None:
            made, value = take_decision()
            return value if made else _PENDING
        take_result = getattr(self._dialog, "take_result", None)
        if take_result is not None:
            value = take_result()
            return value if value is not None else _PENDING
        return _PENDING

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
        rows = [row.fit(rect.width) for row in self._dialog.render(Constraints(width=rect.width))]
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
