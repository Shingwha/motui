"""Geometry value tests: rectangle algebra and split invariants."""

from __future__ import annotations

import random
from dataclasses import FrozenInstanceError

import pytest

from motui.kernel.geom import Axis, Pos, Rect, Size


def _inside(inner: Rect, outer: Rect) -> bool:
    return (
        inner.x >= outer.x
        and inner.y >= outer.y
        and inner.right <= outer.right
        and inner.bottom <= outer.bottom
    )


def _overlaps(a: Rect, b: Rect) -> bool:
    return max(a.x, b.x) < min(a.right, b.right) and max(a.y, b.y) < min(
        a.bottom, b.bottom
    )


def test_values_are_frozen_and_keyword_only() -> None:
    assert Size() == Size(width=0, height=0)
    assert Pos() == Pos(x=0, y=0)
    assert Rect() == Rect(x=0, y=0, width=0, height=0)
    with pytest.raises(FrozenInstanceError):
        Size().width = 1  # type: ignore[misc]
    with pytest.raises(TypeError):
        Rect(0, 0, 1, 1)  # type: ignore[misc]


def test_rect_rejects_negative_extent() -> None:
    with pytest.raises(ValueError):
        Rect(width=-1)
    with pytest.raises(ValueError):
        Rect(height=-1)


def test_edges_and_area() -> None:
    rect = Rect(x=2, y=3, width=4, height=5)
    assert rect.right == 6
    assert rect.bottom == 8
    assert rect.area == 20
    assert Rect().area == 0


def test_contains_is_half_open_on_right_and_bottom() -> None:
    rect = Rect(x=1, y=2, width=3, height=2)
    assert rect.contains(Pos(x=1, y=2))
    assert rect.contains(Pos(x=3, y=3))
    assert not rect.contains(Pos(x=4, y=2))  # right edge
    assert not rect.contains(Pos(x=1, y=4))  # bottom edge
    assert not rect.contains(Pos(x=0, y=2))
    assert not rect.contains(Pos(x=1, y=1))
    assert not Rect().contains(Pos(x=0, y=0))


def test_intersect_disjoint_is_the_empty_rect() -> None:
    a = Rect(x=0, y=0, width=2, height=2)
    b = Rect(x=3, y=0, width=2, height=2)
    assert a.intersect(b) == Rect()
    assert b.intersect(a) == Rect()
    touching = Rect(x=2, y=0, width=2, height=2)
    assert a.intersect(touching) == Rect()


def test_intersect_overlap_is_contained_in_both() -> None:
    a = Rect(x=0, y=0, width=10, height=5)
    b = Rect(x=4, y=2, width=10, height=10)
    overlap = a.intersect(b)
    assert overlap == Rect(x=4, y=2, width=6, height=3)
    assert _inside(overlap, a) and _inside(overlap, b)


def test_intersect_is_commutative_random() -> None:
    rng = random.Random(20261025)
    for _ in range(500):
        a = Rect(
            x=rng.randint(-20, 20),
            y=rng.randint(-20, 20),
            width=rng.randint(0, 30),
            height=rng.randint(0, 30),
        )
        b = Rect(
            x=rng.randint(-20, 20),
            y=rng.randint(-20, 20),
            width=rng.randint(0, 30),
            height=rng.randint(0, 30),
        )
        overlap = a.intersect(b)
        assert overlap == b.intersect(a)
        assert _overlaps(a, b) == (overlap.area > 0)
        if overlap.area:
            assert _inside(overlap, a)
            assert _inside(overlap, b)


def test_split_axis_names_what_moves() -> None:
    rect = Rect(x=1, y=2, width=10, height=6)
    left, right = rect.split(Axis.X, (1, 1))
    assert (left.x, left.width) == (1, 5)
    assert (right.x, right.width) == (6, 5)
    assert left.y == right.y == 2
    assert left.height == right.height == 6

    top, bottom = rect.split(Axis.Y, (1, 1))
    assert (top.y, top.height) == (2, 3)
    assert (bottom.y, bottom.height) == (5, 3)
    assert top.x == bottom.x == 1
    assert top.width == bottom.width == 10


def test_split_matches_the_1x_kernel() -> None:
    from motui.kernel.frame import Split

    core = Split("vertical", (2, 1)).rects(Rect(x=0, y=0, width=10, height=5))
    kernel = Rect(x=0, y=0, width=10, height=5).split(Axis.X, (2, 1))
    assert [(r.x, r.y, r.width, r.height) for r in kernel] == [
        (r.x, r.y, r.width, r.height) for r in core
    ]

    core = Split("horizontal", (1, 2)).rects(Rect(x=3, y=4, width=7, height=11))
    kernel = Rect(x=3, y=4, width=7, height=11).split(Axis.Y, (1, 2))
    assert [(r.x, r.y, r.width, r.height) for r in kernel] == [
        (r.x, r.y, r.width, r.height) for r in core
    ]


def test_split_last_child_takes_the_remainder() -> None:
    parts = Rect(x=0, y=0, width=10, height=1).split(Axis.X, (1, 1, 1))
    assert [part.width for part in parts] == [3, 3, 4]
    assert [part.x for part in parts] == [0, 3, 6]


def test_split_min_size_lifts_every_share() -> None:
    parts = Rect(x=0, y=0, width=3, height=1).split(Axis.X, (9, 1), min_size=1)
    assert [part.width for part in parts] == [2, 1]
    assert sum(part.width for part in parts) == 3


def test_split_overrun_is_clipped_at_the_span() -> None:
    parts = Rect(x=0, y=0, width=4, height=1).split(Axis.X, (1, 1, 1), min_size=2)
    assert [part.width for part in parts] == [2, 2, 0]
    assert sum(part.width for part in parts) == 4


def test_split_validation() -> None:
    rect = Rect(width=10, height=10)
    with pytest.raises(ValueError):
        rect.split(Axis.X, ())
    with pytest.raises(ValueError):
        rect.split(Axis.X, (0, 0))
    with pytest.raises(ValueError):
        rect.split(Axis.X, (-1, 2))
    with pytest.raises(ValueError):
        rect.split(Axis.X, (1, 1), min_size=-1)


def test_split_invariants_random() -> None:
    rng = random.Random(424242)
    for _ in range(300):
        rect = Rect(
            x=rng.randint(-10, 10),
            y=rng.randint(-10, 10),
            width=rng.randint(0, 40),
            height=rng.randint(0, 40),
        )
        axis = rng.choice((Axis.X, Axis.Y))
        weights = tuple(rng.randint(1, 5) for _ in range(rng.randint(1, 4)))
        min_size = rng.randint(0, 3)
        parts = rect.split(axis, weights, min_size)
        span = rect.width if axis is Axis.X else rect.height

        assert len(parts) == len(weights)
        consumed = 0
        for part in parts:
            if axis is Axis.X:
                assert (part.y, part.height) == (rect.y, rect.height)
                assert part.x == rect.x + consumed
                size = part.width
            else:
                assert (part.x, part.width) == (rect.x, rect.width)
                assert part.y == rect.y + consumed
                size = part.height
            # A share is clipped only by what the span has left, so every
            # child is at least the floor its remaining span can host.
            assert size >= min(min_size, span - consumed)
            consumed += size
        assert consumed <= span
        if min_size == 0:
            assert consumed == span  # floor shares plus the remainder partition it
