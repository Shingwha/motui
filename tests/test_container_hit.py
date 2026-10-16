"""Hit translation: the kernel's ``descend`` and the containers' ``child_at``.

``descend`` walks ``Container.child_at`` to the deepest component owning a
cell; the layout and decor containers answer it from the geometry of their
last render, so a container that has not rendered yet declines every cell.
Nothing here re-renders through ``child_at``: the cache is read, never
recomputed.
"""

from mocode_tui.core.block import Container, Hoverable, descend
from mocode_tui.core.lines import Line, Text


class SelfReturning:
    """A malformed container that claims every cell as its own child."""

    def __init__(self) -> None:
        self.calls = 0

    def render(self, width: int) -> list[Line]:
        return [Line()]

    def child_at(self, row: int, col: int):
        self.calls += 1
        return self, row, col


class Flag:
    """The minimum a hoverable declares: one read-write flag."""

    def __init__(self) -> None:
        self.hover = False


# --- the kernel protocols and descend -------------------------------------------


def test_hoverable_is_a_runtime_protocol_over_one_flag():
    assert isinstance(Flag(), Hoverable)
    assert not isinstance(Text("x"), Hoverable)


def test_container_is_a_runtime_protocol_over_child_at():
    assert isinstance(SelfReturning(), Container)
    assert not isinstance(Text("x"), Container)


def test_descend_returns_a_leaf_with_its_coords_unchanged():
    text = Text("x")
    assert descend(text, 0, 0) == (text, 0, 0)
    assert descend(text, 3, 4) == (text, 3, 4)


def test_descend_stops_at_a_malformed_container_that_returns_itself():
    loop = SelfReturning()
    assert descend(loop, 3, 4) == (loop, 3, 4)
    assert loop.calls == 64  # the module's _DESCEND_LIMIT guard
