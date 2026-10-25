"""The shipped examples run: the headless snake finishes with a result."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_snake_example_runs_headless():
    done = subprocess.run(
        [sys.executable, "examples/snake.py", "--headless"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "score" in done.stdout
    assert "alive" in done.stdout
