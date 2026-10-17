"""Run the README's code samples: the docs cannot rot silently.

The quickstart, the shell recipe, and the Theme / keymap snippets are
parsed out of ``README.md`` and executed headless on a scripted source --
keys, clicks and motions included.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import motui
from motui import Key, MouseEvent, Paste, Style, TUI
from motui.kernel import HeadlessScreen, ScriptedKeys

README = Path(__file__).resolve().parent.parent / "README.md"


def _blocks_under(heading: str) -> list[str]:
    """Every fenced ``python`` block that follows ``heading`` in README.md."""
    _, _, rest = README.read_text(encoding="utf-8").partition(heading)
    assert rest, heading
    return re.findall(r"```python\n(.*?)```", rest, re.S)


class _YieldingSource:
    """A key source that yields to the loop before every event it reads.

    A live host waits for input while the pump paints the first frame; a
    scripted source that never suspends would let a mouse report arrive
    before anything has composed, and the hit test would resolve nothing.
    ``sleep(0)`` is that wait -- the order a real terminal delivers.
    """

    def __init__(self, source):
        self._source = source

    async def read(self):
        await asyncio.sleep(0)
        return await self._source.read()


def _scripted_tui(keys, monkeypatch, width=80, height=24):
    """Patch ``motui.TUI`` so a snippet's ``TUI()`` replays ``keys``.

    The snippets import ``TUI`` from the package root at exec time, so
    patching the root attribute rebinds their import; the built driver is
    parked in the returned holder for the test to inspect.
    """
    holder: dict[str, TUI] = {}

    def factory(**kwargs):
        holder["tui"] = TUI(
            screen=HeadlessScreen(width, height),
            keys=_YieldingSource(keys),
            interactive=False,
        )
        return holder["tui"]

    monkeypatch.setattr(motui, "TUI", factory)
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


def _motion(x: int, y: int) -> MouseEvent:
    """A button-free motion report at a 0-based cell."""
    return MouseEvent("motion", button=0, x=x, y=y, kind="motion")


def _press(x: int, y: int) -> MouseEvent:
    return MouseEvent("left", button=0, x=x, y=y, kind="press")


def _release(x: int, y: int) -> MouseEvent:
    return MouseEvent("left", button=0, x=x, y=y, kind="release")


def _screen_text(tui: TUI) -> list[str]:
    return [row.text for row in tui.rows]


# ---------------------------------------------------------------------------
# The quickstart
# ---------------------------------------------------------------------------


def test_readme_quickstart_runs_headless(monkeypatch):
    """The quickstart builds its two primitives and renders them."""
    holder = _scripted_tui(ScriptedKeys([Key("c-c")]), monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    tui = holder["tui"]
    assert tui.get("ship") and tui.get("trace")
    rows = _screen_text(tui)
    assert any(row.startswith(" Ship ") for row in rows)
    assert any(row.startswith("[ ] Trace") for row in rows)


def test_readme_quickstart_enter_activates_the_focused_button(monkeypatch):
    """The ring starts on the button: enter lands its activation in chosen."""
    keys = ScriptedKeys([Key("enter"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    assert any("Ship: True" in row for row in _screen_text(holder["tui"]))


def test_readme_quickstart_tab_then_enter_toggles_the_checkbox(monkeypatch):
    """The host's tab moves the focus; enter then flips the checkbox."""
    keys = ScriptedKeys([Key("tab"), Key("enter"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    assert any("Trace: True" in row for row in _screen_text(holder["tui"]))


def test_readme_quickstart_click_dispatches_through_the_pointer(monkeypatch):
    """A press and release on the button's cell is a stationary click."""
    keys = ScriptedKeys([_press(0, 0), _release(0, 0), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    assert any("Ship: True" in row for row in _screen_text(holder["tui"]))


def test_readme_quickstart_hover_follows_the_pointer(monkeypatch):
    """Motion reports move the hover: the row under the pointer is flagged."""
    keys = ScriptedKeys([_motion(0, 0), _motion(0, 1), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    tui = holder["tui"]
    assert tui.get("ship").component.hover is False
    assert tui.get("trace").component.hover is True


def test_readme_quickstart_hover_clears_over_blank_fill(monkeypatch):
    """A motion off the blocks clears the hover."""
    keys = ScriptedKeys([_motion(0, 0), _motion(0, 2), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Quickstart")[0])
    assert holder["tui"].get("ship").component.hover is False


# ---------------------------------------------------------------------------
# The shell recipe
# ---------------------------------------------------------------------------


def test_readme_shell_recipe_runs_headless(monkeypatch):
    """The recipe: a footer Document parked in the band under the panes."""
    keys = ScriptedKeys([*_type("ship it"), Key("enter"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Building your own shell")[0])
    tui = holder["tui"]
    rows = _screen_text(tui)
    assert any("you: ship it" in row for row in rows)   # the submit gesture landed
    assert tui.get("input") and tui.get("status")       # the band's own document
    assert rows[-1].startswith("ready")                 # the status row hugs the bottom


def test_readme_shell_recipe_folds_a_paste_into_the_input(monkeypatch):
    """A bracketed Paste inserts into the editor instead of crashing the loop."""
    keys = ScriptedKeys([Paste("from a paste"), Key("enter"), Key("c-c")])
    holder = _scripted_tui(keys, monkeypatch)
    _run(_blocks_under("## Building your own shell")[0])
    assert any("you: from a paste" in row for row in _screen_text(holder["tui"]))


# ---------------------------------------------------------------------------
# The Theme and keymap snippets
# ---------------------------------------------------------------------------


def test_readme_theme_snippet_builds_a_variant(monkeypatch):
    """The documented Theme example really restyles every component."""
    scope = _run(_blocks_under("## Styling: Theme")[0])
    theme = scope["theme"]
    assert theme.accent == Style(fg="#ff8800")
    assert theme != motui.DEFAULT_THEME
    assert theme.border == motui.DEFAULT_THEME.border  # untouched fields carry over
    rows = scope["Markdown"]("# H", theme=theme).render(80)
    assert rows[0].segments[0].style == Style(fg="#ff8800", underline=True)  # h1 follows


def test_readme_keymap_snippet_rebinds_one_key(monkeypatch):
    """The documented keymap example rebinds and unbinds single keys."""
    scope = _run(_blocks_under("## Keys and keymaps")[0])
    field = scope["field"]
    field.insert("x")
    assert field.handle(Key("c-j")) is True           # rebound: consumes
    assert field.text == ""                                   # c-j was bound to clear
    assert field.handle(Key("up")) is False           # unbound: back to the host
