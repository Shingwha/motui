"""The golden frames: every demo topic pinned byte for byte.

``tools/golden.py`` renders the demo's topics through the path ``python -m
motui --pages`` walks and records one file per topic; this test is the
in-repo assertion: exactly one file per registry topic (a missing or an
extra file is a failure, not a shrug), and every file equal to today's
render -- read as bytes, not text, so a changed byte cannot hide behind a
newline translation.  The one accepted other spelling is the exact
``LF -> CRLF`` conversion a Windows checkout makes (``core.autocrlf``; the
tree has no line-ending attributes on purpose): it is the same frame, and
``golden.matches`` is the one rule the tool and this test share.  Nothing
here sleeps: a topic render is a paint on a headless screen.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import golden  # noqa: E402

from motui.demo.registry import TOPICS  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "topics"


def _names() -> list[str]:
    return [golden.topic_name(topic) for topic in TOPICS]


def test_the_golden_directory_holds_exactly_one_file_per_topic():
    """The file set is the registry's topic set: no topic without a frame."""
    stems = sorted(path.name for path in GOLDEN.glob("*.txt"))
    assert stems == sorted(_names())
    assert len(stems) == len(TOPICS)


def test_every_topic_matches_its_golden_frame_byte_for_byte():
    """One topic, one file, one byte-for-byte comparison (LF or a CRLF checkout)."""
    for topic in TOPICS:
        path = GOLDEN / golden.topic_name(topic)
        expected = golden.render_topic(topic).encode("utf-8")
        assert b"\r" not in expected  # the render itself is LF-only
        assert golden.matches(path.read_bytes(), expected), golden.topic_name(topic)


def test_the_one_other_accepted_spelling_is_the_exact_checkout_conversion():
    """``matches`` accepts the LF record and its exact CRLF conversion only.

    The rule is what makes the check green in a fresh Windows clone
    (``core.autocrlf`` rewrites every LF) without letting any other
    spelling through: a mixed ending, a stray CR and a changed byte are
    all diffs.
    """
    record = b"row one\nrow two\n"
    assert golden.matches(record, record)
    assert golden.matches(record.replace(b"\n", b"\r\n"), record)
    assert not golden.matches(b"row one\r\nrow two\n", record)  # mixed
    assert not golden.matches(b"row one\nrow two\r\n", record)  # mixed
    assert not golden.matches(b"row one\nrow two", record)  # lost newline
    assert not golden.matches(b"row ONE\nrow two\n", record)  # changed byte


def test_update_reproduces_the_frames_and_check_names_every_problem(tmp_path):
    """``update`` records what the repository holds; ``check`` names what moved."""
    golden.update(tmp_path)
    for topic in TOPICS:
        name = golden.topic_name(topic)
        written = (tmp_path / name).read_bytes()
        assert b"\r" not in written  # the writer always records LF
        assert golden.matches(written, golden.render_topic(topic).encode("utf-8")), name
    assert golden.check(tmp_path) == []

    damaged = tmp_path / golden.topic_name(TOPICS[0])
    damaged.write_text("stale frame\n", encoding="utf-8")
    removed = tmp_path / golden.topic_name(TOPICS[1])
    removed.unlink()
    (tmp_path / "ghost--topic.txt").write_text("no topic owns me\n", encoding="utf-8")
    assert golden.check(tmp_path) == sorted([
        "ghost--topic.txt: extra",
        f"{golden.topic_name(TOPICS[0])}: differs",
        f"{golden.topic_name(TOPICS[1])}: missing",
    ])


def test_the_cli_defaults_to_check_and_fails_on_a_diff(monkeypatch, tmp_path):
    """No argument means ``--check``; a diff exits 1, a bad flag 2."""
    monkeypatch.setattr(golden, "GOLDEN", tmp_path)
    monkeypatch.setattr(golden, "check", lambda *args, **kwargs: [])
    monkeypatch.setattr(golden, "update", lambda *args, **kwargs: None)
    assert golden.main([]) == 0  # the gate's line, no flag
    assert golden.main(["--check"]) == 0
    monkeypatch.setattr(golden, "check", lambda *args, **kwargs: ["welcome.txt: differs"])
    assert golden.main(["--check"]) == 1
    assert golden.main(["--update"]) == 0
    assert golden.main(["--nonsense"]) == 2
    assert golden.main(["--check", "--update"]) == 2


def test_the_recorded_frames_are_not_empty_and_carry_their_topic_rule():
    """A frame that lost its header line or its content is not a frame."""
    for topic in TOPICS:
        text = (GOLDEN / golden.topic_name(topic)).read_text(encoding="utf-8")
        assert text.startswith(f"\u2500\u2500 /{topic.section}/{topic.key} ")
        assert len(text.splitlines()) > 3, golden.topic_name(topic)
