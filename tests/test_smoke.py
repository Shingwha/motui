"""The shipped demo still boots: both headless entries and every topic.

This is a smoke test, not an IA test.  It runs the same paths a user runs --
the piped replay and ``--pages`` -- and asserts they complete and print
something; the exact content is the golden frames' job.
"""

from __future__ import annotations

import sys

from motui.demo import main, render_topic
from motui.demo.registry import TOPICS


def test_every_topic_renders_a_frame():
    assert TOPICS
    for topic in TOPICS:
        text = render_topic(topic)
        assert text.startswith(f"\u2500\u2500 /{topic.section}/{topic.key} "), topic.key
        assert topic.title in text, topic.key
        assert text.endswith("\n") and len(text.splitlines()) > 3, topic.key


def test_the_pages_entry_prints_every_topic(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["motui", "--pages"])
    main()
    out = capsys.readouterr().out
    for topic in TOPICS:
        assert f"/{topic.section}/{topic.key} " in out, topic.key


def test_the_piped_entry_replays_and_dumps(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["motui"])
    main()
    out = capsys.readouterr().out
    assert out.strip()
    assert "\u2500\u2500" in out
