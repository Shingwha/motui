"""Menus: the horizontal :class:`MenuBar` and the :class:`ContextMenu` preset.

:class:`MenuBar` is the one-row horizontal menu strip -- a desktop menu bar's
top level: ``" File │ Edit │ View "``, the labels separated by ``" " + glyphs.vertical_rule + " "``,
leading and trailing one-column padding, the whole
row ``fit`` to the painting width.  Exactly one label is the bar's *active*
label: it wears ``content.accent`` with **no
underline** -- the colour is the whole indicator -- while every other label
rests in ``text.faint``, a disabled label in
``text.faint`` as well and every divider in
``text.muted`` (a separator is never accent).  The
label under the pointer merges ``surfaces.hover`` over
its own style; a disabled label keeps its disabled style (the stricter state
wins over the pointer's echo).

The cursor is clamped, never wrapping -- a menu bar is a data strip, not
:class:`~motui.widgets.choice.Select`'s cycling menu: :meth:`MenuBar.move`
stops at the ends, steps over ``disabled_items`` and clears a stale pending
result, :meth:`MenuBar.select` clamps and refuses a disabled index, and
:meth:`MenuBar.on_click` / :meth:`MenuBar.on_hover` resolve a cell against the
span table of the component's **last render** (the leading and trailing
padding, every divider gap, a row other than the first and a truncating
``fit`` all carry no label).  ``disabled=True`` refuses every gesture.

:meth:`MenuBar.on_action` is the bar's activation: it leaves the active
label's text pending, and :meth:`MenuBar.take` reads that value once
and clears it.  An empty bar and a disabled bar (or a disabled active label)
answer ``False`` and leave nothing pending.  ``focused`` is the focus flag
the focus tier sets; the bar renders the same whether it is
focused or not -- its active label is the selection, not a focus band -- and
the flag touches the widget all the same.

:class:`ContextMenu` is :class:`~motui.widgets.choice.Select`'s desktop-menu
preset: a vertical option list with the menu cursor, ``commit=False`` (only
:meth:`~motui.widgets.choice.Select.on_action` settles a pick),
``wrap=True`` (the ends cycle) and ``window=False`` (the list window hangs at
the top).  An :meth:`~motui.widgets.choice.Select.on_action` leaves the
option under the cursor pending and :meth:`~motui.widgets.choice.Select.take`
reads it once.  The menu itself neither opens nor positions itself; a host
mounts it over a click with a modal controller --
``Modal(tui, menu, anchor=(y, x))`` -- routes the pointer through the modal
and calls ``menu.on_action("activate")`` on the return key.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Sequence

from ..widgets.cursor import Cursor
from ..kernel.events import KeyEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..kernel.text import WrapMode
from .choice import Option, Select
from .strip import Keymap, LabelStrip

__all__ = ["ContextMenu", "MenuBar"]


class MenuBar(LabelStrip):
    """A horizontal menu bar: one row, one active label, a clamped cursor.

    ``items`` is the label sequence; ``index`` is the active label (read-only
    property) and is clamped into ``0..len(items)-1`` on construction and on
    every later :meth:`select`/:meth:`move` (a disabled index passed to the
    constructor is kept -- the constructor rewrites no explicit request, the
    verbs refuse).  ``disabled_items`` names the labels that are visible but
    refuse :meth:`select`/:meth:`on_click`/:meth:`on_action` and are stepped over
    by :meth:`move`; the ``disabled`` flag refuses every gesture.

    Styles resolve at render time from the theme (or a ``styles=`` group
    override): ``content.accent`` paints the active label (never
    underlined), ``text.faint`` the inactive and disabled ones,
    ``surfaces.hover`` the label under the pointer and ``text.muted`` the
    dividers.
    ``glyphs.vertical_rule`` is the separator between labels, padded with one
    space per side; an empty glyph collapses the gap.  ``focused`` starts
    ``True``, the old default.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry :meth:`on_click` maps a column against; until the first paint it is
    80, the same convention as ``Tabs``/``TextBuffer.last_width``.  The span
    table is recorded once per render, so a hit never re-renders the bar.
    """

    __slots__ = ("_pending", "items")

    #: A bar activates its active label (unlike a tab strip, which only selects).
    activatable = True

    #: The default key table (a per-instance copy backs ``self.keymap``).
    keymap = Keymap(
        {
            "up": "prev",
            "down": "next",
            "left": "prev",
            "right": "next",
            "enter": "activate",
        }
    )

    def __init__(
        self,
        items: Sequence[str],
        *,
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled_items: Iterable[int] = (),
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.items = list(items)
        self.glyphs = glyphs
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the label-level emphasis lives in
        #: ``_hover_index`` (:meth:`on_hover`).
        self.hover = False
        #: The whole bar refuses every gesture when disabled.
        self.disabled = disabled
        self._index = 0
        # The label the pointer is on, or ``None``; written by ``on_hover``,
        # read by ``render``.  ``None`` renders byte-for-byte what the bar
        # always did.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable.
        self._disabled_items = frozenset(disabled_items)
        # The width ``click`` maps against before the first paint (the same
        # 80 as ``Tabs``/``TextBuffer.last_width``); every render refreshes it.
        self._last_width = 80
        # The label spans of the last render -- ``(start, stop, index)`` per
        # label, in paint order -- so a hit reads the table instead of
        # re-rendering the bar.
        self._spans: tuple[tuple[int, int, int], ...] | None = None
        #: The pending one-shot result: written by activation, read once by
        #: ``take``.
        self._pending: str | None = None
        if self.items:
            # Clamped like every later request; the disabled rule belongs to
            # the verbs, not to this explicit constructor value.
            self._index = Cursor(len(self.items)).clamp(index)

    @property
    def _entries(self) -> list[str]:
        """The menu labels every cursor verb and the span walk measure."""
        return self.items

    def move(self, delta: int) -> bool:
        """Move the active label ``delta`` labels, clamped and never wrapping.

        The cursor rule is :meth:`~motui.widgets.strip.LabelStrip.move`:
        disabled indices are stepped over, the ends clamp and never wrap.  A
        moved step clears a stale pending result -- an activation never
        survives the next keystroke.  A disabled or empty bar moves nowhere.
        """
        moved = super().move(delta)
        if moved:
            self._pending = None
        return moved

    def take(self) -> str | None:
        """Read the pending label once and clear it (the ``take`` door)."""
        value = self._pending
        self._pending = None
        return value

    # -- the keyboard -----------------------------------------------------------

    def on_action(self, name: str) -> bool:
        """Run one named bar action; ``False`` for an unknown name.

        ``prev`` / ``next`` step the active label through :meth:`move` and
        answer its result (a clamped edge reports ``False``, the old focus
        router's rule); ``activate`` leaves the active label pending through
        :meth:`on_action` and answers whether there was one.  An unknown name
        answers ``False`` without touching the bar.
        """
        if name == "prev":
            return self.move(-1)
        if name == "next":
            return self.move(1)
        if name == "activate":
            if self.disabled or not self.items or self._index in self._disabled_items:
                self._pending = None
                return False
            self._pending = self.items[self._index]
            return True
        return False

    def on_key(self, event: KeyEvent) -> bool:
        """Route a key through :attr:`keymap` to :meth:`on_action`.

        The default table binds the four arrows and ``enter``; a key no
        entry names is declined so the host keeps it.  A disabled bar
        answers ``False``.
        """
        if self.disabled or not isinstance(event, KeyEvent):
            return False
        action = self.keymap.get(event.key)
        if action is None:
            return False
        return self.on_action(action)

    def _style_of(self, index: int) -> Style:
        """The style one label renders with (the stricter state wins)."""
        if index in self._disabled_items:
            return self.group("text").faint
        if index == self._index:
            style = self.group("content").accent
        else:
            style = self.group("text").faint
        if index == self._hover_index:
            style = style.merge(self.group("surfaces").hover)
        return style

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The bar's fitted row and the label span table, in one build."""
        if not self.items:
            return Line(), ()
        divider_style = self.group("text").muted
        segments: list[Segment] = [Segment(" ")]
        for i, label in enumerate(self.items):
            if i:
                segments.append(
                    Segment(f" {self.glyphs.vertical_rule} ", divider_style)
                )
            segments.append(Segment(label, self._style_of(i)))
        segments.append(Segment(" "))
        line = Line(segments).clip(WrapMode.ELLIPSIS, width)
        return line, self._spans_of(line)

    def __repr__(self) -> str:
        return f"MenuBar({self.items!r}, index={self._index})"


class ContextMenu(Select):
    """A :class:`~motui.widgets.choice.Select` preset for a desktop context menu.

    ``options`` are :class:`~motui.widgets.choice.Option` values (a payload
    rides through untouched), ``title`` is the optional heading row and
    ``marker`` the cursor row's glyph (the vocabulary's ``cursor``,
    ``"\u2192"``).  The preset's knobs are a desktop menu's: ``commit=False``
    (moving the cursor picks nothing -- only :meth:`~motui.widgets.choice.Select.on_action`
    settles the option under it), ``wrap=True`` (the ends cycle) and
    ``window=False`` (a window longer than ``max_rows`` hangs at the top).
    They may still be overridden through ``**kwargs``, which forwards every
    other :class:`~motui.widgets.choice.Select` parameter.

    The menu neither opens nor positions itself: a host mounts it with the
    modal controller at the click cell -- ``Modal(tui, menu, anchor=(y, x))``
    -- routes the pointer reports through the modal (a click inside the panel
    lands the cursor, a click outside dismisses), calls ``menu.on_action("activate")``
    on the return key and reads the choice once through
    :meth:`~motui.widgets.choice.Select.take`, which answers the
    pending :class:`~motui.widgets.choice.Option` (or ``None`` for a cancel).
    """

    __slots__ = ()

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int = 8,
        glyphs: Glyphs = GLYPHS,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("commit", False)
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("window", False)
        super().__init__(
            options,
            title=title,
            max_rows=max_rows,
            glyphs=glyphs,
            **kwargs,
        )
