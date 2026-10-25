"""Overlay layers: the pipeline stage that paints over a composed frame.

An overlay claims no space and takes no budget: it paints last, over the
composed frame, and hands back the layout the next overlay (or the painter)
sees.  The registry lives on the frame; this module owns the layer
vocabulary, the protocol, and the ordered walk that runs the registry.

The frame's registry is the kernel's mechanism; the overlays' controllers
(selection, toasts, tooltips) are policy and live one level up, in
:mod:`motui.app`.
"""

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
    """One overlay of the frame's pipeline: a pure ``paint(frame) -> layout``.

    An overlay claims nothing -- it paints last, over the composed frame, so
    it needs no budget negotiation.  The frame hands it the composed value:
    :attr:`Frame.layout` is the rows as they stand (an earlier overlay's
    rows when the registry already ran one), :meth:`Frame.pane_layout` one
    pane's own layout, :attr:`Frame.table` the ownership table, and
    :attr:`Frame.rect` the frame's bounds -- a toast paints a corner off the
    bounds, a highlight rewrites a pane's rows.  What comes back is the
    layout to paint: the frame's layout with its rows rewritten, a
    pane-relative edit spliced back through :meth:`Frame.with_pane_rows`.

    Overlays register with :meth:`Frame.add_overlay`, naming one of
    :data:`LAYERS`; they paint back to front by layer and in registration
    order within one layer, and their lifecycle and their input live in the
    controller that owns them, never in the kernel.
    """

    def paint(self, frame: "Frame") -> ScreenLayout: ...


def apply_overlays(frame: "Frame", layout: ScreenLayout) -> ScreenLayout:
    """Run ``frame``'s overlay registry over ``layout``, back to front by layer.

    Each overlay paints over the composed frame and hands back the layout to
    paint, which becomes the frame's ``layout`` for the next one -- a later
    overlay composes over the rows an earlier one painted.  The registry is
    walked in a **stable sort** by layer index, so same-layer overlays keep
    their registration order and an explicitly lower layer always paints
    first.  The painting target is written back once, when the registry has
    run.  An empty registry, like an overlay that rewrites nothing, hands
    ``layout`` through unchanged.
    """
    for _layer, overlay in sorted(frame._overlays, key=lambda entry: entry[0]):
        frame._painting = layout  # the running target the overlay reads
        layout = overlay.paint(frame)
    frame._painting = layout
    return layout
