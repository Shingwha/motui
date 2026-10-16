"""docs/API.md is generated: the facades' names pinned to the page.

``tools/apidoc.py`` renders the page from the modules and ``--check`` is the
drift gate; this test is the in-repo assertion, the same shape as the golden
frames': the committed page matches a fresh render (read with universal
newlines, so a checkout's CRLF reads as the LF it stands for -- this page is
prose, not a byte-pinned frame), every facade and every name in its
``__all__`` is on it exactly once, a missing page and a drifted copy are
both named, the CLI's exit codes speak, and the render carries neither a
memory address nor a repr'd annotation -- the two things that would move
the page on a machine that changed nothing.  Nothing here sleeps: a render
is reflection over already-imported modules.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import apidoc  # noqa: E402

PAGE = ROOT / "docs" / "API.md"


def test_the_page_matches_the_facades():
    """The gate's line: docs/API.md is exactly what the modules render."""
    assert apidoc.check() == []
    assert PAGE.read_text(encoding="utf-8").startswith("# API\n")


def test_every_facade_and_every_curated_name_is_on_the_page():
    """Every ``__all__`` name has its ``### name`` block under its facade.

    A name two facades both curate (the root re-exports the core's ``ACCENT``)
    rightly appears under both; the entry count and the heading count are
    what say every name is covered exactly as often as a facade claims it.
    """
    text = apidoc.render()
    assert text.startswith("# API\n")
    assert "**Generated**" in text
    for facade in apidoc.FACADES:
        module = importlib.import_module(facade)
        assert f"## {facade}\n" in text
        for name in module.__all__:
            assert f"### {name}\n" in text, name
    assert len(re.findall(r"^### ", text, re.M)) == apidoc.entry_count()
    assert apidoc.entry_count() == sum(
        len(importlib.import_module(facade).__all__) for facade in apidoc.FACADES
    )


def test_a_missing_page_and_a_drifted_copy_are_both_named(tmp_path):
    """``check`` says ``missing`` for no file and ``differs`` for a moved one."""
    page = tmp_path / "API.md"
    assert apidoc.check(page) == ["API.md: missing"]
    page.write_text(apidoc.render().replace("### Find\n", "### Find me\n", 1), encoding="utf-8")
    assert apidoc.check(page) == ["API.md: differs"]


def test_a_checkout_crlf_copy_reads_as_the_lf_it_stands_for(tmp_path):
    """The one other spelling a checkout makes is the same page, not a diff."""
    page = tmp_path / "API.md"
    page.write_bytes(apidoc.render().replace("\n", "\r\n").encode("utf-8"))
    assert apidoc.check(page) == []


def test_the_cli_defaults_to_check_and_its_exit_codes_speak(tmp_path, monkeypatch):
    """No flag means ``--check``; a drift exits 1, a bad flag 2, ``--write`` records."""
    page = tmp_path / "API.md"
    monkeypatch.setattr(apidoc, "OUTPUT", page)
    assert apidoc.main(["--check"]) == 1  # missing is a problem, not a shrug
    assert apidoc.main(["--write"]) == 0
    assert page.is_file() and apidoc.check(page) == []
    assert apidoc.main([]) == 0  # the gate's line, no flag
    page.write_text("stale\n", encoding="utf-8")
    assert apidoc.main(["--check"]) == 1
    assert apidoc.main(["--nonsense"]) == 2
    assert apidoc.main(["--check", "--write"]) == 2


def test_signatures_are_source_text_without_reprs_or_addresses():
    """The formatter's two rules: annotations raw, instances by their type."""
    text = apidoc.render()
    assert "theme: Theme | None = None" in text  # the source's annotation, verbatim
    assert "'Theme | None'" not in text  # never a repr'd annotation
    assert "theme: Theme = Theme(...)" in text  # RenderContext's instance default
    assert "on_end: _OnEnd = copy_on_select" in text  # a routine default, by name
    assert " at 0x" not in text  # no memory addresses anywhere
    assert apidoc.render() == apidoc.render()  # and the render is stable
