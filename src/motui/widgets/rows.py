"""Row-shaped furniture: the status row, the shortcut bar and the notice.

Three one-row components a host pins around its content, one family file:

* :class:`StatusLine` -- a two-column status row: a left part left-aligned,
  a right part right-aligned, a computed gutter between them and one trailing
  column of right margin, so a host that pins it below a viewport keeps a
  constant height no matter what the two sides say.  Each side is a sequence
  of elements, a bare ``str`` or a ``(str, Style)`` tuple, and the whole row
  defaults to the theme's ``dim`` (a status bar whispers; it never shouts).
* :class:`ShortcutBar` -- the key hints: one row listing the session's keys
  and what each does -- ``c-n next \u00b7 c-p prev \u00b7 / palette`` -- every
  key in ``key_style`` (the theme's ``accent``), every label in
  ``label_style`` (the theme's ``dim``), the pairs joined by ``separator``.
* :class:`Notice` -- one message row with an optional level prefix
  (``WARNING: `` / ``ERROR: ``), the inline announcement a form or a panel
  carries.

All three render through the frozen protocol and are ``fit`` to the painting
width, so a row too wide for its pane truncates with the usual ``\u2026``
rather than wrapping: a status row, a shortcut bar and a notice own exactly
one row each.  None of them is interactive -- no ``chosen``, no controller
methods, no capability flags.  Only the kernel is imported: layout is
computed here, never drawn.

Overflow ruling for the status row (decided and documented here): the **left
part is preserved first** and the **right part is cut from its tail** -- the
row is composed at full length and closed with the kernel's
:meth:`~motui.kernel.lines.Line.fit`, which ellipsizes the end.  A narrow
terminal therefore drops the tail of the right-hand information -- typically
the end of a model name or mode -- while the left-hand counters stay
readable.
"""

from __future__ import annotations

from typing import Sequence

from ..kernel.lines import Line, Segment, fuse
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed

__all__ = ["Notice", "ShortcutBar", "StatusLine"]

#: One element of a status side: bare text, or text plus an explicit style.
Element = str | tuple[str, Style]


def _element_text(element: Element) -> str:
    """The text of one element (the style half of a tuple is dropped)."""
    return element[0] if isinstance(element, tuple) else element


def _row(elements, default: Style, gap: tuple[str, Style] | None = None) -> Line:
    """One row from ``str | (str, Style)`` elements with an optional middle.

    ``elements`` is one side (or the whole row, see :meth:`StatusLine.render`);
    ``default`` styles the bare strings.  Adjacent elements sharing one
    style are fused into a single segment, so a row of plain text renders
    as one styled run instead of a stutter of identical escapes.
    """
    parts = list(elements)
    if gap is not None:
        parts.append(gap)
    return Line(fuse(
        Segment(text, style)
        for text, style in (
            (element if isinstance(element, tuple) else (element, default))
            for element in parts
        )
        if text  # an empty element contributes nothing at all
    ))


def _width(elements, default: Style) -> int:
    """The display width one side will render at (styles ignored)."""
    return sum(visible_width(_element_text(element)) for element in elements)


class StatusLine(Themed):
    """A dim two-sided status row: left text, right text, gutter between.

    ``left``/``right`` are sequences of :data:`Element` values updated in
    place by the host; ``gap_style`` overrides the gutter's style (the
    theme's ``dim`` by default, same as the elements).  Rendering always
    yields exactly one row, ``fit`` to ``width``: the left part starts at
    column 0, the right part ends one column short of ``width`` (the right
    margin), and the gutter absorbs the difference -- at least one column
    wide, so the two sides never touch.  An over-wide row keeps the left
    part and ellipsizes the right part's tail (see the module docstring).
    """

    __slots__ = ("_default", "_gap_style", "left", "right", "theme")

    def __init__(
        self,
        *,
        left=(),
        right=(),
        theme: Theme | None = None,
        gap_style: Style | None = None,
    ) -> None:
        super().__init__(theme)
        self.left = left
        self.right = right
        self.theme = theme
        # Nothing here depends on mutable state, so both the element default
        # and the gutter style resolve once, at construction (charter:
        # explicit > theme field > DEFAULT_THEME).
        self._default = self._pick(None, "dim")
        self._gap_style = self._pick(gap_style, "dim")

    def render(self, width: int) -> list[Line]:
        default = self._default
        gap_style = self._gap_style
        used = _width(self.left, default) + _width(self.right, default)
        gutter = max(1, width - used - 1)  # one trailing column of right margin
        parts = [*self.left, (" " * gutter, gap_style), *self.right]
        return [_row(parts, default).fit(width)]

    def __repr__(self) -> str:
        return f"StatusLine(left={self.left!r}, right={self.right!r})"


class ShortcutBar(Themed):
    """One row of ``(key, label)`` hints, truncated to the painting width.

    ``items`` is a sequence of ``(key, label)`` pairs; each pair renders as
    the key, one space and the label, and neighbouring pairs are joined by
    ``separator`` (``" \u00b7 "`` by default: one space, the middot, one
    space).  An empty bar renders one empty row -- a bar is chrome; it owns
    exactly one row whatever it holds (the ``Tabs`` precedent).  Styles
    resolve once, at construction, as explicit > theme field >
    ``DEFAULT_THEME``: ``key_style`` falls back to the theme's ``accent``
    and ``label_style`` to the theme's ``dim``; the separator renders
    unstyled.
    """

    __slots__ = (
        "_key_style",
        "_label_style",
        "items",
        "separator",
        "theme",
    )

    def __init__(
        self,
        items: Sequence[tuple[str, str]],
        *,
        separator: str = " \u00b7 ",
        key_style: Style | None = None,
        label_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.items = [(key, label) for key, label in items]
        self.separator = separator
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._key_style = self._pick(key_style, "accent")
        self._label_style = self._pick(label_style, "dim")

    def render(self, width: int) -> list[Line]:
        segments: list[Segment] = []
        for index, (key, label) in enumerate(self.items):
            if index:
                segments.append(Segment(self.separator, NONE))
            segments.append(Segment(key, self._key_style))
            segments.append(Segment(f" {label}", self._label_style))
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        return f"ShortcutBar({self.items!r}, separator={self.separator!r})"


class Notice(Themed):
    """A one-row message with an optional level prefix.

    ``info`` renders the text bare; ``warn``/``error`` prepend
    ``"WARNING: "``/``"ERROR: "`` in the matching semantic style, taken from
    the theme's ``notice_levels`` table.  Any other level degrades to plain
    ``info`` rather than raising.  The row is a single line: it is truncated
    (never wrapped) to ``width``.
    """

    __slots__ = ("level", "text", "theme")

    def __init__(self, text: str, *, level: str = "info", theme: Theme | None = None) -> None:
        super().__init__(theme)
        self.text = text
        self.level = level
        self.theme = theme
        # The level is a plain (mutable) attribute, so the pick is
        # state-dependent: the level is looked up in the stored theme per
        # render.

    def render(self, width: int) -> list[Line]:
        prefix = self._theme.notice_levels.get(self.level)
        if prefix is None:  # info or unknown -> bare row
            return [Line.from_text(self.text).fit(width)]
        label, style = prefix
        line = Line((Segment(label, style), Segment(self.text, NONE)))
        return [line.fit(width)]

    def __repr__(self) -> str:
        return f"Notice({self.text!r}, level={self.level!r})"
