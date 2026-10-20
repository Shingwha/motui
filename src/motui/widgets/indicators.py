"""Value indicators: the progress bar, the slider and the spinner.

Three components that show a value, one family file:

* :class:`ProgressBar` -- the determinate bar: a single-row
  ``[\u2588\u2588\u2588\u2591\u2591\u2591]`` track whose filled part is ``fraction``
  of the whole.  ``fraction`` is a mutable attribute that clamps into
  ``[0, 1]`` on assignment; the host moves it over time and calls
  ``refresh()`` -- ``render`` itself stays a pure function of the
  component and ``width``.
* :class:`Slider` -- the numeric control: ``[====----] 4``, a bracketed
  track whose length follows the painting width, the value printed after the
  closing bracket.  The value lives on the ``step`` grid the constructor
  defines; :meth:`Slider.move`, :meth:`Slider.click` (mapped against the
  track of the last render) and :meth:`Slider.activate` are its controller
  doors, and all three write :attr:`Slider.chosen` for the host's one read.
* :class:`Spinner` -- the activity indicator: a frame index cycling around a
  label.  :meth:`Spinner.advance` steps the cycle (wrapping around) and the
  current ``frame`` plus ``text`` are what a host paints -- a working
  indicator rolls them into its label.  The pump's clock decides when
  ``advance`` is called; nothing here reads a clock or a key, and a spinner
  has no styles and no theme -- it draws no color of its own.

The two drawn components render through the frozen protocol and are ``fit``
to the painting width; styles resolve once, at construction, as explicit >
theme field > :data:`~motui.kernel.theme.DEFAULT_THEME`.
"""

from __future__ import annotations

from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed

__all__ = ["DEFAULT_FRAMES", "ProgressBar", "Slider", "Spinner"]

#: The classic braille spinner cycle (each frame is one column wide).
DEFAULT_FRAMES: tuple[str, ...] = (
    "\u280b",
    "\u2819",
    "\u2839",
    "\u2838",
    "\u283c",
    "\u2834",
    "\u2826",
    "\u2827",
    "\u2807",
    "\u280f",
)

#: The filled cell of the slider's track.
FILL = "="

#: The empty cell of the slider's track.
EMPTY = "-"

#: The width the slider's ``click`` maps a column against before the first
#: paint (the same 80-column fallback ``Tabs`` and ``TextBuffer`` use).
DEFAULT_WIDTH = 80


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

    def revision(self) -> object:
        """The row cache's snapshot: every input ``render`` reads.

        The fraction (the filled share), the label prefix, the pinned track
        width (``None``: follow the painting width) and the two resolved
        bands (filled / empty).  This component has no hover or focus state
        and reads no theme at render time, so those are absent by design --
        there is nothing else a row can depend on.  The snapshot is five
        plain values, far cheaper than a render.
        """
        return (
            self._fraction,
            self.label,
            self.width_chars,
            self._done_style,
            self._todo_style,
        )

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


class Slider(Themed):
    """A one-row ``[====----] value`` control over a stepped integer range.

    ``value`` is a read-write attribute: assigning clamps into
    ``[minimum, maximum]`` and snaps onto the ``step`` grid, so the value
    is always one the arrows can reach (an empty range -- ``maximum <=
    minimum`` -- pins it to ``minimum``).  :meth:`move` steps ``delta``
    whole ``step``s (clamped at the ends; a step that moved clears a stale
    :attr:`chosen`), :meth:`click` maps a column of the track onto the grid,
    and :meth:`activate` writes the current value into ``chosen`` for the
    host's one read.

    The track's length follows the painting width: ``[`` and ``]`` plus one
    space and the value's digits are the fixed part, the rest is track
    (a width too narrow for even the brackets truncates through ``fit``).
    ``hover_at`` marks the row (any other row answers "no row" and clears
    the marking; a negative row clears it too), and ``render`` merges the
    theme's ``hover`` band over the marked row.  The marking starts ``None``
    -- or, equivalently, unmarked -- so an un-hovered slider renders
    byte-for-byte what it always did.  ``focused`` is the focus flag the
    focus tier sets (:class:`~motui.kernel.block.Focusable`): while it is
    ``True`` every segment additionally merges ``focus_style`` (the theme's
    ``focus``), so a focused slider is told apart from an unfocused one.
    """

    __slots__ = (
        "_empty_style",
        "_filled_style",
        "_focus_style",
        "_hover_style",
        "_last_width",
        "_marked",
        "_value",
        "chosen",
        "focused",
        "hover",
        "maximum",
        "minimum",
        "step",
        "theme",
    )

    def __init__(
        self,
        value: int = 0,
        *,
        minimum: int = 0,
        maximum: int = 10,
        step: int = 1,
        filled_style: Style | None = None,
        empty_style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_marked`` (:meth:`hover_at`).
        self.hover = False
        # The row is marked while the pointer is on it; written by
        # ``hover_at``, read by ``render``.  Unmarked renders byte-for-byte
        # the same row.
        self._marked = False
        # The width ``click`` maps a column against before the first paint;
        # every render refreshes it.
        self._last_width = DEFAULT_WIDTH
        #: The pending confirmation: written by ``activate`` (the current
        #: value), read once by the host, cleared by a move or a click.
        self.chosen: int | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._filled_style = self._pick(filled_style, "accent")
        self._empty_style = self._pick(empty_style, "dim")
        self._hover_style = self._pick(hover_style, "hover")
        self._focus_style = self._pick(focus_style, "focus")
        self._value = self._align(value)

    # -- the value -------------------------------------------------------------

    def _align(self, value: int) -> int:
        """Clamp ``value`` into range and snap it onto the ``step`` grid."""
        span = self.maximum - self.minimum
        if span <= 0 or self.step <= 0:
            return self.minimum
        steps = int(span // self.step)  # the grid runs 0..steps, not past maximum
        k = int((min(max(value, self.minimum), self.maximum) - self.minimum) / self.step + 0.5)
        return self.minimum + min(max(k, 0), steps) * self.step

    @property
    def value(self) -> int:
        """The current value: always inside ``[minimum, maximum]``, on the grid."""
        return self._value

    @value.setter
    def value(self, value: int) -> None:
        self._value = self._align(value)

    def move(self, delta: int) -> bool:
        """Step the value ``delta`` whole ``step``s, clamped; ``True`` when it moved.

        A step that moved clears a stale :attr:`chosen` -- a pick never
        survives the next move (the ``Select`` precedent).
        """
        target = self._align(self._value + delta * self.step)
        moved = target != self._value
        if moved:
            self._value = target
            self.chosen = None
        return moved

    def click(self, row: int, col: int) -> bool:
        """Position the value by the clicked column; ``True`` on a hit.

        The slider paints one row, so any other ``row`` answers ``False``.
        ``col`` is a 0-based cell of this component's own render, resolved
        against the track of the **last render** (``_last_width``): the
        cell's position over the track's columns becomes the fraction of
        the range, and the value lands on the nearest grid point -- a cell
        at or left of the opening bracket lands on ``minimum``, a cell at
        or past the closing bracket on the largest grid point.  A hit
        clears a stale :attr:`chosen` and answers ``True`` even when the
        value did not move (a click is a hit whether or not it changed
        anything).
        """
        if row != 0:
            return False
        track = self._track(self._last_width)
        if track > 0:
            fraction = min(max((col - 1) / track, 0.0), 1.0)
            self._value = self._align(
                self.minimum + fraction * (self.maximum - self.minimum)
            )
        self.chosen = None
        return True

    def activate(self) -> bool:
        """Confirm the current value into :attr:`chosen`; always ``True``.

        The slider's :class:`~motui.kernel.block.Activable` verb: a host
        routes the return key here, then reads ``chosen`` once -- the slide
        really does always have a value to confirm.
        """
        self.chosen = self._value
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the row under a cell; ``True`` when the marking changed.

        The pointer tier's row-level half: ``row 0`` is the slider's single
        row and every other row -- a negative one included (the pointer
        left) -- clears the marking.  ``col`` is ignored.  The answer is
        whether the marking changed, so a motion inside the row answers
        ``False`` (nothing to repaint); :meth:`render` merges the theme's
        ``hover`` over the marked row.
        """
        target = row == 0
        changed = target != self._marked
        self._marked = target
        return changed

    # -- the track -------------------------------------------------------------

    def _suffix(self) -> str:
        """The value printed after the closing bracket."""
        return f" {self._value}"

    def _track(self, width: int) -> int:
        """The track's column budget at ``width`` (never negative)."""
        return max(0, width - len(self._suffix()) - 2)

    def _filled(self, track: int) -> int:
        """The filled cells of a ``track``-wide run: the round-half-up share."""
        span = self.maximum - self.minimum
        if track <= 0 or span <= 0:
            return 0
        fraction = (self._value - self.minimum) / span
        return min(track, max(0, int(fraction * track + 0.5)))

    def revision(self) -> object:
        """The row cache's snapshot: every input ``render`` reads.

        The value (the suffix and the filled share), the three range fields
        (the span ``_filled`` divides by), the row mark (``_marked``), the
        ``focused`` flag and the four resolved bands.  The block-level
        ``hover`` flag paints nothing -- the row emphasis lives in
        ``_marked`` -- and ``chosen`` / ``_last_width`` are not row inputs,
        so they are deliberately out.  The snapshot is ten plain values,
        far cheaper than a render.
        """
        return (
            self._value,
            self.minimum,
            self.maximum,
            self.step,
            self._marked,
            self.focused,
            self._filled_style,
            self._empty_style,
            self._hover_style,
            self._focus_style,
        )

    def render(self, width: int) -> list[Line]:
        self._last_width = width  # the geometry ``click`` maps a column against
        suffix = self._suffix()
        track = self._track(width)
        filled = self._filled(track)
        segments = [
            Segment("[", NONE),
            Segment(FILL * filled, self._filled_style),
            Segment(EMPTY * (track - filled), self._empty_style),
            Segment("]", NONE),
            Segment(suffix, NONE),
        ]
        if self._marked or self.focused:
            band = self._hover_style if self._marked else NONE
            if self.focused:
                band = band.merge(self._focus_style)
            segments = [seg.with_style(seg.style.merge(band)) for seg in segments]
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        return (
            f"Slider(value={self._value}, minimum={self.minimum}, "
            f"maximum={self.maximum}, step={self.step})"
        )


class Spinner:
    """A frame-cycling activity indicator with an optional label.

    A spinner has no styles and no theme -- it draws no color of its own.
    """

    __slots__ = ("_frame", "frames", "text")

    def __init__(
        self,
        text: str = "",
        *,
        frames: tuple[str, ...] | None = None,
    ) -> None:
        self.text = text
        self.frames = DEFAULT_FRAMES if frames is None else tuple(frames)
        self._frame = 0

    @property
    def frame(self) -> str:
        """The current frame (``""`` when the frame list is empty)."""
        if not self.frames:
            return ""
        return self.frames[self._frame]

    def advance(self) -> None:
        """Step to the next frame, wrapping around at the end of the cycle."""
        if self.frames:
            self._frame = (self._frame + 1) % len(self.frames)

    def __repr__(self) -> str:
        return f"Spinner({self.text!r}, frame={self.frame!r})"
