"""Test configuration: make the repository root importable.

The suite is a package (``tests``), so ``tests.testing`` resolves when pytest
imports a test module from any subdirectory.  No fixtures live here on
purpose: the shared helpers are ordinary functions in :mod:`tests.testing`,
so a test can see exactly what it wires.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
