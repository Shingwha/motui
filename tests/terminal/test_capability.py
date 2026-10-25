"""Terminal capability probes: the color-mode matrix, size and auto theme.

``detect_color_mode`` reads an explicit mapping (or the process environment),
``terminal_size`` falls back to 80x24 off a terminal, and ``auto_theme`` is
the one convenience that reads :data:`os.environ` for :meth:`Theme.auto`.
"""

from __future__ import annotations

from motui.kernel.theme import Theme
from motui.terminal.capability import auto_theme, detect_color_mode


def test_detect_color_mode_env_matrix():
    cases = [
        ({"NO_COLOR": "1"}, "none"),
        ({"NO_COLOR": ""}, "truecolor"),
        ({"NO_COLOR": "", "TERM": "xterm-256color"}, "256"),
        ({"NO_COLOR": "", "COLORTERM": "truecolor"}, "truecolor"),
        ({"TERM": "dumb"}, "none"),
        ({"TERM": "dumb", "COLORTERM": "truecolor"}, "none"),
        ({"COLORTERM": "truecolor", "TERM": "xterm-256color"}, "truecolor"),
        ({"COLORTERM": "24bit"}, "truecolor"),
        ({"COLORTERM": "unknown"}, "truecolor"),
        ({"TERM": "xterm-256color"}, "256"),
        ({"TERM": "screen-256color"}, "256"),
        ({"TERM": "xterm"}, "truecolor"),
        ({}, "truecolor"),
    ]
    for env, expected in cases:
        assert detect_color_mode(env) == expected


def test_detect_color_mode_defaults_to_the_process_environment(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert detect_color_mode() == "none"
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("COLORTERM", raising=False)
    assert detect_color_mode() == "256"


def test_auto_theme_reads_the_process_environment(monkeypatch):
    monkeypatch.setenv("TERM_BACKGROUND", "light")
    assert auto_theme() == Theme.light()
    monkeypatch.delenv("TERM_BACKGROUND")
    monkeypatch.setenv("COLORFGBG", "15;0")
    assert auto_theme() == Theme.dark()


def test_auto_theme_takes_an_explicit_environment():
    assert auto_theme({"TERM_BACKGROUND": "black"}) == Theme.dark()
    assert auto_theme({"TERM_BACKGROUND": "white"}) == Theme.light()
