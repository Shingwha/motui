"""The shell: Home tiles, wipe, section round trips and global help."""

from __future__ import annotations

import pytest

from motui.demo.registry import TILES
from motui.demo.sections import (
    ComponentsScene,
    LayoutScene,
    TerminalScene,
    ThemesScene,
)
from motui.demo.sections.menu import MenuScene
from motui.demo.shell import Showcase
from motui.kernel.cell import Surface
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme

FRAME = Constraints(width=100, max_height=30)


def _frame(showcase: Showcase, width: int = 80, height: int = 24) -> str:
    surface = showcase.render(Constraints(width=width, max_height=height))
    return "\n".join(row.text for row in surface)


def _text(surface: Surface) -> str:
    return "\n".join(row.text for row in surface)


def _menu() -> MenuScene:
    scene = MenuScene(Theme.dark(), TILES)
    scene.render(Constraints(width=80, max_height=24), 0)
    return scene


def test_the_home_tiles_route_keys_and_clicks_to_their_sections():
    menu = _menu()
    menu.on_key(KeyEvent("down"))  # components -> dashboard: a row jump
    menu.on_key(KeyEvent("right"))  # dashboard -> terminal
    assert menu.on_key(KeyEvent("enter")) == "terminal"

    fresh = _menu()
    fresh.on_key(KeyEvent("left"))  # wraps to the last tile of the grid
    assert fresh.on_key(KeyEvent("enter")) == "themes"

    clicked = _menu()
    assert clicked.on_click(Pos(x=10, y=5)) == "components"
    assert clicked.on_key(KeyEvent("s")) == "snake"
    assert clicked.on_key(KeyEvent("g")) == "gallery"


def _wiped_frames() -> list[str]:
    """Twelve frames of a menu -> dashboard wipe, one per tick."""
    showcase = Showcase("menu")
    showcase.switch("dashboard")
    frames = []
    for _ in range(12):
        showcase.tick()
        frames.append(_frame(showcase))
    return frames


def test_a_wipe_replays_tick_for_tick_and_lands_on_the_static_frame():
    first, second = _wiped_frames(), _wiped_frames()
    assert first == second  # the mask is a pure function of the phase
    assert first[0] != first[4] != first[8]  # the middle frames really move
    static = Showcase("dashboard")
    for _ in range(12):
        static.tick()
    assert first[-1] == _frame(static)  # the tail is the plain dashboard


def test_the_wipe_holds_the_old_scene_at_its_leaving_phase():
    showcase = Showcase("dashboard")
    for _ in range(40):
        showcase.tick()
    before = _frame(showcase)
    showcase.switch("menu")
    after = _frame(showcase)
    cut = 80 * (showcase.phase + 1) // 9
    assert [row[cut:] for row in after.splitlines()] == [
        row[cut:] for row in before.splitlines()
    ]


@pytest.mark.parametrize("name", [spec.name for spec in TILES])
def test_every_section_enters_renders_and_returns_home(name):
    showcase = Showcase(name)
    assert _frame(showcase).strip()
    showcase.on_key(KeyEvent("escape"))
    assert showcase.scene == "menu"
    assert _frame(showcase)


def test_the_help_overlay_opens_pauses_and_closes():
    showcase = Showcase("menu")
    showcase.on_key(KeyEvent("f1"))
    assert showcase.help_open
    phase = showcase.phase
    showcase.tick()
    assert showcase.phase == phase  # help pauses the clock
    text = _frame(showcase)
    assert "choose a section" in text and "global:" in text
    showcase.on_key(KeyEvent("escape"))
    assert not showcase.help_open


def _terminal_scene() -> TerminalScene:
    scene = TerminalScene(Theme.dark())
    scene.render(FRAME, 0)
    scene.on_click(Pos(x=20, y=10))
    scene.on_click(Pos(x=21, y=11))
    return scene


def test_the_terminal_report_dissects_the_pipe_and_replays():
    scene = _terminal_scene()
    text = _text(scene.render(FRAME, 0))
    assert "100 x 30 cells" in text
    assert "\\x1b[?2026h" in text and "\\x1b[?2026l" in text
    assert "\\x1b[?1000h" in text
    assert "octant" in text and "not probed" in text
    assert scene.feed[-1] == "click (21, 11)"
    assert _text(scene.render(FRAME, 0)) == text


def test_the_themes_section_switches_skins_live():
    scene = ThemesScene(Theme.dark())
    dark = _text(scene.render(FRAME, 0))
    scene.on_key(KeyEvent("right"))
    light = _text(scene.render(FRAME, 0))
    assert scene.tabs.index == 1
    assert "Theme.dark()" in dark and "Theme.light()" in light

    scene.on_key(KeyEvent("4"))
    sepia = _text(scene.render(FRAME, 0))
    assert scene.tabs.index == 3 and "from_palette" in sepia

    scene.on_key(KeyEvent("c"))
    compare = _text(scene.render(FRAME, 0))
    assert scene.compare
    assert all(name in compare for name in ("dark", "light", "flat", "sepia"))

    clicked = ThemesScene(Theme.dark())
    clicked.render(FRAME, 0)
    clicked.on_click(Pos(x=8, y=1))
    assert clicked.tabs.index == 1


def _driven_components() -> tuple[ComponentsScene, str]:
    scene = ComponentsScene(Theme.dark())
    scene.render(FRAME, 0)
    for key in ("right", "right", "tab", "tab", "enter", "escape"):
        scene.on_key(KeyEvent(key))
    return scene, _text(scene.render(FRAME, 0))


def test_the_components_playground_drives_and_replays_deterministically():
    first, first_text = _driven_components()
    second, second_text = _driven_components()
    assert first_text == second_text
    assert not first.modal and not second.modal
    fresh = ComponentsScene(Theme.dark())
    assert "Ada Lovelace" in _text(fresh.render(FRAME, 0))


def test_the_components_controls_answer_their_keys():
    scene = ComponentsScene(Theme.dark())
    scene.render(FRAME, 0)
    scene.on_key(KeyEvent("right"))  # the strip owns the focus: page -> data
    scene.on_key(KeyEvent("tab"))  # focus -> the table
    for _ in range(3):
        scene.on_key(KeyEvent("s"))
    assert scene.sort_column == 2
    rows = [row[0] for row in scene.table.rows]
    assert rows.index("bergamot") < rows.index("cherries")

    scene.on_key(KeyEvent("tab"))
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("tab"))
    scene.on_key(KeyEvent("enter"))
    assert scene.toast_state is not None and "saved to disk" in scene.toast_state[0]


def test_the_layout_drills_reach_both_ends_and_replay_deterministically():
    def driven() -> tuple[str, str, object, object]:
        scene = LayoutScene(Theme.dark())
        scene.render(FRAME, 0)
        scene.on_key(KeyEvent("4"))
        scene.render(FRAME, 0)
        wide = scene.wide_scroll
        wide.scroll_x_to_end()
        wide_frame = _text(scene.render(FRAME, 0))
        scene.on_key(KeyEvent("3"))
        scene.render(FRAME, 0)
        code = scene.code_scroll
        for _ in range(60):
            code.scroll_x_by(4)
        return wide_frame, _text(scene.render(FRAME, 0)), wide, code

    first_wide, first_code, wide, code = driven()
    second_wide, second_code, _wide2, _code2 = driven()
    assert (first_wide, first_code) == (second_wide, second_code)
    assert wide.x_offset == wide.total_columns - wide.viewport_width
    assert code.x_offset == code.total_columns - code.viewport_width
    assert "harbour master" in first_code
    assert "on schedule" in first_wide
