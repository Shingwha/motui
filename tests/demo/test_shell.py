"""The Signal Lab shell: navigation, transitions, global themes and input."""

from __future__ import annotations

from motui.demo.registry import TILES
from motui.demo.sections import ComponentsScene, LayoutScene, TerminalScene
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


def test_home_routes_every_keyboard_navigation_path():
    menu = _menu()
    menu.on_key(KeyEvent("down"))
    menu.on_key(KeyEvent("right"))
    assert menu.on_key(KeyEvent("enter")) == "motion"
    assert _menu().on_key(KeyEvent("4")) == "dashboard"
    assert _menu().on_key(KeyEvent("g")) == "gallery"
    clicked = _menu()
    row, col, _height, _width = clicked.rects[2]
    assert clicked.on_click(Pos(x=col + 1, y=row)) == "motion"


def test_home_tab_and_reverse_tab_cover_the_whole_index():
    menu = _menu()
    for expected in range(1, len(TILES)):
        menu.on_key(KeyEvent("tab"))
        assert menu.index == expected
    menu.on_key(KeyEvent("tab"))
    assert menu.index == 0
    menu.on_key(KeyEvent("s-tab"))
    assert menu.index == len(TILES) - 1


def test_home_selection_survives_round_trips_and_global_theme_changes():
    showcase = Showcase("menu")
    showcase.on_key(KeyEvent("down"))
    showcase.on_key(KeyEvent("down"))
    showcase.on_key(KeyEvent("enter"))
    assert showcase.scene == "motion"
    showcase.on_key(KeyEvent("escape"))
    assert showcase._scenes["menu"].index == 2
    showcase.on_key(KeyEvent("ctrl+t"))
    assert showcase._scenes["menu"].index == 2


def _transition_frames() -> list[str]:
    showcase = Showcase("menu")
    showcase.switch("dashboard")
    frames = []
    for _ in range(20):
        showcase.tick()
        frames.append(_frame(showcase))
    return frames


def test_randomized_transition_replays_and_lands_on_the_static_frame():
    first, second = _transition_frames(), _transition_frames()
    assert first == second
    assert first[0] != first[8] != first[-1]
    static = Showcase("dashboard")
    for _ in range(20):
        static.tick()
    assert first[-1] == _frame(static)


def test_every_experiment_enters_renders_and_returns_home():
    for spec in TILES:
        showcase = Showcase(spec.name)
        assert _frame(showcase).strip()
        showcase.on_key(KeyEvent("escape"))
        assert showcase.scene == "menu"
        for _ in range(20):
            showcase.tick()
        assert "SIGNAL LAB" in _frame(showcase)


def test_help_calm_and_global_theme_shortcuts_work_from_any_scene():
    showcase = Showcase("dashboard")
    showcase.on_key(KeyEvent("f1"))
    assert showcase.help_open
    phase = showcase.phase
    showcase.tick()
    assert showcase.phase == phase
    showcase.on_key(KeyEvent("escape"))
    showcase.on_key(KeyEvent("f2"))
    showcase.tick()
    assert showcase.phase == phase and not showcase.motion
    showcase.on_key(KeyEvent("ctrl+t"))
    assert showcase.theme_index == 1 and showcase.scene == "dashboard"
    assert showcase.theme_spec.name == "aurora"
    assert "aurora" in showcase.theme_spec.name


def test_themes_scene_applies_the_palette_to_the_whole_shell():
    showcase = Showcase("themes")
    before = showcase.theme
    showcase.on_key(KeyEvent("right"))
    assert showcase.theme_index == 1 and showcase.theme is not before
    showcase.on_key(KeyEvent("5"))
    assert showcase.theme_index == 4 and showcase.theme_spec.name == "mono"
    showcase.switch("motion")
    assert showcase.theme is showcase._scenes["motion"].theme


def test_terminal_probe_is_fully_keyboard_operable():
    scene = TerminalScene(Theme.dark())
    scene.render(FRAME, 0)
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("down"))
    scene.on_key(KeyEvent("enter"))
    assert scene.feed[-1] == "enter (1, 1)"
    scene.on_key(KeyEvent("space"))
    assert scene.feed[-1] == "space (1, 1)"
    text = _text(scene.render(FRAME, 0))
    assert "X-RAY" in text and "probe" in text


def test_components_controls_answer_their_keys():
    scene = ComponentsScene(Theme.dark())
    scene.render(FRAME, 0)
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("tab"))
    for _ in range(3):
        scene.on_key(KeyEvent("s"))
    assert scene.sort_column == 2
    rows = [row[0] for row in scene.table.rows]
    assert rows.index("borealis") < rows.index("cygnus")
    scene.on_key(KeyEvent("tab"))
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("right"))
    scene.on_key(KeyEvent("tab"))
    scene.on_key(KeyEvent("enter"))
    assert scene.toast_state is not None and "preset saved" in scene.toast_state[0]


def test_layout_drills_reach_both_ends_and_replay_deterministically():
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
    assert "recover a clean lock" in first_code
    assert "on schedule" in first_wide
