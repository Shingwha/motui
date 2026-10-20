"""The one home for shared test helpers.

Import everything from this package, never from a submodule::

    from tests.testing import Clock, Rows, key, press, texts

The public helpers of :mod:`motui.testing` (``ScriptedEvents``,
``headless_tui``, ``snapshot``) are re-exported here so a test has a single
import source.
"""

from __future__ import annotations

from motui.testing import ScriptedEvents, headless_tui, snapshot

from .clock import Clock
from .doubles import RecordingScreen, Rows, many
from .events import key, motion, paste, press, release, resize, wheel
from .layout import marked, rows, texts

__all__ = [
    "Clock",
    "RecordingScreen",
    "Rows",
    "ScriptedEvents",
    "headless_tui",
    "key",
    "many",
    "marked",
    "motion",
    "paste",
    "press",
    "release",
    "resize",
    "rows",
    "snapshot",
    "texts",
    "wheel",
]
