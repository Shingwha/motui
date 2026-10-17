"""Tests for motui.kernel.block: Component, Block, Document.

A ``Block`` has a stable id, a component and an OPEN/SEALED lifecycle;
``Document`` is ordered and id-addressable with ``pin`` validation.
"""

import pytest

from motui.kernel.block import Block, BlockState, Document
from motui.kernel.lines import Line


class FakeComponent:
    """Minimal Component: renders its text as one row."""

    def __init__(self, text: str = "row") -> None:
        self.text = text
        self.calls: list[int] = []

    def render(self, width: int) -> list[Line]:
        self.calls.append(width)
        return [Line.from_text(self.text)]


def test_block_render_forwards_to_its_component():
    component = FakeComponent("hello")
    block = Block("b1", component)
    assert block.render(42) == [Line.from_text("hello")] and component.calls == [42]
    assert Block("b1", FakeComponent("second")).render(10) == [
        Line.from_text("second")
    ]


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
    # The block-side pin validation, both edges: an unknown pin name is
    # refused at construction and the property is read-only afterwards.
    with pytest.raises(ValueError):
        Block("x", FakeComponent(), pin="middle")
    with pytest.raises(AttributeError):
        Block("x", FakeComponent()).pin = "bottom"  # type: ignore[misc]
