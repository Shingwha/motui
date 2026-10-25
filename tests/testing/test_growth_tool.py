"""The growth probe: a defaulted field survives the gates in a throw-away copy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GROWTH = ROOT / "tools" / "growth.py"


@pytest.mark.timeout(180)
def test_growth_quick_passes_against_the_current_tree():
    done = subprocess.run(
        [sys.executable, str(GROWTH), "--quick"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=150,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "growth: pytest -> 0" in done.stdout
    assert "growth: semantic -> 0" in done.stdout
    assert "growth: OK (quick probe)" in done.stdout
