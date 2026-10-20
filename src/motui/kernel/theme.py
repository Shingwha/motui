"""Theme: the frozen dataclass that carries every semantic style default.

Every color the toolkit renders with has one home here: the semantic
constants of :mod:`motui.kernel.style` (``dim`` .. ``selection``, plus the
markdown palette), the band tokens (``caret``, ``ground``,
``ground_active``, ``hover`` -- ``NONE`` by default, the host's to theme),
the component bands
(``table_border``, ``first_column``), the pane-chrome bands
(``scrollbar`` / ``scrollbar_thumb``) and the overlay band (``toast``) -- the
single place a host edits to restyle the whole toolkit.

Every component takes ``style=...`` (an explicit override, which always
wins) plus ``theme=Theme | None`` (default ``None``).  A component resolves
each style it renders as::

    explicit style parameter  >  theme field  >  DEFAULT_THEME field

so ``Theme()`` -- :data:`DEFAULT_THEME` -- is the toolkit's default
rendering.  Build a variant with :func:`dataclasses.replace`
(``replace(DEFAULT_THEME, accent=Style(fg="#ff0000"))``) and hand it to the
components you build; nothing global is mutated.

The resolution rule lives in one base class: :class:`Themed` stores the
resolved theme once, at construction, and picks each style with
``_pick(explicit, field)``.  Stateless styles resolve once, in ``__init__``;
the few styles a host may restyle in place (a divider's label) resolve
per render, against the same stored theme.

The two structural tables (``headings``, ``notice_levels``) are **derived**
from this theme's own colors when the theme is built -- the heading ladder
from ``heading``, the notice levels from ``warning``/``error`` -- so
replacing one color restyles every structure that reads it.  They are
read-only properties over one private derived-cache field: readable and
comparable through the colors they follow, rebuilt per theme, and immutable --
an assignment raises ``TypeError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import NamedTuple

from .style import (
    ACCENT,
    BORDER,
    CODE,
    DIM,
    ERROR,
    FOCUS,
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

__all__ = ["DEFAULT_THEME", "Theme", "Themed"]


class _Tables(NamedTuple):
    """The two structural tables, derived once from one theme's colors."""

    headings: tuple[Style, ...]
    notice_levels: Mapping[str, tuple[str, Style]]


@dataclass(frozen=True)
class Theme:
    """Every semantic style the toolkit renders with, in one frozen value.

    The **semantic colors** mirror the :mod:`motui.kernel.style`
    constants (``dim`` .. ``selection``, plus the markdown palette
    ``heading``/``link``/``inline_code``/``list_marker``); the
    **component bands** are the widget-level surfaces (``table_border``,
    ``first_column``); the
    **pane-chrome bands** are the scrollbar's track
    and thumb (``scrollbar``/``scrollbar_thumb``); the **overlay bands**
    are the toast's band (``toast``).  The **band vocabulary** is one
    token per role and defaults to ``NONE``: ``ground`` the resting
    surface, ``ground_active`` the engaged row surface the keyboard cursor
    row wears, ``hover`` the pointer band the pointer tier paints while
    the pointer is over a component, ``focus`` the band a focused control
    paints, ``selection`` the text selection's own band and ``caret`` the
    text caret's own block.  The band family is the host's to theme -- the
    toolkit owns no screen of its own and assumes no background, so a
    transparent terminal, a light terminal and a custom theme are all
    safe -- and a default render therefore paints structure and position
    only.  Three values are the carve-outs that keep a default, all of
    them position or text semantics rather than feedback: ``caret`` (the
    insertion point's one cell, the only terminal-independent way to show
    it), ``focus`` (the keyboard position band, which predates this
    taxonomy) and ``selection`` (the text selection's own semantics).
    ``hover`` is a separate mechanism from ``selection`` even where the
    two render identically, and a component that highlights on hover
    resolves it with an explicit ``hover_style=`` override winning over
    the theme field.  The two
    **structural tables** are derived from those colors at construction
    (see the module docstring) and are exposed as read-only properties.

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
    focus: Style = FOCUS  # the focused control's band
    selection: Style = SELECTION
    heading: Style = HEADING  # the Markdown heading ladder's base
    link: Style = LINK  # link labels: color + underline, never bold
    inline_code: Style = INLINE_CODE  # inline `code` runs
    list_marker: Style = LIST_MARKER  # list bullets / numbers
    # -- the band family: NONE by default, the host's to theme -------------
    hover: Style = NONE  # pointer hover: the pointer tier's own highlight
    caret: Style = Style(reverse=True)  # the text caret's own block
    ground: Style = NONE  # the resting surface
    ground_active: Style = NONE  # the engaged row surface (the keyboard cursor row)

    # -- component bands -----------------------------------------------------
    table_border: Style = NONE  # grid lines: uncolored
    first_column: Style = NONE  # Table first column: plain by default

    # -- pane chrome (the Scrollbar's bands) ----------------------------------
    scrollbar: Style = DIM  # the scrollbar's track
    scrollbar_thumb: Style = NONE  # the scrollbar's thumb

    # -- overlay bands (the Toasts band) ----------------------------------------
    toast: Style = Style(reverse=True, dim=True)  # the toast band: reverse video, dimmed

    # -- derived cache (the two structural tables, one write) ----------------
    _tables: _Tables = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Derive the structural tables from this theme's own colors."""
        # Heading ladder: one gold for every level -- the reference palette's
        # flat ladder reads by color alone, so nothing dims; only h1
        # underlines.  No bold: weight stays reserved for **...** syntax.
        headings = (self.heading.merge(Style(underline=True)), *(self.heading,) * 5)
        # Row prefixes and styles for the non-info notice levels.  The table
        # is exposed read-only: a theme is a value, and one component editing
        # another's table would restyle a whole application by accident.
        notice_levels = MappingProxyType(
            {
                "warn": ("WARNING: ", self.warning),
                "error": ("ERROR: ", self.error),
            }
        )
        object.__setattr__(self, "_tables", _Tables(headings, notice_levels))

    @property
    def headings(self) -> tuple[Style, ...]:
        """The Markdown heading ladder: ``headings[0]`` underlines, all one hue."""
        return self._tables.headings

    @property
    def notice_levels(self) -> Mapping[str, tuple[str, Style]]:
        """Non-info level to ``(prefix, style)`` for :class:`~motui.widgets.decor.Notice`.

        A read-only mapping: assignment raises ``TypeError``.
        """
        return self._tables.notice_levels


class Themed:
    """Base for components that resolve styles against a theme.

    A themed component stores one resolved theme -- ``theme`` when given,
    :data:`DEFAULT_THEME` otherwise -- and picks each style with
    ``_pick(explicit, field)``: the explicit style wins, otherwise the
    named theme field.  Subclasses resolve their styles in ``__init__`` and
    keep the stored theme for the rare render-time pick (a divider whose
    label a host restyles in place).
    """

    __slots__ = ("_theme",)

    def __init__(self, theme: Theme | None = None) -> None:
        self._theme = theme or DEFAULT_THEME

    def _pick(self, style: Style | None, field: str) -> Style:
        """``style`` when given, else this component's theme field."""
        return style if style is not None else getattr(self._theme, field)


#: The shipped palette: what every component falls back to.  ``Theme()``.
DEFAULT_THEME = Theme()
