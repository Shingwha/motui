"""The shipped showcase boots in every entry mode at both sizes."""

from __future__ import annotations

import sys

import pytest

from motui.demo import SCENES, main, render_scene, scene_output
from motui.demo.version import DEMO_BAND


def test_every_scene_renders_a_bounded_frame():
    assert {"splash", "menu", "snake", "dashboard", "gallery"} <= set(SCENES)
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
        assert f"\u2500\u2500 /{name} " in out, name
    assert "Snake" in out
    assert f"{DEMO_BAND} in one page" in out
    assert "score" in out and "snake" in out
    assert "motui dashboard" in out and "requests" in out


def test_the_piped_entry_prints_the_menu(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["motui"])
    assert main() == 0
    out = capsys.readouterr().out
    assert "Snake" in out and "Gallery" in out and "showcase" in out


def test_splash_entry_modes(capsys):
    for args in (
        ["--scene", "splash", "--headless"],
        ["--scene", "splash", "--frames", "60", "--headless"],
    ):
        assert main(args) == 0
        out = capsys.readouterr().out
        assert "press any key" in out
        assert "Snake" not in out


@pytest.mark.parametrize(
    ("args", "needles"),
    [
        (
            ["--scene", "snake", "--frames", "30", "--headless"],
            ["snake", "score", "arrows/wasd"],
        ),
        (
            ["--scene", "dashboard", "--frames", "30", "--headless"],
            ["motui dashboard", "tick 0050", "throughput", "requests", "events"],
        ),
        (
            ["--scene", "gallery", "--headless"],
            [f"{DEMO_BAND} in one page", "tab focus"],
        ),
    ],
    ids=["snake", "dashboard", "gallery"],
)
def test_headless_scenes_replay(capsys, args, needles):
    assert main(args) == 0
    out = capsys.readouterr().out
    for needle in needles:
        assert needle in out, (needle, args)
    if "snake" in args:
        assert any(block in out for block in "\u2580\u2584\u2588")


def test_unknown_scene_is_a_usage_error(capsys):
    assert main(["--scene", "nope"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_scene_output_is_painter_bytes():
    output = scene_output("menu", width=80, height=24, phase=8)
    assert output and "\x1b[" in output
