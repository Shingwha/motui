"""Layout and scroll value tests, pinned against the 1.x ScrollState."""

from __future__ import annotations

import random
from dataclasses import FrozenInstanceError

import pytest

from motui.kernel.layout import Constraints, Scroll, ScrollAxis, ScrollState, as_constraints


def test_layout_exports_as_constraints() -> None:
    import motui.kernel.layout as layout

    assert as_constraints in vars(layout).values()
    assert "as_constraints" in layout.__all__


def test_constraints_defaults_and_validation() -> None:
    assert Constraints() == Constraints(width=0, max_height=None)
    assert Constraints(width=80, max_height=24).max_height == 24
    with pytest.raises(ValueError):
        Constraints(width=-1)
    with pytest.raises(ValueError):
        Constraints(width=1, max_height=-1)
    with pytest.raises(FrozenInstanceError):
        Constraints().width = 1  # type: ignore[misc]


def test_max_offset() -> None:
    assert ScrollAxis(content=100, viewport=10).max_offset == 90
    assert ScrollAxis(content=5, viewport=10).max_offset == 0
    assert ScrollAxis().max_offset == 0


def test_clamp_moves_into_range_and_returns_a_new_value() -> None:
    over = ScrollAxis(offset=99, content=100, viewport=10)
    clamped = over.clamp()
    assert clamped.offset == 90
    assert over.offset == 99  # the receiver is untouched

    assert ScrollAxis(offset=-4, content=100, viewport=10).clamp().offset == 0
    assert ScrollAxis(offset=42, content=100, viewport=10).clamp().offset == 42
    assert ScrollAxis(offset=99, content=5, viewport=10).clamp().offset == 0


def test_clamp_matches_scroll_state_without_stickiness() -> None:
    rng = random.Random(99)
    for _ in range(500):
        offset = rng.randint(-20, 80)
        content = rng.randint(0, 60)
        viewport = rng.randint(0, 60)
        state = ScrollState(
            offset=offset, content_height=content, viewport_height=viewport
        )
        state.clamp()
        value = ScrollAxis(offset=offset, content=content, viewport=viewport).clamp()
        assert value.offset == state.offset


def test_sticky_follows_the_extent_it_can_see() -> None:
    # At or past the bottom, sticky stays at the bottom.
    assert ScrollAxis(offset=90, content=100, viewport=10, sticky=True).clamp().offset == 90
    # Detached (offset above the top but below the bottom) stays put: the
    # value has no previous extent to compare against in this wave.
    assert ScrollAxis(offset=3, content=100, viewport=10, sticky=True).clamp().offset == 3
    # Stickiness never changes the other axis' answer.
    assert ScrollAxis(offset=3, content=100, viewport=10, sticky=False).clamp().offset == 3


def test_reveal_moves_up() -> None:
    axis = ScrollAxis(offset=10, content=20, viewport=5)
    assert axis.reveal(3).offset == 3
    assert axis.offset == 10


def test_reveal_moves_down_minimally() -> None:
    axis = ScrollAxis(offset=2, content=20, viewport=5)
    assert axis.reveal(10).offset == 6  # target is the last visible row
    assert axis.reveal(6).offset == 2  # already the last visible row
    assert axis.reveal(2).offset == 2


def test_reveal_leaves_a_visible_row_alone() -> None:
    axis = ScrollAxis(offset=5, content=20, viewport=5)
    assert axis.reveal(7) == axis


def test_reveal_with_empty_content_or_viewport() -> None:
    empty = ScrollAxis(offset=2, content=0, viewport=5)
    assert empty.reveal(0) == empty
    blind = ScrollAxis(offset=2, content=20, viewport=0)
    assert blind.reveal(3) == blind


def test_reveal_clamps_the_row_and_the_result() -> None:
    assert ScrollAxis(offset=10, content=20, viewport=5).reveal(-5).offset == 0
    assert ScrollAxis(offset=10, content=20, viewport=5).reveal(999).offset == 15
    # An offset outside the extent is corrected by the move.
    assert ScrollAxis(offset=99, content=20, viewport=5).reveal(3).offset == 3


def test_reveal_offsets_match_scroll_state() -> None:
    cases = [
        # offset, content, viewport, row
        (10, 20, 5, 3),  # above
        (2, 20, 5, 10),  # below
        (2, 20, 5, 6),  # already the last visible row
        (5, 20, 5, 7),  # visible
        (2, 0, 5, 0),  # empty content
        (2, 20, 0, 3),  # empty viewport
        (10, 20, 5, -5),  # negative row
        (10, 20, 5, 999),  # row past the content
    ]
    for offset, content, viewport, row in cases:
        state = ScrollState(
            offset=offset, content_height=content, viewport_height=viewport
        )
        state.reveal(row)
        value = ScrollAxis(offset=offset, content=content, viewport=viewport)
        assert value.reveal(row).offset == state.offset


def test_thumb_none_when_nothing_to_map() -> None:
    assert ScrollAxis(content=5, viewport=5).thumb(10) is None
    assert ScrollAxis(content=4, viewport=5).thumb(10) is None
    assert ScrollAxis(content=100, viewport=10).thumb(0) is None
    # A min_length that shaves the rounded length away leaves no thumb.
    assert ScrollAxis(content=1000, viewport=1).thumb(10, min_length=0) is None


def test_thumb_uses_half_even_rounding() -> None:
    # 5 * 5 / 10 == 2.5, and builtin round takes it to the even 2.
    assert ScrollAxis(content=10, viewport=5).thumb(5) == (0, 2)
    assert ScrollAxis(content=100, viewport=10).thumb(20) == (0, 2)
    assert ScrollAxis(offset=90, content=100, viewport=10).thumb(20) == (18, 2)
    assert ScrollAxis(offset=45, content=100, viewport=10).thumb(20) == (9, 2)


def test_thumb_matches_scroll_state() -> None:
    rng = random.Random(1234)
    for _ in range(1000):
        content = rng.randint(0, 60)
        viewport = rng.randint(0, 60)
        offset = rng.randint(-10, 70)
        track = rng.randint(0, 40)
        min_length = rng.randint(0, 4)
        state = ScrollState(
            offset=offset, content_height=content, viewport_height=viewport
        )
        expected = state.thumb(track, min_length)
        value = ScrollAxis(offset=offset, content=content, viewport=viewport)
        assert value.thumb(track, min_length) == expected


def test_scroll_defaults_and_axis_independence() -> None:
    scroll = Scroll()
    assert scroll.x == ScrollAxis()
    assert scroll.y == ScrollAxis(sticky=True)
    assert scroll.y.sticky and not scroll.x.sticky

    moved_x = scroll.with_x(ScrollAxis(offset=3, content=10, viewport=5))
    assert moved_x.x.offset == 3
    assert moved_x.y is scroll.y

    moved_y = scroll.with_y(ScrollAxis(offset=4, content=10, viewport=5))
    assert moved_y.y.offset == 4
    assert moved_y.x is scroll.x

    assert scroll.x.offset == 0 and scroll.y.offset == 0


def test_scroll_is_frozen() -> None:
    scroll = Scroll()
    with pytest.raises(FrozenInstanceError):
        scroll.y = ScrollAxis()  # type: ignore[misc]
