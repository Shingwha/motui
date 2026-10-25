"""The API snapshot tool: exact check, additions-only check and its failures."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "tools" / "api.py"
SNAPSHOT = ROOT / "tools" / "api-2.0.txt"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the real tool from the repository root."""
    return subprocess.run(
        [sys.executable, str(API), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def copied(tmp_path: Path) -> Path:
    """A private copy of the committed snapshot."""
    target = tmp_path / "api.txt"
    shutil.copyfile(SNAPSHOT, target)
    return target


def test_check_accepts_the_recorded_surface(tmp_path):
    done = run("--check", "--snapshot", str(copied(tmp_path)))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "names match" in done.stdout


def test_check_rejects_a_tampered_signature(tmp_path):
    target = copied(tmp_path)
    lines = target.read_text(encoding="utf-8").splitlines()
    parts = lines[0].split("\t")
    parts[-1] += "!"
    lines[0] = "\t".join(parts)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    done = run("--check", "--snapshot", str(target))
    assert done.returncode == 1
    assert "(shape changed)" in done.stdout


def test_allow_additions_accepts_a_new_name(tmp_path):
    target = copied(tmp_path)
    lines = target.read_text(encoding="utf-8").splitlines()
    target.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8", newline="\n")
    done = run("--check", "--allow-additions", "--snapshot", str(target))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "1 additions" in done.stdout


def test_allow_additions_still_rejects_a_deleted_name(tmp_path):
    target = copied(tmp_path)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("motui\tzz_growth_probe\tvalue\tNone\n")
    done = run("--check", "--allow-additions", "--snapshot", str(target))
    assert done.returncode == 1
    assert "(missing)" in done.stdout
