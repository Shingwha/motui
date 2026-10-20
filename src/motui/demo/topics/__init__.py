"""The demo's topic modules, one per section group.

Each module exports ``TOPICS``: a tuple of :class:`~motui.demo.model.Topic`
values built through :func:`motui.demo.stage.topic`.  The registry imports
the modules explicitly; there is no discovery and no side effect beyond
declaring the values.
"""

from __future__ import annotations

__all__ = [
    "components_actions",
    "components_data",
    "components_forms",
    "components_layout",
    "components_overlays",
    "components_text",
    "interactions",
    "overview",
    "patterns",
    "reference",
    "styling",
]
