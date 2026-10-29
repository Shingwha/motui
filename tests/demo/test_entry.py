"""The shipped Signal Lab boots in every entry mode at both target sizes."""

from __future__ import annotations

import sys

from motui.demo import SCENES, main, render_scene, scene_output
from motui.demo.version import DEMO_BAND


def test_every_scene_renders_a_bounded_frame():
    assert len(SCENES) == 9 and "snake" not in SCENES
    for name in SCENES:
        for width, height in ((80, 24), (100, 30)):
            text = render_scene(name, width=width, height=height, phase=240)
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
        assert f"── /{name} " in out, name
    assert "Snake" not in out and "snake" not in out
    assert f"{DEMO_BAND} in one page" in out
    assert "DEEP SPACE UPLINK" in out and "SIGNAL LAB" in out


def test_piped_entry_prints_the_lab_home(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["motui"])
    assert main() == 0
    out = capsys.readouterr().out
    assert "EXPERIMENT INDEX" in out and "SIGNAL LAB" in out
    assert "Component gallery" in out


def test_splash_entry_modes(capsys):
    for args in (
        ["--scene", "splash", "--headless"],
        ["--scene", "splash", "--frames", "240", "--headless"],
    ):
        assert main(args) == 0
        out = capsys.readouterr().out
        assert "space remix" in out and "86 STARS" in out
        assert "Snake" not in out


def test_headless_scenes_replay(capsys):
    for args, needles in [
        (
            ["--scene", "dashboard", "--frames", "400", "--headless"],
            ["DEEP SPACE UPLINK", "REROUTING TRAFFIC", "MISSION EVENTS"],
        ),
        (
            ["--scene", "gallery", "--headless"],
            [f"{DEMO_BAND} in one page", "tab focus"],
        ),
        (
            ["--scene", "themes", "--headless"],
            ["SKIN LAB", "GLOBAL THEME", "signal"],
        ),
    ]:
        assert main(args) == 0
        out = capsys.readouterr().out
        for needle in needles:
            assert needle in out, (needle, args)


def test_unknown_scene_is_a_usage_error(capsys):
    assert main(["--scene", "nope"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_scene_output_is_painter_bytes():
    output = scene_output("menu", width=80, height=24, phase=8)
    assert output and "\x1b[" in output
