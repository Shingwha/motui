"""Progress: the determinate :class:`ProgressBar` component.

The ``Building your own component`` recipe in ``docs/COMPONENTS.md`` grew up
into this library component: a single-row ``[\\u2588\\u2588\\u2588\\u2591\\u2591\\u2591]`` track whose
filled part is ``fraction`` of the whole.  ``label`` prefixes the track
(``"installing \\u2026 "``), ``width_chars`` pins the track width (``None``
fills whatever width ``render`` is given), and the two half-styles default to
the theme's ``success``/``dim``.  ``fraction`` is a mutable attribute that
clamps into ``[0, 1]`` on assignment; the host moves it over time and calls
``invalidate()`` -- ``render`` itself stays a pure function of the component
and ``width``, and always ``fit``\\ s back to the painting width.
"""

from __future__ import annotations

from ..kernel.lines import Line, Segment
from ..kernel.style import Style
from ..kernel.theme import Theme, Themed

__all__ = ["ProgressBar"]


class ProgressBar(Themed):
    """A determinate progress bar: label, ``[``, filled blocks, ``]``.

    ``fraction`` clamps to ``[0, 1]`` (on construction and on every later
    assignment, so ``bar.fraction = 1.4`` reads back ``1.0``).  The track is
    ``width_chars`` columns wide when that is given, otherwise it fills the
    available width minus the label prefix and the two frame cells; the
    filled part is ``round(inner * fraction)`` blocks.  ``done_style``
    (default: the theme's ``success``) paints the filled blocks,
    ``todo_style`` (default: the theme's ``dim``) the empty ones, and the
    label plus frame stay unstyled.  Styles resolve once, at construction,
    as explicit > theme > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_done_style",
        "_fraction",
        "_todo_style",
        "label",
        "theme",
        "width_chars",
    )

    def __init__(
        self,
        fraction: float = 0.0,
        *,
        label: str = "",
        width_chars: int | None = None,
        done_style: Style | None = None,
        todo_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.fraction = fraction
        self.label = label
        self.width_chars = width_chars
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._done_style = self._pick(done_style, "success")
        self._todo_style = self._pick(todo_style, "dim")

    @property
    def fraction(self) -> float:
        """The completed fraction, always clamped into ``[0, 1]``."""
        return self._fraction

    @fraction.setter
    def fraction(self, value: float) -> None:
        self._fraction = min(1.0, max(0.0, value))

    def render(self, width: int) -> list[Line]:
        lead = f"{self.label} " if self.label else ""
        if self.width_chars is None:
            inner = max(0, width - Line.from_text(lead).width - 2)
        else:
            inner = max(0, self.width_chars)
        done = min(inner, int(round(inner * self.fraction))) if inner else 0
        row = Line(
            (
                Segment(lead),
                Segment("["),
                Segment("\u2588" * done, self._done_style),
                Segment("\u2591" * (inner - done), self._todo_style),
                Segment("]"),
            )
        )
        return [row.fit(width)]

    def __repr__(self) -> str:
        return (
            f"ProgressBar(fraction={self.fraction}, label={self.label!r}, "
            f"width_chars={self.width_chars})"
        )
