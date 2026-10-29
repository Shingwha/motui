"""The registry is the one source for Home, commands and headless scenes."""

from __future__ import annotations

from motui.demo import SCENES
from motui.demo.registry import JUMPABLE, SPEC_BY_NAME, SPECS, TILES
from motui.demo.sections.menu import MenuScene
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme


def test_registry_contains_six_experiments_and_the_archive_without_snake():
    assert tuple(spec.name for spec in SPECS) == SCENES
    assert set(SPEC_BY_NAME) == set(SCENES)
    assert len(TILES) == 6
    assert {spec.name for spec in TILES} == {
        "components",
        "layout",
        "motion",
        "dashboard",
        "terminal",
        "themes",
    }
    assert "splash" not in JUMPABLE
    assert "gallery" in JUMPABLE
    assert "snake" not in SCENES
    assert all(spec.title and spec.blurb for spec in SPECS)


def test_menu_is_built_from_the_six_experiment_specs():
    menu = MenuScene(Theme.dark(), TILES)
    menu.render(Constraints(width=80, max_height=24), 0)
    assert [spec.name for spec in menu.tiles] == [spec.name for spec in TILES]
    assert len(menu.rects) == 6
