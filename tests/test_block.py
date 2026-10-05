"""Tests for mocode_tui.core.block.

Contracts (DESIGN.md + the module docstring): ``Component`` is the frozen
``render(width) -> list[Line]`` protocol (duck-typed, runtime checkable); a
``Block`` has a stable id, a component, and an OPEN/SEALED lifecycle (no
COMMITTED state); ``Document`` is ordered and id-addressable -- auto ids
``b0``, ``b1``... clear of explicit ones, duplicates raise ``ValueError``,
missing ids raise ``KeyError``; ``pin`` is ``"top"``/``"bottom"``/``None`` and
anything else raises.
"""

import pytest

from mocode_tui.core.block import Block, BlockState, Component, Document
from mocode_tui.core.lines import Line


class FakeComponent:
    """Minimal Component: renders its text as one row."""

    def __init__(self, text: str = "row") -> None:
        self.text = text
        self.calls: list[int] = []

    def render(self, width: int) -> list[Line]:
        self.calls.append(width)
        return [Line.from_text(self.text)]


class NotAComponent:
    pass


def test_component_protocol_is_duck_typed():
    assert isinstance(FakeComponent(), Component)
    assert not isinstance(NotAComponent(), Component)


def test_block_state_is_open_or_sealed_only():
    assert [state.name for state in BlockState] == ["OPEN", "SEALED"]
    assert (BlockState.OPEN.value, BlockState.SEALED.value) == ("open", "sealed")


def test_block_initial_views_and_pin():
    block = Block("b1", FakeComponent("x"))
    assert (block.id, block.pin) == ("b1", None)
    assert block.state is BlockState.OPEN and block.is_open is True
    assert Block("t", FakeComponent(), pin="top").pin == "top"
    assert Block("b", FakeComponent(), pin="bottom").pin == "bottom"
    with pytest.raises(AttributeError):
        block.pin = "bottom"  # type: ignore[misc]
    with pytest.raises(ValueError):
        Block("x", FakeComponent(), pin="middle")


def test_block_render_forwards_and_component_swaps_in_any_state():
    component = FakeComponent("hello")
    block = Block("b1", component)
    assert block.render(42) == [Line.from_text("hello")] and component.calls == [42]
    block.set_component(FakeComponent("second"))
    assert block.render(10) == [Line.from_text("second")]
    block.seal()
    block.set_component(FakeComponent("third"))  # no state restriction
    assert block.render(10) == [Line.from_text("third")]


def test_seal_is_one_shot():
    block = Block("b1", FakeComponent())
    block.seal()
    assert block.state is BlockState.SEALED and block.is_open is False
    with pytest.raises(ValueError):
        block.seal()


def test_document_auto_ids_clear_of_explicit_ones():
    doc = Document()
    doc.add(FakeComponent(), id="b0")
    first, second = doc.add(FakeComponent("a")), doc.add(FakeComponent("b"))
    assert first.id not in {"b0"}  # skips the taken id
    assert second.id != first.id
    assert len({b.id for b in doc.blocks()}) == 3


def test_document_add_duplicate_id_raises():
    doc = Document()
    doc.add(FakeComponent(), id="dup")
    with pytest.raises(ValueError):
        doc.add(FakeComponent(), id="dup")


def test_document_get_and_remove():
    doc = Document()
    block = doc.add(FakeComponent(), id="keep")
    other = doc.add(FakeComponent(), id="drop")
    assert doc.get("keep") is block
    assert doc.remove("drop") is other
    assert doc.blocks() == (block,) and len(doc) == 1
    with pytest.raises(KeyError):
        doc.get("drop")
    with pytest.raises(KeyError):
        doc.remove("ghost")


def test_document_blocks_is_a_snapshot():
    doc = Document()
    doc.add(FakeComponent())
    taken = doc.blocks()
    doc.add(FakeComponent())
    assert taken == tuple(doc.blocks()[:1])  # immune to later mutation


def test_document_pin_passthrough_and_validation():
    doc = Document()
    assert doc.add(FakeComponent(), pin="top").pin == "top"
    assert doc.add(FakeComponent()).pin is None
    assert doc.add(FakeComponent(), pin="bottom").pin == "bottom"
    with pytest.raises(ValueError):
        doc.add(FakeComponent(), pin="sideways")
