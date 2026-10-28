"""The new shell: Home tiles, the wipe, the placeholders, the coverage.

``test_smoke`` boots the entries and ``test_demo_scenes`` pins the scene
mechanics; this file pins what the shell wave added: the tile grid's
routing, the wipe's tick-for-tick replay, the placeholder round trip and
the SCENES/golden alignment.
"""

from __future__ import annotations

from pathlib import Path

from motui.demo import SCENES
from motui.demo.shell import Showcase
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "semantic"


def _frame(showcase: Showcase, width: int = 80, height: int = 24) -> str:
    surface = showcase.render(Constraints(width=width, max_height=height))
    return "\n".join(row.text for row in surface)


def _wiped_frames() -> list[str]:
    """Twelve frames of a menu -> dashboard wipe, one per tick."""
    showcase = Showcase("menu")
    showcase.switch("dashboard")
    frames = []
    for _ in range(12):
        showcase.tick()
        frames.append(_frame(showcase))
    return frames


def test_the_home_tiles_route_keys_and_clicks_to_their_sections():
    menu = Showcase("menu")._scenes["menu"]
    menu.render(Constraints(width=80, max_height=24), 0)
    menu.on_key(KeyEvent("down"))  # components -> dashboard: a row jump
    menu.on_key(KeyEvent("right"))  # dashboard -> terminal
    assert menu.on_key(KeyEvent("enter")) == "terminal"
    fresh = Showcase("menu")._scenes["menu"]
    fresh.render(Constraints(width=80, max_height=24), 0)
    fresh.on_key(KeyEvent("left"))  # wraps to the last tile of the grid
    assert fresh.on_key(KeyEvent("enter")) == "themes"
    clicked = Showcase("menu")._scenes["menu"]
    clicked.render(Constraints(width=80, max_height=24), 0)
    assert clicked.on_click(Pos(x=10, y=5)) == "components"


def test_a_wipe_replays_tick_for_tick_and_lands_on_the_static_frame():
    first, second = _wiped_frames(), _wiped_frames()
    assert first == second  # the mask is a pure function of the phase
    assert first[0] != first[4] != first[8]  # the middle frames really move
    static = Showcase("dashboard")
    for _ in range(12):
        static.tick()
    assert first[-1] == _frame(static)  # the tail is the plain dashboard


def test_the_placeholder_sections_enter_render_and_return_home():
    for name in ("components", "layout", "terminal", "themes"):
        showcase = Showcase(name)
        text = _frame(showcase)
        assert "under construction" in text, name
        showcase.on_key(KeyEvent("escape"))
        assert showcase.scene == "menu"
        assert _frame(showcase)  # Home renders after the round trip


def test_scenes_and_the_golden_set_cover_each_other():
    expected = {f"{name}.txt" for name in SCENES}
    found = {path.name for path in GOLDEN.glob("*.txt")}
    assert found == expected
