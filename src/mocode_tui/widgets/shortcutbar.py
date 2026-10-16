"""ShortcutBar: the key hints -- one row of ``key label`` pairs.

A shortcut bar is chrome, not a control: one row listing the session's keys
and what each does -- ``c-n next \u00b7 c-p prev \u00b7 / palette`` -- every
key in ``key_style`` (the theme's ``accent``), every label in
``label_style`` (the theme's ``dim``), the pairs joined by ``separator``.
It renders through the same frozen protocol as everything else and is
``fit`` to the painting width, so a bar too wide for its pane truncates
with the usual ``\u2026``: the bar shows as many hints as fit and stops --
there is no wrapping and no interaction: no ``chosen``, no controller
methods, no capability flags.
"""

from __future__ import annotations

from typing import Sequence

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed

__all__ = ["ShortcutBar"]


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
