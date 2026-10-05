"""Run the README's code samples: the docs cannot rot silently.

The quickstart, the mocode integration shape, and the Theme / keymap
snippets are parsed straight out of ``README.md`` and executed here --
the code under test is the documented code, not a copy that can drift.
Every snippet runs headless on a ``HeadlessScreen`` with a
``ScriptedKeys`` source, so nothing touches a real terminal.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import mocode_tui
from mocode_tui import HeadlessScreen, Key, Option, Paste, ScriptedKeys, Style, TUI

README = Path(__file__).resolve().parent.parent / "README.md"


def _blocks_under(heading: str) -> list[str]:
    """Every fenced ``python`` block that follows ``heading`` in README.md."""
    _, _, rest = README.read_text(encoding="utf-8").partition(heading)
    assert rest, heading
    return re.findall(r"```python\n(.*?)```", rest, re.S)


def _scripted_tui(keys, monkeypatch, width=80, height=24):
    """Patch ``mocode_tui.TUI`` so a snippet's ``TUI()`` replays ``keys``.

    The snippets import ``TUI`` from the package root at exec time, so
    patching the root attribute rebinds their import; the built driver is
    parked in the returned holder for the test to inspect.
    """
    holder: dict[str, TUI] = {}

    def factory(**kwargs):
        holder["tui"] = TUI(
            screen=HeadlessScreen(width, height), keys=keys, interactive=False
        )
        return holder["tui"]

    monkeypatch.setattr(mocode_tui, "TUI", factory)
    return holder


def _run(source: str, **namespace) -> dict:
    """Exec one README snippet; extra keywords seed its globals."""
    scope = {"__name__": "readme_snippet"}
    scope.update(namespace)
    exec(compile(source, "README.md", "exec"), scope)
    return scope


def _type(text: str) -> list:
    """A scripted typing run of ``text``."""
    return [Key(char, char) for char in text]


def _screen_text(tui: TUI) -> list[str]:
    return [row.text for row in tui.rows()]


# ---------------------------------------------------------------------------
# The quickstart
# ---------------------------------------------------------------------------


def test_readme_quickstart_runs_headless(monkeypatch):
    """The 15-line quickstart: type, submit, and the message lands."""
    keys = ScriptedKeys([*_type("hello from the readme"), Key("enter"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    tui = holder["tui"]
    assert any("hello from the readme" in row for row in _screen_text(tui))
    # The pinned footer survived the run: the box is top rule + editor +
    # bottom rule, and the status line closes the tail.
    assert tui.get("composer-top") and tui.get("composer-status")


def test_readme_quickstart_editing_keys_reach_the_editor(monkeypatch):
    """Backspace and friends route through the composer's editor keymap."""
    keys = ScriptedKeys([*_type("ab"), Key("backspace"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    # "ab" minus the backspaced "b" is still in the editor, un-submitted.
    editor = holder["tui"].get("composer-input").component
    assert editor.value == "a"


def test_readme_quickstart_survives_a_paste(monkeypatch):
    """A bracketed Paste inserts its text instead of crashing the loop."""
    keys = ScriptedKeys([Paste("from a paste"), Key("enter"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    assert any("from a paste" in row for row in _screen_text(holder["tui"]))


# ---------------------------------------------------------------------------
# The mocode integration shape
# ---------------------------------------------------------------------------


class _FakeModel:
    """A two-chunk "model": no sleeps, no network, deterministic text."""

    async def stream(self, prompt: str):
        for chunk in (f"echo: {prompt}", " -- done"):
            yield chunk


def test_readme_integration_shape_runs_headless(monkeypatch):
    """The documented host shape: palette split, editor, streaming turn."""
    commands = [Option("/clear", value="clear"), Option("/quit", value="quit")]
    scope = _run(
        _blocks_under("## Integrating with a host")[1],
        COMMANDS=commands,
        model=_FakeModel(),
    )
    keys = ScriptedKeys([
        *_type("ship it"),
        Key("enter"),            # the submit gesture: a streaming turn
        Key("/", "/"),           # a freshly typed slash opens the palette
        Key("down"),             # palette navigation stays the palette's
        Key("escape"),           # dismiss it; the typed text stays put
        Key("backspace"),
        Key("backspace"),
        Key("c-c"),
    ])
    tui = TUI(screen=HeadlessScreen(80, 24), keys=keys, interactive=False)
    asyncio.run(tui.run(scope["chat"]))
    rows = _screen_text(tui)
    assert any("ship it" in row for row in rows)               # the user turn
    assert any("echo: ship it -- done" in row for row in rows)  # the streamed reply


# ---------------------------------------------------------------------------
# The Theme and keymap snippets
# ---------------------------------------------------------------------------


def test_readme_theme_snippet_builds_a_variant(monkeypatch):
    """The documented Theme example really restyles every component."""
    scope = _run(_blocks_under("## Styling: Theme")[0])
    theme = scope["theme"]
    assert theme.accent == Style(fg="#ff8800")
    assert theme != mocode_tui.DEFAULT_THEME
    assert theme.border == mocode_tui.DEFAULT_THEME.border  # untouched fields carry over
    rows = scope["Markdown"]("# H", theme=theme).render(80)
    assert rows[0].segments[0].style == Style(fg="#ff8800")  # the heading ladder follows


def test_readme_keymap_snippet_rebinds_one_key(monkeypatch):
    """The documented keymap example rebinds and unbinds single keys."""
    scope = _run(_blocks_under("## Keys and keymaps")[0])
    field = scope["field"]
    field.insert("x")
    assert field.handle_key(Key("c-j"), 80) is True           # rebound: consumes
    assert field.text == ""                                   # c-j was bound to clear
    assert field.handle_key(Key("up"), 80) is False           # unbound: back to the host
