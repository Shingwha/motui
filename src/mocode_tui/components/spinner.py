"""Spinner component: a braille frame cycling around a label.

:class:`Spinner` owns a frame index and a label; ``advance()`` steps the
cycle (wrapping around), and ``render(width)`` draws ``frame + " " + text``.
The W4 driver decides when ``advance`` is called -- nothing here reads a
clock or a key.  Only the kernel is imported.
"""

from __future__ import annotations

from ..lines import Line

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
    """A frame-cycling activity indicator with an optional label."""

    __slots__ = ("_frame", "frames", "text")

    def __init__(self, text: str = "", *, frames: tuple[str, ...] | None = None) -> None:
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

    def render(self, width: int) -> list[Line]:
        body = self.frame
        if self.text:
            body = f"{body} {self.text}" if body else self.text
        return [Line.from_text(body).fit(width)]

    def __repr__(self) -> str:
        return f"Spinner({self.text!r}, frame={self.frame!r})"
