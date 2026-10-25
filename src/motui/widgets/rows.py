"""Row-shaped furniture: the status row, the shortcut bar and the notice.

Three one-row components a host pins around its content, one family file:

* :class:`StatusLine` -- a two-column status row: a left part left-aligned,
  a right part right-aligned, a computed gutter between them and one trailing
  column of right margin, so a host that pins it below a viewport keeps a
  constant height no matter what the two sides say.  Each side is a sequence
  of elements, a bare ``str`` or a ``(str, Style)`` tuple, and the whole row
  defaults to ``text.faint`` (a status bar whispers; it never shouts).
* :class:`ShortcutBar` -- the key hints: one row listing the session's keys
  and what each does -- ``c-n next \u00b7 c-p prev \u00b7 / palette`` -- every
  key in ``content.accent``, every label in
  ``text.faint``, the pairs joined by ``separator``.
* :class:`Notice` -- one message row led by a level glyph
  (``i``/``✓``/``!``/``×``), the inline announcement a form or a panel
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
:meth:`~motui.kernel.cell.Line.clip` (``WrapMode.ELLIPSIS``), which
ellipsizes the end.  A narrow
terminal therefore drops the tail of the right-hand information -- typically
the end of a model name or mode -- while the left-hand counters stay
readable.
"""

from __future__ import annotations

from typing import Sequence

from ..kernel.glyphs import GLYPHS, Glyphs, seat
from ..kernel.cell import Line, Segment, Surface, fuse
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode, visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

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


class StatusLine(Widget):
    """A dim two-sided status row: left text, right text, gutter between.

    ``left``/``right`` are sequences of :data:`Element` values updated in
    place by the host; the bare elements and the gutter share the
    ``text.faint`` band, resolved at render time from ``styles`` (when
    given) or the theme.  Rendering always
    yields exactly one row, ``fit`` to ``width``: the left part starts at
    column 0, the right part ends one column short of ``width`` (the right
    margin), and the gutter absorbs the difference -- at least one column
    wide, so the two sides never touch.  An over-wide row keeps the left
    part and ellipsizes the right part's tail (see the module docstring).
    """

    __slots__ = ("left", "right")

    def __init__(
        self,
        *,
        left=(),
        right=(),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # A tuple copy: a host that mutates its own list in place would
        # otherwise bypass the snapshot and freeze a sealed block.
        self.left = tuple(left)
        self.right = tuple(right)

    def revision(self) -> object:
        """The :class:`~motui.kernel.document.Revisioned` snapshot.

        The two sides as tuples (taken at construction, so the host cannot
        mutate one behind the snapshot's back) and the theme/styles pair the
        bands resolve from -- everything :meth:`render` reads.
        """
        return (self.left, self.right, self.theme, self.styles)

    def render(self, c: Constraints) -> Surface:
        """The one status row, fitted to the constraint width.

        The row is :meth:`Surface.clipped`, so short rows keep the bytes
        they always had, and a ``max_height`` of zero paints no row.
        """
        default = self.group("text").faint
        gap_style = default
        used = _width(self.left, default) + _width(self.right, default)
        gutter = max(1, c.width - used - 1)  # one trailing column of right margin
        parts = [*self.left, (" " * gutter, gap_style), *self.right]
        rows = [_row(parts, default).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"StatusLine(left={self.left!r}, right={self.right!r})"


class ShortcutBar(Widget):
    """One row of ``(key, label)`` hints, truncated to the painting width.

    ``items`` is a sequence of ``(key, label)`` pairs; each pair renders as
    the key, one space and the label, and neighbouring pairs are joined by
    ``separator`` (``" \u00b7 "`` by default: one space, the middot, one
    space).  An empty bar renders one empty row -- a bar is chrome; it owns
    exactly one row whatever it holds (the ``Tabs`` precedent).  The key
    band is ``content.accent`` and the label band ``text.faint``, resolved
    at render time from ``styles`` (when given) or the theme; the separator
    renders unstyled.
    """

    __slots__ = (
        "glyphs",
        "items",
    )

    def __init__(
        self,
        items: Sequence[tuple[str, str]],
        *,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # A tuple copy of the sequence (same rationale as StatusLine).
        self.items = tuple((key, label) for key, label in items)
        self.glyphs = glyphs

    def revision(self) -> object:
        """The :class:`~motui.kernel.document.Revisioned` snapshot.

        The item pairs (a tuple copy), the glyph vocabulary and the
        theme/styles pair the two bands resolve from.
        """
        return (
            self.items,
            self.glyphs,
            self.theme,
            self.styles,
        )

    def render(self, c: Constraints) -> Surface:
        """The one hint row, fitted to the constraint width.

        The row is :meth:`Surface.clipped`, so short rows keep the bytes
        they always had, and a ``max_height`` of zero paints no row.
        """
        key_style = self.group("content").accent
        label_style = self.group("text").faint
        segments: list[Segment] = []
        for index, (key, label) in enumerate(self.items):
            if index:
                segments.append(Segment(self.glyphs.separator, NONE))
            segments.append(Segment(key, key_style))
            segments.append(Segment(f" {label}", label_style))
        rows = [Line(segments).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"ShortcutBar({self.items!r})"


class Notice(Widget):
    """A one-row message with a level glyph.

    Every level leads with the vocabulary's glyph seated in one column:
    ``notice_info`` for ``info`` (and any unknown level, which degrades to
    info rather than raising), ``notice_success`` for ``success``,
    ``notice_warn`` for ``warn`` and ``notice_error`` for ``error``.  The
    glyph carries the level's semantic style (``text.base`` for info,
    ``status.success`` / ``status.warning`` / ``status.danger`` otherwise),
    resolved at render time from ``styles`` (when given) or the theme;
    the message text stays plain.  The row is a single line: it is truncated
    (never wrapped) to ``width``.
    """

    __slots__ = ("glyphs", "level", "text")

    def __init__(
        self,
        text: str,
        *,
        level: str = "info",
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.text = text
        self.level = level
        self.glyphs = glyphs
        # The level is a plain (mutable) attribute, so the pick is
        # state-dependent: the level is looked up per render.

    def revision(self) -> object:
        """The :class:`~motui.kernel.document.Revisioned` snapshot.

        The text, the level (resolved per render), the glyph vocabulary and
        the theme/styles pair the level band resolves from.
        """
        return (self.text, self.level, self.glyphs, self.theme, self.styles)

    def _level_style(self) -> tuple[str, Style]:
        """The ``(glyph, style)`` pair this level renders with."""
        if self.level == "success":
            return self.glyphs.notice_success, self.group("status").success
        if self.level == "warn":
            return self.glyphs.notice_warn, self.group("status").warning
        if self.level == "error":
            return self.glyphs.notice_error, self.group("status").danger
        return self.glyphs.notice_info, self.group("text").base

    def render(self, c: Constraints) -> Surface:
        """The one message row, fitted to the constraint width.

        The row is :meth:`Surface.clipped`, so short rows keep the bytes
        they always had, and a ``max_height`` of zero paints no row.
        """
        glyph, style = self._level_style()
        prefix = seat(glyph)
        if not prefix:
            rows = [Line.from_text(self.text, NONE).clip(WrapMode.ELLIPSIS, c.width)]
        else:
            line = Line((Segment(prefix, style), Segment(self.text, NONE)))
            rows = [line.clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"Notice({self.text!r}, level={self.level!r})"
