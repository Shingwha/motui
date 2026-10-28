"""The version the showcase displays, read from the one distribution source."""

from __future__ import annotations

from .. import __version__

__all__ = ["DEMO_BAND", "DEMO_VERSION"]

DEMO_VERSION = __version__
DEMO_BAND = ".".join(__version__.split(".")[:2])
