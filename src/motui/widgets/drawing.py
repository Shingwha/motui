"""Drawing: the sizing and caching lifecycle every drawing widget shares.

A :class:`Drawing` owns a width and a height in cells, one full-size
:class:`~motui.kernel.cell.Surface` cache, and the rule that separates the
two acts a paint used to fuse: **sizing is explicit** and **rendering is
pure**.  A host calls :meth:`resize` (or :meth:`fit`) before it paints and
:meth:`render` afterwards; ``render`` clips the cached image to the
constraints and never moves the canvas.  A drawing widget whose size
followed its constraints would lose its ink whenever a caller probed another
width -- the invariant matrix renders every component at seven widths, and
a game board must survive that.

Subclasses provide three hooks:

* :meth:`_resize_storage` rebuilds the private storage for the new size
  (the base has already installed ``width``/``height`` when it runs);
* :meth:`_build_surface` assembles the full-size surface from that storage;
* :meth:`_invalidate` clears the surface cache and touches the widget, for
  every drawing verb that changes the image in place.

``resize`` clamps a negative size to zero and is a no-op when the size is
unchanged, so a scene that resizes every tick does not drop its ink.  Every
other cache-clearing path goes through :meth:`_invalidate`, which is the one
answer to "the image changed": a verb must call it or the next ``surface``
would answer stale rows.
"""

from __future__ import annotations

from ..kernel.cell import Surface
from ..kernel.layout import Constraints
from .base import Widget

__all__ = ["Drawing"]


class Drawing(Widget):
    """A sized, cached drawing surface with an explicit resize step.

    ``width`` and ``height`` are cell dimensions; assigning either one
    resizes through the setter, exactly as :meth:`resize` does.  The surface
    cache is lazily built by :meth:`surface` and cleared by :meth:`resize`
    and :meth:`_invalidate`, so a clean canvas answers the very same
    ``Surface`` value it answered before, while a drawing verb pays for one
    rebuild on the next read.
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

        Both dimensions clamp at zero.  An unchanged size is a no-op: the
        stored ink survives, because a redraw loop that resizes every frame
        must not pay for a rebuild (and a pixel board must not lose its ink
        between two equal constraints).  A real change installs the new
        dimensions, lets the subclass rebuild its storage, drops the surface
        cache and touches the widget.
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
        """Adopt the constraint's size: its width and its height budget.

        A natural-height constraint (``max_height is None``) keeps the
        current height.  A zero budget is a real zero, not "natural" --
        the host asked for no rows.
        """
        self.resize(
            c.width,
            self._height if c.max_height is None else c.max_height,
        )

    # -- the image ---------------------------------------------------------

    def surface(self) -> Surface:
        """The full-size surface, built once per invalidation.

        A clean drawing answers the very same ``Surface`` value on every
        call; a verb that changed the image calls :meth:`_invalidate`, so
        the next read rebuilds.  The returned surface is immutable.
        """
        image = self._surface_cache
        if image is None:
            image = self._build_surface()
            object.__setattr__(self, "_surface_cache", image)
        return image

    def render(self, c: Constraints) -> Surface:
        """The cached image clipped to ``c``; never resizes the drawing.

        A natural-height constraint takes the whole image; a budget takes
        the leading rows.  Rows are clipped, never padded, and the surface
        width is the constraint's width.  A same-size constraint returns
        the cached surface object itself.
        """
        image = self.surface()
        height = image.height if c.max_height is None else min(image.height, c.max_height)
        if height == image.height and c.width == image.width:
            return image
        return Surface.clipped(image.rows[:height], c.width)

    # -- subclass hooks ----------------------------------------------------

    def _resize_storage(self, width: int, height: int) -> None:
        """Rebuild private storage for ``width`` x ``height``.

        The base has already installed the new dimensions when this runs;
        a subclass drops or preserves its ink here and must not call
        ``touch`` (the base does that once, after the hook).
        """
        return None

    def _build_surface(self) -> Surface:
        """Assemble the full-size surface from the private storage."""
        raise NotImplementedError

    def _invalidate(self) -> None:
        """Drop the cached surface and touch the widget.

        The one invalidation door every drawing verb calls after it changed
        the image in place.  ``resize`` clears the cache itself and need not
        go through here (it already touches).
        """
        object.__setattr__(self, "_surface_cache", None)
        self.touch()
