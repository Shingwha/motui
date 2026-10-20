"""Test configuration: make the repository root and the legacy shim importable.

The suite is a package (``tests``), so ``tests.testing`` resolves when pytest
imports a test module from any subdirectory.  ``tests/`` itself stays on
``sys.path`` only while old flat test modules still import ``_doubles``; the
last wave deletes both.  No fixtures live here on purpose: the shared helpers
are ordinary functions in :mod:`tests.testing`, so a test can see exactly
what it wires.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent
for path in (ROOT, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
