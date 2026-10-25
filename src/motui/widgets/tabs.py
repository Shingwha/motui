"""Tabs: the horizontal content strip -- one row, one underline indicator.

:class:`Tabs` is the strip a content view switch wears: exactly one row of
``" a \\u2502 b \\u2502 c "`` -- one space of breathing room at both ends,
the labels joined by ``" " + glyphs.vertical_rule + " "``, the whole row ``fit`` to the
painting width so a narrow screen truncates with an ellipsis instead of
wrapping.  The active label is the strip's **indicator**: it carries
``content.accent`` merged with the indicator role (``controls.focus``,
whose default underline is one hue with the mark) **and the underline
mark** -- the indicator's shape, which survives every color mode as an SGR
attribute, so an active label reads as active even with the colors off.
The other labels wear ``text.faint``, the
dividers ``text.muted`` -- a separator is never
accent -- and the label under the pointer merges ``surfaces.hover``.

``focused`` is the focus flag the focus tier sets
The focus tier's flag.  While it is ``False`` the
indicator **drops from accent to muted** -- the label is *not* dimmed (the
old reverse-video recipe dimmed it; that behaviour is gone).  The color
rule is worth spelling out because :meth:`~motui.kernel.style.Style.merge`
cannot take "just the foreground": the default indicator is the theme's
``accent`` whole (its ``fg`` *and* its bold flag), so an unfocused strip
composes ``content.accent.merge(text.muted)`` -- ``muted`` whole, the same
rule the ``NavList`` bar follows -- rather than merging something onto
``accent`` and hoping to lower its weight.  The underline mark stays: an
unfocused strip loses the indicator's hue, never the indicator.

``disabled_items`` names the indices that are visible but not selectable:
their label renders in ``text.faint``, so a
disabled label is quiet by default, :meth:`on_click` answers ``False``
without touching the selection, and :meth:`move` **steps over** them --
a step towards a disabled index lands on the next enabled one, and a step
with no enabled index left in that direction stays put.  :meth:`select`
onto a disabled index answers ``False`` and changes nothing.  A pointer
over a disabled label still marks it (the hover band is the pointer's
echo, not a selection), and a disabled index passed as the constructor's
``index`` is kept -- the constructor rewrites no explicit request, the
four verbs above are what refuse.  The ``disabled`` flag is the whole-strip
switch: every selection gesture is refused.

Inactive and disabled labels share ``text.faint`` by default: the
state difference is carried by what the label *can do* (the 2.0 role set
has no separate disabled token; a ``styles=`` override of ``text`` moves
both).

The strip is horizontal, period: the second axis this class used to take
(a one-label-per-row rail) is gone, not aliased -- the vertical navigation
rail is :class:`~motui.widgets.navlist.NavList`.  Pure component: the
host routes keys and cells, ``render`` only draws.  ``_last_width`` is
the width the last :meth:`render` painted at -- the geometry
:meth:`on_click` maps a column against; until the first paint it is 80, the
same convention as ``TextBuffer.last_width``.  :meth:`on_click` and the
pointer tier's :meth:`on_hover` resolve a cell through the one walk
:meth:`_hit` runs over this component's own last render, so the host
never resolves a tab itself: the leading and trailing padding, every
``" rule "`` gap, a cell past the last label and a truncating ``fit``
answer no tab.  The marking starts ``None``, so an un-hovered strip
renders exactly the bytes it always did.
"""

from __future__ import annotations

from typing import Iterable

from ..widgets.cursor import Cursor
from ..kernel.events import KeyEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..kernel.text import WrapMode
from .strip import Keymap, LabelStrip

__all__ = ["Tabs"]

#: The horizontal indicator's shape: the active label underlines its own
#: cells (D2).  It is composed onto the label whatever the colors say, so
#: "active" reads with the terminal's colors off.
UNDERLINE = Style(underline=True)


class Tabs(LabelStrip):
    """A horizontal content strip: one row, a clamped, non-wrapping selection.

    ``tabs`` is a list of labels; ``index`` is the selected index (read-only
    property), clamped
    into ``0..len(tabs)-1`` on construction (a disabled index passed there
    is kept: see the module docstring) and on every later
    :meth:`select`/:meth:`move`.  ``disabled_items`` is an iterable of indices
    that render but refuse :meth:`on_click`/:meth:`select` and are stepped
    over by :meth:`move`; the ``disabled`` flag refuses every gesture.

    Styles resolve at render time from the theme (or a ``styles=`` group
    override): ``content.accent`` paints the active label,
    ``text.faint`` the inactive and disabled ones,
    ``surfaces.hover`` the label under the pointer, ``text.muted`` the
    dividers and the separator glyph is ``glyphs.vertical_rule``; the
    indicator's color is ``controls.focus`` -- so the default active label
    is one hue, marked by the underline.  While ``focused`` is ``False`` the
    indicator composes ``text.muted`` (whole) instead; the label's own
    style is untouched.  ``focused`` starts ``True``, the old default.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry :meth:`on_click` maps a column against; until the first paint it
    is 80, the same convention as ``TextBuffer.last_width``.  The marking
    starts ``None``, so an un-hovered strip renders exactly the bytes it
    always did.
    """

    __slots__ = ("tabs",)

    #: The default key table (a per-instance copy backs ``self.keymap``).
    keymap = Keymap(
        {
            "up": "prev",
            "down": "next",
            "left": "prev",
            "right": "next",
        }
    )

    def __init__(
        self,
        tabs: list[str],
        *,
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled_items: Iterable[int] = (),
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.tabs = list(tabs)
        self.glyphs = glyphs
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the label-level emphasis lives in
        #: ``_hover_index`` (:meth:`on_hover`).
        self.hover = False
        #: The whole strip refuses every selection gesture when disabled.
        self.disabled = disabled
        self._index = 0
        # The label the pointer is on, or ``None``; written by ``on_hover``,
        # read by ``render``.  ``None`` renders byte-for-byte what the strip
        # always did.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable; a frozenset so
        # ``click``/``select``/``move`` are one membership test apiece.
        self._disabled_items = frozenset(disabled_items)
        # The width ``click`` maps against before the first paint (same 80 as
        # ``TextBuffer.last_width``); every render refreshes it.
        self._last_width = 80
        # The label spans of the last render -- ``(start, stop, index)`` per
        # label, in paint order -- so a hit reads the table instead of
        # re-rendering the strip (the P0).  ``None`` until the first paint:
        # the fallback builds the geometry once, without calling ``render``.
        self._spans: tuple[tuple[int, int, int], ...] | None = None
        if self.tabs:
            # Clamped like every later request; the disabled rule belongs to
            # the verbs, not to this explicit constructor value.
            self._index = Cursor(len(self.tabs)).clamp(index)

    @property
    def _entries(self) -> list[str]:
        """The tab labels every cursor verb and the span walk measure."""
        return self.tabs

    # -- the keyboard -----------------------------------------------------------

    def on_action(self, name: str) -> bool:
        """Run one named strip action; ``False`` for an unknown name.

        ``prev`` / ``next`` step the selection one tab through
        :meth:`move` and answer its result -- a clamped edge reports
        ``False``, the old focus router's rule.  A tab strip selects, it
        never activates, so no other action is bound.
        """
        if name == "prev":
            return self.move(-1)
        if name == "next":
            return self.move(1)
        return False

    def on_key(self, event: KeyEvent) -> bool:
        """Route a key through :attr:`keymap` to :meth:`on_action`.

        The default table binds the four arrows; a key no entry names is
        declined so the host keeps it.  A disabled strip answers ``False``.
        """
        if self.disabled or not isinstance(event, KeyEvent):
            return False
        action = self.keymap.get(event.key)
        if action is None:
            return False
        return self.on_action(action)

    def revision(self) -> object:
        """The row cache's snapshot: every input the strip's row reads.

        In order: the labels (a tuple copy, so an in-place edit of the
        host's list moves it), the index, the disabled item set, the
        whole-control disabled flag, the index under the pointer,
        ``focused``, the glyph vocabulary, the theme and the ``styles``
        overrides (the bands resolve from them at render time).
        The block-level ``hover`` flag paints nothing -- the row emphasis
        lives in ``_hover_index`` -- so it is deliberately out, and
        ``_last_width``/``_spans`` are outputs of ``render``, not inputs.

        The snapshot is plain immutable values and costs far less than a
        render; it is what lets a **sealed** strip's hover, focus flip or
        selection reach the screen (D4).
        """
        return (
            tuple(self.tabs),
            self._index,
            self._disabled_items,
            self.disabled,
            self._hover_index,
            self.focused,
            self.glyphs,
            self.theme,
            self.styles,
        )

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The strip's fitted row and the label span table, in one build."""
        if not self.tabs:
            return Line(), ()
        # The focus rule, once per build: an unfocused strip drops the
        # indicator from accent to muted -- the label is never dimmed (D3).
        indicator = (
            self.group("controls").focus if self.focused else self.group("text").muted
        )
        active_style = self.group("content").accent.merge(indicator).merge(UNDERLINE)
        inactive_style = self.group("text").faint
        disabled_style = self.group("text").faint
        hover_style = self.group("surfaces").hover
        divider_style = self.group("text").muted

        def style_of(index: int) -> Style:
            if index in self._disabled_items:
                style = disabled_style
            else:
                style = active_style if index == self._index else inactive_style
            return style.merge(hover_style) if index == self._hover_index else style

        segments: list[Segment] = [Segment(" ")]
        for i, name in enumerate(self.tabs):
            if i:
                segments.append(
                    Segment(f" {self.glyphs.vertical_rule} ", divider_style)
                )
            segments.append(Segment(name, style_of(i)))
        segments.append(Segment(" "))
        line = Line(segments).clip(WrapMode.ELLIPSIS, width)
        return line, self._spans_of(line)

    def __repr__(self) -> str:
        return f"Tabs({self.tabs!r}, index={self._index})"
