"""The one object every markdown rule reads while rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...kernel.glyphs import GLYPHS, Glyphs
from ...kernel.text import WrapMode
from ...kernel.theme import DEFAULT_THEME, Theme
from ..syntax import Highlighter

if TYPE_CHECKING:  # the registries are typed, never imported, here
    from .blocks import BlockRule
    from .inline import InlineRule


@dataclass(frozen=True)
class RenderContext:
    """Everything a rule reads while rendering, frozen and shared.

    ``theme``/``highlighter`` are resolved by the component; the registries
    are the document's live ones so nested rendering follows custom rules.
    ``glyphs`` is the structural vocabulary and ``code_wrap`` the fence row
    policy.
    """

    theme: Theme = DEFAULT_THEME
    highlighter: Highlighter | None = None
    glyphs: Glyphs = GLYPHS
    divider_max_width: int | None = 80
    block_rules: Sequence[BlockRule] = ()
    inline_rules: Sequence[InlineRule] = ()
    code_wrap: WrapMode = WrapMode.WORD
