"""Theme: the frozen dataclass that carries every semantic style default.

Before the restructure each component module defined its own color
constants -- a user band in ``message``, tool/code tone bands in ``tools``,
a grid-line style in ``table`` -- and the markdown engine kept a private
heading ladder.  Those constants now live here, next to the semantic
``style`` constants, as fields of one frozen :class:`Theme` -- the single
place a host edits to restyle the whole toolkit.

Every component takes ``style=...`` (an explicit override, which always
wins) plus ``theme=Theme | None`` (default ``None``).  A component resolves
each style it renders, at render time, as::

    explicit style parameter  >  theme field  >  DEFAULT_THEME field

so ``Theme()`` -- :data:`DEFAULT_THEME` -- reproduces the pre-Theme
defaults byte for byte.  Build a variant with :func:`dataclasses.replace`
(``replace(DEFAULT_THEME, accent=Style(fg="#ff0000"))``) and hand it to the
components you build; nothing global is mutated.

The four structural tables (``headings``, ``tones``, ``title_tones``,
``notice_levels``) are **derived** from this theme's own colors when the
theme is built -- the heading ladder from ``heading``/``muted``, the tone
tables from ``tool_bg``/``code_bg``/``success``, the notice levels from
``warning``/``error`` -- so replacing one color restyles every structure
that reads it.  They are ordinary (frozen-dataclass) fields: readable and
comparable, rebuilt per theme, and meant to be read, never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .style import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DIM,
    ERROR,
    HEADING,
    INLINE_CODE,
    LINK,
    LIST_MARKER,
    MUTED,
    NONE,
    SELECTION,
    SUCCESS,
    WARNING,
    Style,
)

__all__ = ["DEFAULT_THEME", "Theme"]


@dataclass(frozen=True)
class Theme:
    """Every semantic style the toolkit renders with, in one frozen value.

    The **semantic colors** mirror the :mod:`mocode_tui.core.style`
    constants (``dim`` .. ``selection``, plus the markdown palette
    ``heading``/``link``/``inline_code``/``list_marker``); the
    **component bands** are the colors the widget modules used to define
    themselves (``user_bg``, ``tool_bg``, ``code_bg``, ``table_border``,
    ``first_column``).  The four **structural tables** are derived from
    those colors at construction (see the module docstring) and are
    exposed as read-only fields.

    Instances are frozen: build variants with :func:`dataclasses.replace`
    rather than mutating.  Equality is field-wise, so a custom theme never
    compares equal to :data:`DEFAULT_THEME` unless every field matches.
    """

    # -- semantic colors (the style.py constants) ---------------------------
    dim: Style = DIM
    muted: Style = MUTED
    accent: Style = ACCENT
    success: Style = SUCCESS
    error: Style = ERROR
    warning: Style = WARNING
    border: Style = BORDER
    code: Style = CODE
    cursor: Style = CURSOR
    selection: Style = SELECTION
    heading: Style = HEADING  # the Markdown heading ladder's base
    link: Style = LINK  # link labels: color + underline, never bold
    inline_code: Style = INLINE_CODE  # inline `code` runs
    list_marker: Style = LIST_MARKER  # list bullets / numbers

    # -- component bands (the old per-module constants) ----------------------
    user_bg: Style = Style(bg="#1c2b3a")  # the user-turn band
    tool_bg: Style = Style(bg="#16281c")  # the "tool" tone band
    code_bg: Style = Style(bg="#12181f")  # the "code" tone / EditBlock band
    table_border: Style = NONE  # grid lines: uncolored
    first_column: Style = NONE  # Table first column: plain by default

    # -- structural tables (derived from the colors above) --------------------
    headings: tuple[Style, ...] = field(init=False)
    tones: dict[str, Style] = field(init=False)
    title_tones: dict[str, Style] = field(init=False)
    notice_levels: dict[str, tuple[str, Style]] = field(init=False)

    def __post_init__(self) -> None:
        """Derive the structural tables from this theme's own colors."""
        # Heading ladder: decreasing prominence with depth -- the gold
        # heading color for the top levels, settling into muted, muted-dim,
        # and dim-italic for h6 (the old markdown._HEADING_STYLES).  No
        # bold, no underline: weight stays reserved for **...** syntax and
        # underline for links, so the ladder reads by color alone.
        object.__setattr__(
            self,
            "headings",
            (
                self.heading,
                self.heading,
                self.heading.merge(Style(dim=True)),
                self.muted.merge(Style(dim=True)),
                self.muted.merge(Style(dim=True)),
                self.muted.merge(Style(dim=True, italic=True)),
            ),
        )
        # ``tone`` -> band style for ToolBlock; anything unknown degrades to
        # no band, like ``"plain"`` (the old tools._TONES).
        object.__setattr__(
            self,
            "tones",
            {"tool": self.tool_bg, "code": self.code_bg, "plain": NONE},
        )
        # ToolBlock title overrides per tone: the "tool" band carries a green
        # bold title, every other tone falls back to ``band.merge(bold)``
        # (the old tools._TITLE_TONES).
        object.__setattr__(
            self,
            "title_tones",
            {"tool": self.tool_bg.merge(self.success).merge(Style(bold=True))},
        )
        # Row prefixes and styles for the non-info notice levels (the old
        # chrome._NOTICE_LEVELS).
        object.__setattr__(
            self,
            "notice_levels",
            {
                "warn": ("WARNING: ", self.warning),
                "error": ("ERROR: ", self.error),
            },
        )


#: The shipped palette: what every component falls back to.  ``Theme()``.
DEFAULT_THEME = Theme()
