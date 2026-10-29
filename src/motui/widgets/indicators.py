"""Value indicators: the progress bar, the slider and the spinner.

Three components that show a value, one family file:

* :class:`ProgressBar` -- the determinate bar: a single-row
  ``[\u2588\u2588\u2588\u2591\u2591\u2591]`` track whose filled part is
  :attr:`ProgressBar.fraction` of the whole.  ``value`` and ``maximum`` are
  the state; ``fraction`` is the read-only quotient ``value / maximum``.
  The host moves ``value`` over time -- ``render`` itself stays a pure
  function of the component and ``width``.
* :class:`Slider` -- the numeric control: ``[━━━━●───] 4``, a bracketed
  track whose length follows the painting width, the value printed after the
  closing bracket.  The value lives on the ``step`` grid the constructor
  defines; :meth:`Slider.move`, :meth:`Slider.on_click` (mapped against the
  track of the last render) and :meth:`Slider.on_action` are its controller
  doors, and activation answers whether the control is available -- the
  value itself is the only state (no one-shot result).
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

from ..kernel.cell import Line, Segment, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.style import NONE
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["ProgressBar", "Slider", "Spinner"]

#: The width the slider's ``click`` maps a column against before the first
#: paint (the same 80-column fallback ``Tabs`` and ``TextBuffer`` use).
DEFAULT_WIDTH = 80


class ProgressBar(Widget):
    """A determinate progress bar: label, ``[``, filled blocks, ``]``.

    ``value`` clamps into ``[0, maximum]`` on construction and on every
    later assignment, so ``bar.value = 1.4`` reads back ``1.0`` with the
    default maximum.  ``maximum`` must be positive (``ValueError``
    otherwise) and re-clamps the value when assigned.  :attr:`fraction` is
    the read-only quotient ``value / maximum``.  The track is
    ``width_chars`` columns wide when that is given, otherwise it fills the
    available width minus the label prefix and the two frame cells; the
    filled part is ``round(inner * fraction)`` blocks.  The filled blocks
    carry ``status.success`` and the empty ones ``text.faint``, resolved at
    render time from ``styles`` (when given) or the theme; the
    label plus frame stay unstyled.
    """

    __slots__ = (
        "_maximum",
        "_value",
        "glyphs",
        "label",
        "width_chars",
    )

    def __init__(
        self,
        value: float = 0.0,
        *,
        maximum: float = 1.0,
        label: str = "",
        width_chars: int | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        if maximum <= 0:
            raise ValueError(f"maximum must be positive, got {maximum!r}")
        super().__init__(theme, styles)
        self._maximum = maximum
        self.value = value
        self.label = label
        self.width_chars = width_chars
        self.glyphs = glyphs

    @property
    def maximum(self) -> float:
        """The value the bar is full at (always positive)."""
        return self._maximum

    @maximum.setter
    def maximum(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f"maximum must be positive, got {value!r}")
        self._maximum = value
        self._value = min(max(self._value, 0.0), value)
        self.touch()

    @property
    def value(self) -> float:
        """The completed value, always clamped into ``[0, maximum]``."""
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._value = min(max(value, 0.0), self._maximum)
        self.touch()

    @property
    def fraction(self) -> float:
        """The completed fraction, the read-only ``value / maximum``."""
        return self._value / self._maximum

    def render(self, c: Constraints) -> Surface:
        """The label-plus-track row, under the render constraints.

        A ``max_height`` budget truncates the single row (``0`` paints
        nothing).  The answer is
        :meth:`~motui.kernel.cell.Surface.clipped`, not padded, so the bytes
        match the old list answer.
        """
        done_style = self.group("status").success
        todo_style = self.group("text").faint
        lead = f"{self.label} " if self.label else ""
        if self.width_chars is None:
            inner = max(0, c.width - Line.from_text(lead).width - 2)
        else:
            inner = max(0, self.width_chars)
        done = min(inner, round(inner * self.fraction)) if inner else 0
        row = Line(
            (
                Segment(lead),
                Segment("["),
                Segment(self.glyphs.bar_full * done, done_style),
                Segment(self.glyphs.bar_empty * (inner - done), todo_style),
                Segment("]"),
            )
        )
        rows = [row.clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"ProgressBar(value={self.value}, maximum={self.maximum}, "
            f"label={self.label!r}, width_chars={self.width_chars})"
        )


class Slider(Widget):
    """A one-row ``[━━━━●───] value`` control over a stepped integer range.

    ``value`` is a read-write attribute: assigning clamps into
    ``[minimum, maximum]`` and snaps onto the ``step`` grid, so the value
    is always one the arrows can reach (an empty range -- ``maximum <=
    minimum`` -- pins it to ``minimum``).  ``minimum``, ``maximum`` and
    ``step`` are property setters too: assigning any of them re-clamps and
    re-snaps the current value, so the invariant survives a range change.
    :meth:`move` steps ``delta`` whole ``step``s (clamped at the ends),
    :meth:`on_click` maps a column of the track onto the grid, and
    :meth:`activate` answers whether the control is available -- the value
    is the only state, so there is no one-shot result to take.  A disabled
    slider refuses all three doors and merges ``text.faint`` over every
    segment.

    The track's length follows the painting width: ``[`` and ``]`` plus one
    space and the value's digits are the fixed part, the rest is track
    (a width too narrow for even the brackets truncates through ``fit``).
    ``on_hover`` marks the row (any other row answers "no row" and clears
    the marking; a negative row clears it too).  The marking starts ``None``
    -- or, equivalently, unmarked -- so an un-hovered slider renders
    byte-for-byte what it always did.  ``focused`` is the focus flag the
    focus tier sets.  Hover, focus and disabled all merge the shared
    ``controls.overlay`` over every segment (so focus is a visible
    bold+underline+reverse band, and disabled is faint+dim); the bands are
    read at render time from ``styles`` (when given) or the theme: filled
    ``content.accent``, empty ``text.faint``, hover/focus/disabled
    ``controls.overlay`` and disabled additionally ``text.faint``.
    """

    __slots__ = (
        "_last_width",
        "_marked",
        "_maximum",
        "_minimum",
        "_step",
        "_value",
        "disabled",
        "glyphs",
    )

    #: A slider is a focus target, takes pointer clicks (the track maps the
    #: value), paints a hover band and confirms its value on activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

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
        # ``on_hover``, read by ``render``.  Unmarked renders byte-for-byte
        # the same row.
        self._marked = False
        # The width ``click`` maps a column against before the first paint;
        # every render refreshes it.
        self._last_width = DEFAULT_WIDTH
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
        self.touch()

    @property
    def maximum(self) -> int:
        """The high end of the range; assigning re-clamps the value."""
        return self._maximum

    @maximum.setter
    def maximum(self, value: int) -> None:
        self._maximum = value
        self._value = self._align(self._value)
        self.touch()

    @property
    def step(self) -> int:
        """The grid step; assigning re-snaps the value onto the new grid."""
        return self._step

    @step.setter
    def step(self, value: int) -> None:
        self._step = value
        self._value = self._align(self._value)
        self.touch()

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
        self.touch()

    def move(self, delta: int) -> bool:
        """Step the value ``delta`` whole ``step``s, clamped; ``True`` when it moved.

        A disabled slider moves nowhere.
        """
        if self.disabled:
            return False
        target = self._align(self._value + delta * self._step)
        moved = target != self._value
        if moved:
            self._value = target
            self.touch()
        return moved

    def activate(self) -> bool:
        """Answer whether the slider is available; the value is the state."""
        return not self.disabled

    def on_key(self, e: KeyEvent) -> bool:
        """Route one key: the arrows step the value, ``enter`` confirms it.

        ``left``/``up`` step back and ``right``/``down`` step on, exactly
        the 1.x focus tier's mapping; a step at the end of the range answers
        ``False`` (nothing moved), so the host keeps the key.  ``enter``
        answers :meth:`activate`.  Every other key declines.
        """
        if e.key in ("left", "up"):
            return self.move(-1)
        if e.key in ("right", "down"):
            return self.move(1)
        if e.key == "enter":
            return self.activate()
        return False

    def on_action(self, name: str) -> bool:
        """Run one named action: activation or a one-step move.

        ``"activate"`` delegates :meth:`activate` (the value is not a
        one-shot result); ``"prev"`` / ``"next"`` (and the arrow spellings)
        step the value one ``step``.  Unknown names decline.
        """
        if name == "activate":
            return self.activate()
        if name in ("prev", "left", "up", "move_left", "move_up"):
            return self.move(-1)
        if name in ("next", "right", "down", "move_right", "move_down"):
            return self.move(1)
        return False

    def on_click(self, pos: Pos) -> bool:
        """Position the value by the clicked cell; ``True`` on a hit.

        The slider paints one row, so any other ``pos.y`` answers ``False``.
        ``pos.x`` is a 0-based cell of this component's own render, resolved
        against the track of the **last render** (``_last_width``): the
        cell's position over the track's columns becomes the fraction of
        the range, and the value lands on the nearest grid point -- a cell
        at or left of the opening bracket lands on ``minimum``, a cell at
        or past the closing bracket on the largest grid point.  A hit
        answers ``True`` even when the value did not move (a click is a hit
        whether or not it changed anything).
        """
        if pos.y != 0:
            return False
        if self.disabled:
            return False
        track = self._track(self._last_width)
        if track > 0:
            fraction = min(max((pos.x - 1) / track, 0.0), 1.0)
            self._value = self._align(
                self.minimum + fraction * (self.maximum - self.minimum)
            )
        self.touch()
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the row under the pointer; ``True`` when the marking changed.

        The pointer tier's row-level half: row 0 is the slider's single row
        and every other row -- ``None`` (the pointer left) included --
        clears the marking.  The column is ignored.  The answer is whether
        the marking changed, so a motion inside the row answers ``False``
        (nothing to repaint); :meth:`render` merges the theme's ``hover``
        over the marked row.
        """
        target = pos is not None and pos.y == 0
        changed = target != self._marked
        if changed:
            self._marked = target
            self.touch()
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

    def render(self, c: Constraints) -> Surface:
        """The track row, under the render constraints.

        ``_last_width`` is the constrained width :meth:`on_click` maps a column
        against (seeded even by a zero height budget).  ``max_height``
        truncates the single row and the surface is clipped, not padded.
        """
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
        overlay = self.group("controls").overlay(
            hovered=self._marked, focused=self.focused, disabled=self.disabled
        )
        if overlay != NONE:
            segments = [
                seg.with_style(seg.style.merge(overlay)) for seg in segments
            ]
        rows = [Line(segments).clip(WrapMode.ELLIPSIS, width)]
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

    ``render(c)`` is the current ``frame`` followed by ``text``, ``fit``
    to the painting width -- the spinner is a component like every other,
    so ``tui.add(Spinner(...))`` paints it.  ``advance`` steps the cycle;
    the pump's clock decides when.  The frame and text carry
    ``content.accent``, resolved at render time from ``styles`` (when given)
    or the theme.  :meth:`advance` touches the widget, so a block's row
    cache follows an advanced frame; assigning ``text`` or ``theme`` touches
    through :class:`~motui.widgets.base.Widget`.
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
            self.touch()

    def render(self, c: Constraints) -> Surface:
        """One fitted row: the current frame followed by the label.

        ``max_height`` truncates the single row and the surface is clipped,
        not padded.
        """
        style = self.group("content").accent
        rows = [Line.from_text(self.frame + self.text, style).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"Spinner({self.text!r}, frame={self.frame!r})"
