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
    # The components and layout sections are real scenes now (W2-b); the
    # two placeholders this wave left behind are terminal and themes.
    for name in ("terminal", "themes"):
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


def _driven_components() -> str:
    """One components frame after a fixed key script (tabs, sort, modal)."""
    showcase = Showcase("components")
    scene = showcase._scenes["components"]
    scene.render(Constraints(width=100, max_height=30), 0)
    for key in ("right", "right", "tab", "tab", "enter", "escape"):
        scene.on_key(KeyEvent(key))
    return _frame(showcase, width=100, height=30)


def test_the_components_playground_drives_and_replays_deterministically():
    first, second = _driven_components(), _driven_components()
    assert first == second  # the modal path is a pure function of the keys
    assert "shipment cancelled" in first  # the modal resolved, not the frame
    fresh = Showcase("components")
    assert "Ada Lovelace" in _frame(fresh, width=100, height=30)


def test_the_components_controls_answer_their_keys():
    showcase = Showcase("components")
    scene = showcase._scenes["components"]
    scene.render(Constraints(width=100, max_height=30), 0)
    scene.on_key(KeyEvent("right"))  # the strip owns the focus: page -> data
    scene.on_key(KeyEvent("tab"))  # focus -> the table
    scene.on_key(KeyEvent("s"))  # the sort cycles column by column...
    scene.on_key(KeyEvent("s"))
    scene.on_key(KeyEvent("s"))  # ...third press: by ripe asc
    text = _frame(showcase, width=100, height=30)
    assert "crates.sort_by(2)" in text and "by ripe asc" in text
    lines = text.splitlines()
    bergamot = next(i for i, row in enumerate(lines) if "│ bergamot" in row)
    cherries = next(i for i, row in enumerate(lines) if "│ cherries" in row)
    assert bergamot < cherries  # 0.31 sorts before 0.95: really reordered
    scene.on_key(KeyEvent("tab"))  # focus -> the strip
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("right"))  # page -> overlays
    scene.on_key(KeyEvent("tab"))
    scene.on_key(KeyEvent("enter"))  # the save button
    assert "saved to disk" in _frame(showcase, width=100, height=30)


def test_the_layout_drills_reach_both_ends_and_replay_deterministically():
    def driven() -> tuple[str, str, object, object]:
        showcase = Showcase("layout")
        scene = showcase._scenes["layout"]
        scene.render(Constraints(width=100, max_height=30), 0)
        scene.on_key(KeyEvent("4"))  # the wide table
        scene.render(Constraints(width=100, max_height=30), 0)
        wide = scene._wide_scroll
        wide.scroll_x_to_end()
        wide_frame = _frame(showcase, width=100, height=30)
        scene.on_key(KeyEvent("3"))  # the long code
        scene.render(Constraints(width=100, max_height=30), 0)
        code = scene._code_scroll
        for _ in range(60):
            code.scroll_x_by(4)
        return wide_frame, _frame(showcase, width=100, height=30), wide, code

    first_wide, first_code, wide, code = driven()
    second_wide, second_code, _wide2, _code2 = driven()
    assert (first_wide, first_code) == (second_wide, second_code)
    assert wide.x_offset == wide.total_columns - wide.viewport_width
    assert code.x_offset == code.total_columns - code.viewport_width
    assert "harbour master" in first_code  # the long line's tail is reachable
    assert "on schedule" in first_wide  # the wide table's last column is there
