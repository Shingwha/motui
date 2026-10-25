"""Value indicators: the progress bar, the slider and the spinner.

Three components that show a value, one family file:

* :class:`ProgressBar` -- the determinate bar: a single-row
  ``[\u2588\u2588\u2588\u2591\u2591\u2591]`` track whose filled part is ``fraction``
  of the whole.  ``fraction`` is a mutable attribute that clamps into
  ``[0, 1]`` on assignment; the host moves it over time and calls
  ``refresh()`` -- ``render`` itself stays a pure function of the
  component and ``width``.
* :class:`Slider` -- the numeric control: ``[━━━━●───] 4``, a bracketed
  track whose length follows the painting width, the value printed after the
  closing bracket.  The value lives on the ``step`` grid the constructor
  defines; :meth:`Slider.move`, :meth:`Slider.click` (mapped against the
  track of the last render) and :meth:`Slider.activate` are its controller
  doors, and activation leaves the current value pending for
  :meth:`Slider.take_result`.
* :class:`Spinner` -- the activity indicator: a frame index cycling around a
  label.  :meth:`Spinner.advance` steps the cycle (wrapping around) and
  :meth:`Spinner.render` paints the current ``frame`` followed by ``text``
  -- a host adds it to a document like any other component.  The pump's
  clock decides when ``advance`` is called; nothing here reads a clock or a
  key.

The two drawn components render through the frozen protocol and are ``fit``
to the painting width; styles resolve once, at construction, as explicit >
theme field > :data:`~motui.kernel.theme.DEFAULT_THEME`.
"""

from __future__ import annotations

from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment, Surface
from ..kernel.layout import Constraints, as_constraints
from ..kernel.style import NONE
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["ProgressBar", "Slider", "Spinner"]

#: The width the slider's ``click`` maps a column against before the first
#: paint (the same 80-column fallback ``Tabs`` and ``TextBuffer`` use).
DEFAULT_WIDTH = 80


class ProgressBar(Widget):
    """A determinate progress bar: label, ``[``, filled blocks, ``]``.

    ``fraction`` clamps to ``[0, 1]`` (on construction and on every later
    assignment, so ``bar.fraction = 1.4`` reads back ``1.0``).  The track is
    ``width_chars`` columns wide when that is given, otherwise it fills the
    available width minus the label prefix and the two frame cells; the
    filled part is ``round(inner * fraction)`` blocks.  The filled blocks
    carry ``status.success`` and the empty ones ``text.faint``, resolved at
    render time from ``styles`` (when given) or the theme; the
    label plus frame stay unstyled.
    """

    __slots__ = (
        "_fraction",
        "glyphs",
        "label",
        "width_chars",
    )

    def __init__(
        self,
        fraction: float = 0.0,
        *,
        label: str = "",
        width_chars: int | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.fraction = fraction
        self.label = label
        self.width_chars = width_chars
        self.glyphs = glyphs

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
        width (``None``: follow the painting width), the glyphs and the
        theme/styles pair the two bands resolve from.  This component has no
        hover or focus state, so those are absent by design -- there is
        nothing else a row can depend on.  The snapshot is plain values, far
        cheaper than a render.
        """
        return (
            self._fraction,
            self.label,
            self.width_chars,
            self.glyphs,
            self.theme,
            self.styles,
        )

    def render(self, c: Constraints | int) -> Surface:
        """The label-plus-track row, under the render constraints.

        A bare ``int`` is the 1.x width spelling and is normalized through
        :func:`~motui.kernel.layout.as_constraints`; a ``max_height`` budget
        truncates the single row (``0`` paints nothing).  The answer is
        :meth:`~motui.kernel.cell.Surface.clipped`, not padded, so the bytes
        match the old list answer.
        """
        c = as_constraints(c)
        done_style = self.group("status").success
        todo_style = self.group("text").faint
        lead = f"{self.label} " if self.label else ""
        if self.width_chars is None:
            inner = max(0, c.width - Line.from_text(lead).width - 2)
        else:
            inner = max(0, self.width_chars)
        done = min(inner, int(round(inner * self.fraction))) if inner else 0
        row = Line(
            (
                Segment(lead),
                Segment("["),
                Segment(self.glyphs.bar_full * done, done_style),
                Segment(self.glyphs.bar_empty * (inner - done), todo_style),
                Segment("]"),
            )
        )
        rows = [row.fit(c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"ProgressBar(fraction={self.fraction}, label={self.label!r}, "
            f"width_chars={self.width_chars})"
        )


class Slider(Widget):
    """A one-row ``[━━━━●───] value`` control over a stepped integer range.

    ``value`` is a read-write attribute: assigning clamps into
    ``[minimum, maximum]`` and snaps onto the ``step`` grid, so the value
    is always one the arrows can reach (an empty range -- ``maximum <=
    minimum`` -- pins it to ``minimum``).  ``minimum``, ``maximum`` and
    ``step`` are property setters too: assigning any of them re-clamps and
    re-snaps the current value, so the invariant survives a range change.
    :meth:`move` steps ``delta`` whole ``step``s (clamped at the ends; a
    step that moved clears a stale pending value), :meth:`click` maps a
    column of the track onto the grid, and :meth:`activate` leaves the
    current value pending for :meth:`take_result`.  A disabled slider
    refuses all three doors and merges ``text.faint`` over every segment.

    The track's length follows the painting width: ``[`` and ``]`` plus one
    space and the value's digits are the fixed part, the rest is track
    (a width too narrow for even the brackets truncates through ``fit``).
    ``hover_at`` marks the row (any other row answers "no row" and clears
    the marking; a negative row clears it too), and ``render`` merges the
    ``surfaces.hover`` band over the marked row.  The marking starts ``None``
    -- or, equivalently, unmarked -- so an un-hovered slider renders
    byte-for-byte what it always did.  ``focused`` is the focus flag the
    focus tier sets (:class:`~motui.kernel.document.Focusable`): while it is
    ``True`` every segment additionally merges ``controls.focus``, so a
    focused slider is told apart from an unfocused one.  The bands are read
    at render time from ``styles`` (when given) or the theme: filled
    ``content.accent``, empty ``text.faint``, hover ``surfaces.hover``,
    focus ``controls.focus`` and disabled ``text.faint``.
    """

    __slots__ = (
        "_last_width",
        "_marked",
        "_maximum",
        "_minimum",
        "_pending",
        "_step",
        "_value",
        "disabled",
        "glyphs",
    )

    def __init__(
        self,
        value: int = 0,
        *,
        minimum: int = 0,
        maximum: int = 10,
        step: int = 1,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self.glyphs = glyphs
        #: Refuse every cursor gesture and paint the disabled band.
        self.disabled = disabled
        # The row is marked while the pointer is on it; written by
        # ``hover_at``, read by ``render``.  Unmarked renders byte-for-byte
        # the same row.
        self._marked = False
        # The width ``click`` maps a column against before the first paint;
        # every render refreshes it.
        self._last_width = DEFAULT_WIDTH
        #: The pending confirmation: written by ``activate`` (the current
        #: value), read once through :meth:`take_result`, cleared by a move
        #: or a click.
        self._pending: int | None = None
        self._value = self._align(value)

    # -- the value -------------------------------------------------------------

    @property
    def minimum(self) -> int:
        """The low end of the range; assigning re-clamps the value."""
        return self._minimum

    @minimum.setter
    def minimum(self, value: int) -> None:
        self._minimum = value
        self._value = self._align(self._value)

    @property
    def maximum(self) -> int:
        """The high end of the range; assigning re-clamps the value."""
        return self._maximum

    @maximum.setter
    def maximum(self, value: int) -> None:
        self._maximum = value
        self._value = self._align(self._value)

    @property
    def step(self) -> int:
        """The grid step; assigning re-snaps the value onto the new grid."""
        return self._step

    @step.setter
    def step(self, value: int) -> None:
        self._step = value
        self._value = self._align(self._value)

    def _align(self, value: int) -> int:
        """Clamp ``value`` into range and snap it onto the ``step`` grid."""
        span = self._maximum - self._minimum
        if span <= 0 or self._step <= 0:
            return self._minimum
        steps = int(span // self._step)  # the grid runs 0..steps, not past maximum
        k = int(
            (min(max(value, self._minimum), self._maximum) - self._minimum)
            / self._step
            + 0.5
        )
        return self._minimum + min(max(k, 0), steps) * self._step

    @property
    def value(self) -> int:
        """The current value: always inside ``[minimum, maximum]``, on the grid."""
        return self._value

    @value.setter
    def value(self, value: int) -> None:
        self._value = self._align(value)

    def move(self, delta: int) -> bool:
        """Step the value ``delta`` whole ``step``s, clamped; ``True`` when it moved.

        A step that moved clears a stale pending value -- a pick never
        survives the next move (the ``Select`` precedent).  A disabled
        slider moves nowhere.
        """
        if self.disabled:
            return False
        target = self._align(self._value + delta * self._step)
        moved = target != self._value
        if moved:
            self._value = target
            self._pending = None
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
        clears a stale pending value and answers ``True`` even when the
        value did not move (a click is a hit whether or not it changed
        anything).
        """
        if row != 0:
            return False
        if self.disabled:
            return False
        track = self._track(self._last_width)
        if track > 0:
            fraction = min(max((col - 1) / track, 0.0), 1.0)
            self._value = self._align(
                self.minimum + fraction * (self.maximum - self.minimum)
            )
        self._pending = None
        return True

    def activate(self) -> bool:
        """Confirm the current value into the pending result; ``False`` when disabled.

        The slider's :class:`~motui.kernel.document.Activable` verb: a host
        routes the return key here, then reads the value once through
        :meth:`take_result` -- a non-disabled slider always has a value to
        confirm.
        """
        if self.disabled:
            return False
        self._pending = self._value
        return True

    def take_result(self) -> int | None:
        """Read the pending confirmation once and clear it."""
        value = self._pending
        self._pending = None
        return value

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
        ``focused``/``disabled`` flags, the glyphs and the theme/styles pair
        the bands resolve from.  The block-level ``hover`` flag paints
        nothing -- the row emphasis lives in ``_marked`` -- and the pending
        result / ``_last_width`` are not row inputs, so they are
        deliberately out.  The snapshot is plain values, far cheaper than a
        render.
        """
        return (
            self._value,
            self._minimum,
            self._maximum,
            self._step,
            self._marked,
            self.focused,
            self.disabled,
            self.glyphs,
            self.theme,
            self.styles,
        )

    def render(self, c: Constraints | int) -> Surface:
        """The track row, under the render constraints.

        ``_last_width`` is the constrained width :meth:`click` maps a column
        against (seeded even by a zero height budget).  A bare ``int`` is the
        1.x width spelling and is normalized through
        :func:`~motui.kernel.layout.as_constraints`; ``max_height`` truncates
        the single row and the surface is clipped, not padded.
        """
        c = as_constraints(c)
        width = c.width
        self._last_width = width  # the geometry ``click`` maps a column against
        text = self.group("text")
        filled_style = self.group("content").accent
        empty_style = text.faint
        suffix = self._suffix()
        track = self._track(width)
        filled = self._filled(track)
        track_glyph = self.glyphs.slider_track
        thumb = self.glyphs.slider_thumb
        if thumb and track > 0:
            # The thumb is the position marker: every track cell up to it is
            # the filled run, every cell after it the empty one.
            at = min(filled, track - 1)
            segments = [
                Segment("[", NONE),
                Segment(track_glyph * at, filled_style),
                Segment(thumb, filled_style),
                Segment(track_glyph * (track - at - 1), empty_style),
                Segment("]", NONE),
                Segment(suffix, text.muted),
            ]
        else:
            segments = [
                Segment("[", NONE),
                Segment(track_glyph * filled, filled_style),
                Segment(track_glyph * (track - filled), empty_style),
                Segment("]", NONE),
                Segment(suffix, text.muted),
            ]
        if self.disabled:
            disabled_style = text.faint
            segments = [
                seg.with_style(seg.style.merge(disabled_style))
                for seg in segments
            ]
        elif self._marked or self.focused:
            band = self.group("surfaces").hover if self._marked else NONE
            if self.focused:
                band = band.merge(self.group("controls").focus)
            segments = [seg.with_style(seg.style.merge(band)) for seg in segments]
        rows = [Line(segments).fit(width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"Slider(value={self._value}, minimum={self.minimum}, "
            f"maximum={self.maximum}, step={self.step})"
        )


class Spinner(Widget):
    """A frame-cycling activity indicator with an optional label.

    ``render(width)`` is the current ``frame`` followed by ``text``, ``fit``
    to the painting width -- the spinner is a component like every other,
    so ``tui.add(Spinner(...))`` paints it.  ``advance`` steps the cycle;
    the pump's clock decides when.  The frame and text carry
    ``content.accent``, resolved at render time from ``styles`` (when given)
    or the theme, and :meth:`revision` snapshots the
    frame, the text, the theme and the styles, so a block's row cache
    follows an advanced frame or a retheme.
    """

    __slots__ = ("_frame", "frames", "glyphs", "text")

    def __init__(
        self,
        text: str = "",
        *,
        frames: tuple[str, ...] | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.text = text
        self.glyphs = glyphs
        self.frames = glyphs.spinner if frames is None else tuple(frames)
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

    def revision(self) -> object:
        """The row cache's snapshot: the frame, the text, theme and styles."""
        return (self.frame, self.text, self.theme, self.styles)

    def render(self, c: Constraints | int) -> Surface:
        """One fitted row: the current frame followed by the label.

        A bare ``int`` is the 1.x width spelling and is normalized through
        :func:`~motui.kernel.layout.as_constraints`; ``max_height`` truncates
        the single row and the surface is clipped, not padded.
        """
        c = as_constraints(c)
        style = self.group("content").accent
        rows = [Line.from_text(self.frame + self.text, style).fit(c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"Spinner({self.text!r}, frame={self.frame!r})"
