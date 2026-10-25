"""The shipped examples run: the headless snake finishes, the wide table scrolls."""

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


def test_the_wide_table_example_reaches_its_rightmost_column():
    done = subprocess.run(
        [sys.executable, "examples/wide_table.py", "--headless"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "c199" in done.stdout and "v199" in done.stdout
    assert "200 columns" in done.stdout


def test_the_dashboard_example_replays_frames_headless():
    done = subprocess.run(
        [sys.executable, "examples/dashboard.py", "--headless", "--frames", "12"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "dashboard: 12 frames" in done.stdout
    assert "points" in done.stdout
