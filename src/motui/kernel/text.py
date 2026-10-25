"""Wrapping strategy values.

``WrapMode`` names *how* a row responds to a width limit; the algorithms
themselves arrive in W2.5.  The enum lives beside the geometry so that
components can hold a stable configuration value before the wrap engine is
migrated.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["WrapMode"]


class WrapMode(Enum):
    """How a line is fitted to a width.

    ``WORD`` and ``CHAR`` may produce several rows (1..N); ``ELLIPSIS``,
    ``CLIP`` and ``OVERFLOW`` are single-row modes.  ``OVERFLOW`` is the only
    mode that may return a row wider than the limit; the container clips it
    at its own edge.
    """

    WORD = "word"
    CHAR = "char"
    ELLIPSIS = "ellipsis"
    CLIP = "clip"
    OVERFLOW = "overflow"
