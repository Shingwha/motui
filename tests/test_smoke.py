"""The shipped showcase still boots: every scene entry and every mode.

This is a smoke test, not an IA test.  It renders each scene on the two
supported geometries and runs the same paths a user runs -- ``--pages``,
the piped default and ``--scene ... --headless`` -- asserting they complete
and print something.  The exact bytes are the semantic snapshots' job.
"""

from __future__ import annotations

import sys

from motui.demo import SCENES, main, render_scene, scene_output


def test_every_scene_renders_a_bounded_frame():
    assert SCENES == ("splash", "menu", "breakout", "gallery")
    for name in SCENES:
        for width, height in ((80, 24), (100, 30)):
            text = render_scene(name, width=width, height=height, phase=8)
            assert text.strip(), name
            lines = text.splitlines()
            assert len(lines) <= height, name
            for line in lines:
                assert len(line) <= width, (name, line)
                assert line == line.rstrip(), (name, line)


def test_pages_entry_prints_every_scene(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["motui", "--pages"])
    assert main() == 0
    out = capsys.readouterr().out
    for name in SCENES:
        assert f"\u2500\u2500 /{name} \u2500" in out, name
    assert "Breakout" in out
    assert "2.0 in one page" in out
    assert "score" in out and "paddle" in out


def test_the_piped_entry_prints_the_menu(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["motui"])
    assert main() == 0
    out = capsys.readouterr().out
    assert "Breakout" in out and "Gallery" in out and "showcase" in out


def test_scene_flag_renders_that_scene(capsys):
    assert main(["--scene", "splash", "--headless"]) == 0
    out = capsys.readouterr().out
    assert "press any key" in out
    assert "Breakout" not in out


def test_frames_advance_the_scene_machine(capsys):
    assert main(["--scene", "splash", "--frames", "60", "--headless"]) == 0
    out = capsys.readouterr().out
    assert "Breakout" in out  # the splash handed over to the menu


def test_gallery_scene_is_reachable_headless(capsys):
    assert main(["--scene", "gallery", "--headless"]) == 0
    out = capsys.readouterr().out
    assert "2.0 in one page" in out and "tab focus" in out


def test_breakout_replays_headless(capsys):
    assert main(["--scene", "breakout", "--frames", "30", "--headless"]) == 0
    out = capsys.readouterr().out
    assert "breakout" in out and "score" in out
    assert "\u2584" in out  # the brick wall is painted
    assert "paddle" in out


def test_unknown_scene_is_a_usage_error(capsys):
    assert main(["--scene", "nope"]) == 2
    assert "usage:" in capsys.readouterr().out


def test_scene_output_is_painter_bytes():
    output = scene_output("menu", width=80, height=24, phase=8)
    assert output and "\x1b[" in output
