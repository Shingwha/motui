"""Overlay layers: the pipeline stage that paints over a composed frame.

An overlay claims no space and takes no budget; it paints last and hands
back the layout. Controllers are policy and live in :mod:`motui.app`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .layout import ScreenLayout

if TYPE_CHECKING:  # the protocol names the frame; no runtime import needed
    from .frame import Frame

__all__ = ["LAYERS", "Overlay", "apply_overlays"]

#: The overlay layers, back to front.  An overlay registered on a frame owns
#: one of these names; same-layer overlays paint in registration order.
LAYERS = (
    "background",
    "content",
    "selection",
    "chrome",
    "overlay",
    "modal",
    "tooltip",
    "toast",
)


class Overlay(Protocol):
    """One overlay: a pure ``paint(frame) -> layout``.

    It reads the composed layout, pane layouts and ownership table, and
    returns the layout to paint. It registers on a frame under one of
    :data:`LAYERS`."""

    def paint(self, frame: Frame) -> ScreenLayout: ...


def apply_overlays(frame: Frame, layout: ScreenLayout) -> ScreenLayout:
    """Run the registry over ``layout`` back to front by layer, stable within a
    layer; an empty registry passes ``layout`` through unchanged."""
    for _layer, overlay in sorted(frame._overlays, key=lambda entry: entry[0]):
        frame._painting = layout  # the running target the overlay reads
        layout = overlay.paint(frame)
    frame._painting = layout
    return layout
