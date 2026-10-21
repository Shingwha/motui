"""The one object every markdown rule reads while rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.glyphs import GLYPHS, Glyphs
from ...core.theme import DEFAULT_THEME, Theme
from ..syntax import Highlighter

if TYPE_CHECKING:  # the registries are typed, never imported, here
    from .blocks import BlockRule
    from .inline import InlineRule


@dataclass(frozen=True)
class RenderContext:
    """Everything a rule reads while rendering, frozen and shared.

    ``theme`` and ``highlighter`` are already resolved by the component (a
    missing theme is :data:`~motui.core.theme.DEFAULT_THEME`, a missing
    highlighter the engine a fence would derive from the theme).  The two
    registries are the *live* ones of the document being rendered: a rule
    that re-runs blocks -- a quote body, a list continuation -- and the
    paragraph catch-all that yields to higher-priority rules both follow
    them, so a custom rule reaches every built-in block without any
    re-binding.  ``glyphs`` is the structural vocabulary the nested rules
    read: the task box's ``check_on`` / ``check_off``, the list ``bullets``
    and the ``quote`` bar, each seated through
    :func:`~motui.core.glyphs.pair_seat` or
    :func:`~motui.core.glyphs.seat` so the states keep one column.
    """

    theme: Theme = DEFAULT_THEME
    highlighter: Highlighter | None = None
    glyphs: Glyphs = GLYPHS
    divider_max_width: int | None = 80
    block_rules: Sequence[BlockRule] = ()
    inline_rules: Sequence[InlineRule] = ()
