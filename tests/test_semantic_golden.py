"""The semantic golden tool: a small snapshot round trip and the real set.

The tool lives outside the package (``tools/semantic.py``), like
``tools/golden.py``; load it by path so the tests exercise the same module
the CI step runs.  The round-trip tests shrink the registry to one topic --
the tool reads it as a module global -- so they stay fast, while the last
test asserts the committed set covers every real topic.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from motui.demo.registry import TOPICS

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "semantic.py"


def _load():
    """Import ``tools/semantic.py`` under a private name."""
    spec = importlib.util.spec_from_file_location("semantic_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def semantic():
    return _load()


@pytest.fixture
def one_topic(semantic, monkeypatch):
    """Shrink the tool's registry to the first topic for a fast round trip."""
    topic = TOPICS[0]
    monkeypatch.setattr(semantic, "TOPICS", (topic,))
    return topic


def test_snapshot_has_one_line_per_row_and_a_cursor_header(semantic, one_topic):
    text = semantic.snapshot(one_topic)
    assert text.endswith("\n") and not text.endswith("\n\n")
    lines = text.split("\n")
    header = lines[0]
    assert header.startswith(f"# {one_topic.section}/{one_topic.key} 110x70 cursor=")
    cursor = header.rsplit("cursor=", 1)[1]
    assert cursor.count(",") == 1 and all(part.isdigit() for part in cursor.split(","))
    body = lines[1:-1]
    assert len(body) == 70
    assert all("\t" in line for line in body)
    assert all(not line.endswith(" ") for line in body)


def test_update_then_check_round_trips(semantic, one_topic, tmp_path, capsys):
    assert semantic.main(["--update", "--snapshot", str(tmp_path)]) == 0
    assert "recorded 1 topics" in capsys.readouterr().out
    files = list(tmp_path.glob("*.txt"))
    assert [path.name for path in files] == [semantic.topic_name(one_topic)]

    assert semantic.main(["--check", "--snapshot", str(tmp_path)]) == 0
    assert "semantic: 1 topics match" in capsys.readouterr().out


def test_update_is_deterministic(semantic, one_topic, tmp_path):
    assert semantic.main(["--update", "--snapshot", str(tmp_path)]) == 0
    first = {path.name: path.read_bytes() for path in tmp_path.glob("*.txt")}
    assert semantic.main(["--update", "--snapshot", str(tmp_path)]) == 0
    second = {path.name: path.read_bytes() for path in tmp_path.glob("*.txt")}
    assert first == second


def test_check_reports_a_tampered_row(semantic, one_topic, tmp_path, capsys):
    assert semantic.main(["--update", "--snapshot", str(tmp_path)]) == 0
    path = tmp_path / semantic.topic_name(one_topic)
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] += "X"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    assert semantic.main(["--check", "--snapshot", str(tmp_path)]) == 1
    assert f"{path.name}: differs" in capsys.readouterr().out


def test_check_reports_a_missing_file(semantic, one_topic, tmp_path, capsys):
    assert semantic.main(["--update", "--snapshot", str(tmp_path)]) == 0
    path = tmp_path / semantic.topic_name(one_topic)
    path.unlink()

    assert semantic.main(["--check", "--snapshot", str(tmp_path)]) == 1
    assert f"{path.name}: missing" in capsys.readouterr().out


def test_every_topic_has_a_snapshot(semantic):
    expected = {semantic.topic_name(topic): topic for topic in TOPICS}
    found = {path.name: path for path in semantic.GOLDEN.glob("*.txt")}
    assert set(found) == set(expected)
    assert len(found) == 57
    for name, topic in expected.items():
        lines = found[name].read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith(f"# {topic.section}/{topic.key} 110x70 cursor=")
        assert len(lines) == 71
