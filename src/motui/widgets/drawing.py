"""Drawing: the sizing and caching lifecycle every drawing widget shares.

Sizing is explicit (``resize``/``fit``) and rendering is pure: ``render``
clips the cached full-size surface and never resizes.  Subclasses supply
``_resize_storage``, ``_build_surface`` and ``_invalidate``.
"""

from __future__ import annotations

from ..kernel.cell import Surface
from ..kernel.layout import Constraints
from .base import Widget

__all__ = ["Drawing"]


class Drawing(Widget):
    """A sized, cached drawing surface with an explicit resize step.

    Assigning ``width``/``height`` resizes through the setter.  ``surface``
    lazily builds the immutable full-size image; ``resize`` and
    ``_invalidate`` clear the cache and touch the widget.
    """

    __slots__ = ("_height", "_surface_cache", "_width")

    def __init__(
        self,
        *,
        width: int = 0,
        height: int = 0,
        theme=None,
    ) -> None:
        super().__init__(theme, None)
        object.__setattr__(self, "_width", max(0, int(width)))
        object.__setattr__(self, "_height", max(0, int(height)))
        object.__setattr__(self, "_surface_cache", None)

    # -- geometry ----------------------------------------------------------

    @property
    def width(self) -> int:
        """The drawing width in cells."""
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        self.resize(value, self._height)

    @property
    def height(self) -> int:
        """The drawing height in cells."""
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        self.resize(self._width, value)

    def resize(self, width: int, height: int) -> None:
        """Resize the drawing, rebuilding the subclass storage.

        Dimensions clamp at zero; an unchanged size is a no-op so ink
        survives equal constraints.  A real change rebuilds, drops the
        cache and touches.
        """
        width = max(0, int(width))
        height = max(0, int(height))
        if width == self._width and height == self._height:
            return
        object.__setattr__(self, "_width", width)
        object.__setattr__(self, "_height", height)
        self._resize_storage(width, height)
        object.__setattr__(self, "_surface_cache", None)
        self.touch()

    def fit(self, c: Constraints) -> None:
        """Adopt the constraint's width and height budget.

        A natural-height constraint keeps the current height; a zero budget
        is a real zero.
        """
        self.resize(
            c.width,
            self._height if c.max_height is None else c.max_height,
        )

    # -- the image ---------------------------------------------------------

    def surface(self) -> Surface:
        """The full-size immutable surface, rebuilt only after invalidation."""
        image = self._surface_cache
        if image is None:
            image = self._build_surface()
            object.__setattr__(self, "_surface_cache", image)
        return image

    def render(self, c: Constraints) -> Surface:
        """The cached image clipped to ``c``; never resizes the drawing."""
        image = self.surface()
        height = image.height if c.max_height is None else min(image.height, c.max_height)
        if height == image.height and c.width == image.width:
            return image
        return Surface.clipped(image.rows[:height], c.width)

    # -- subclass hooks ----------------------------------------------------

    def _resize_storage(self, width: int, height: int) -> None:
        """Rebuild private storage for ``width`` x ``height``.

        The new dimensions are already installed; do not touch.
        """
        return None

    def _build_surface(self) -> Surface:
        """Assemble the full-size surface from the private storage."""
        raise NotImplementedError

    def _invalidate(self) -> None:
        """Drop the cached surface and touch the widget (the one invalidation door)."""
        object.__setattr__(self, "_surface_cache", None)
        self.touch()
