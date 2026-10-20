"""Temporary bridge for flat test modules during the test refactor.

Old modules still say ``from _doubles import ...``.  The names live in
:mod:`tests.testing` now; this module disappears with the last flat module
(W4), so new tests must import from ``tests.testing`` directly.
"""

from __future__ import annotations

from tests.testing import RecordingScreen, Rows, key, many, texts

__all__ = ["RecordingScreen", "Rows", "key", "many", "texts"]
