"""The golden frames: every demo page pinned byte for byte.

``tools/golden.py`` renders the demo's pages through the path ``python -m
motui --pages`` walks and records one file per page; this test is the
in-repo assertion: exactly one file per registry page (a missing or an
extra file is a failure, not a shrug), and every file equal to today's
render -- read as bytes, not text, so a changed byte cannot hide behind a
newline translation.  The one accepted other spelling is the exact
``LF -> CRLF`` conversion a Windows checkout makes (``core.autocrlf``; the
tree has no line-ending attributes on purpose): it is the same frame, and
``golden.matches`` is the one rule the tool and this test share.  Nothing
here sleeps: a page render is a paint on a headless screen.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import golden  # noqa: E402

from motui.demo.registry import PAGES  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "pages"


def test_the_golden_directory_holds_exactly_one_file_per_page():
    """The file set is the registry's page set: no page without a frame."""
    stems = sorted(path.stem for path in GOLDEN.glob("*.txt"))
    assert stems == sorted(page.name for page in PAGES)
    assert len(stems) == len(PAGES)


def test_every_page_matches_its_golden_frame_byte_for_byte():
    """One page, one file, one byte-for-byte comparison (LF or a CRLF checkout)."""
    for page in PAGES:
        path = GOLDEN / f"{page.name}.txt"
        expected = golden.render_page(page).encode("utf-8")
        assert b"\r" not in expected  # the render itself is LF-only
        assert golden.matches(path.read_bytes(), expected), page.name


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
    """``update`` records what the repository holds; ``check`` names what moved.

    The recording half is written into a temporary directory and compared
    with the checked-in files (the writer's LF record really is
    deterministic), then the copy is damaged three ways -- a changed file, a
    stray file, a removed file -- and ``check`` must report exactly those
    three, sorted.
    """
    golden.update(tmp_path)
    for page in PAGES:
        name = f"{page.name}.txt"
        written = (tmp_path / name).read_bytes()
        assert b"\r" not in written  # the writer always records LF
        assert golden.matches(written, golden.render_page(page).encode("utf-8")), name
    assert golden.check(tmp_path) == []

    overview = tmp_path / "overview.txt"
    overview.write_text("stale frame\n", encoding="utf-8")
    (tmp_path / "ghost.txt").write_text("no page owns me\n", encoding="utf-8")
    (tmp_path / "text.txt").unlink()
    assert golden.check(tmp_path) == [
        "ghost.txt: extra",
        "overview.txt: differs",
        "text.txt: missing",
    ]


def test_the_cli_defaults_to_check_and_fails_on_a_diff(monkeypatch, tmp_path):
    """No argument means ``--check``; a diff exits 1, a bad flag 2."""
    monkeypatch.setattr(golden, "GOLDEN", tmp_path)
    monkeypatch.setattr(golden, "check", lambda *args, **kwargs: [])
    monkeypatch.setattr(golden, "update", lambda *args, **kwargs: None)
    assert golden.main([]) == 0  # the gate's line, no flag
    assert golden.main(["--check"]) == 0
    monkeypatch.setattr(golden, "check", lambda *args, **kwargs: ["overview.txt: differs"])
    assert golden.main(["--check"]) == 1
    assert golden.main(["--update"]) == 0
    assert golden.main(["--nonsense"]) == 2
    assert golden.main(["--check", "--update"]) == 2


def test_the_recorded_frames_are_not_empty_and_carry_their_page_rule():
    """A frame that lost its header line or its content is not a frame."""
    for page in PAGES:
        text = (GOLDEN / f"{page.name}.txt").read_text(encoding="utf-8")
        assert text.startswith(f"\u2500\u2500 /{page.name} ")
        assert len(text.splitlines()) > 3, page.name
