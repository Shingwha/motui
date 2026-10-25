"""The shipped examples run: quickstart paints, code scrolls, table reaches its end."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_quickstart_paints_headless_with_or_without_the_flag():
    for args in ([], ["--headless"]):
        done = subprocess.run(
            [sys.executable, "examples/quickstart.py", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=25,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        lines = done.stdout.splitlines()
        assert lines[0] == "Hello, motui."
        assert "type here" in lines[1]
        assert len(lines) == 3


def test_the_code_example_scrolls_to_the_long_line_tail():
    done = subprocess.run(
        [sys.executable, "examples/code.py", "--headless"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "code_wrap=OVERFLOW" in done.stdout
    assert "tail-marker visible" in done.stdout


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
