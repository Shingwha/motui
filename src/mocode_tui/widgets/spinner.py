"""Spinner: a braille frame cycling around a label.

:class:`Spinner` owns a frame index and a label; ``advance()`` steps the
cycle (wrapping around), and the current ``frame`` plus ``text`` are what a
host paints -- the ``Composer`` rolls them into its working label.  The
pump's clock decides when ``advance`` is called; nothing here reads a
clock or a key.
"""

from __future__ import annotations

__all__ = ["DEFAULT_FRAMES", "Spinner"]

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
