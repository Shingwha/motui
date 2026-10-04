"""Tests for mocode_tui.block."""

import pytest

from mocode_tui.block import Block, BlockState, Component, Document
from mocode_tui.lines import Line
from mocode_tui.style import ACCENT, RESET


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


# --- Component protocol -------------------------------------------------------


def test_component_protocol_is_runtime_checkable():
    assert isinstance(FakeComponent(), Component)
    assert not isinstance(NotAComponent(), Component)
    assert not isinstance(object(), Component)


def test_component_protocol_signature_by_convention():
    # A structural match is enough; the protocol documents the signature.
    class Duck:
        def render(self, width: int) -> list[Line]:
            return [Line.from_text("duck")]

    duck = Duck()
    assert isinstance(duck, Component)
    assert duck.render(10) == [Line.from_text("duck")]


# --- BlockState -----------------------------------------------------------------


def test_block_state_has_exactly_open_and_sealed():
    assert [state.name for state in BlockState] == ["OPEN", "SEALED"]
    assert BlockState.OPEN.value == "open"
    assert BlockState.SEALED.value == "sealed"
    assert not any("COMMITT" in state.name for state in BlockState)


# --- Block -----------------------------------------------------------------------


def test_block_initial_state_and_views():
    component = FakeComponent("x")
    block = Block("b1", component)
    assert block.id == "b1"
    assert block.component is component
    assert block.state is BlockState.OPEN
    assert block.is_open is True
    assert block.pinned is False


def test_block_pinned_is_read_only():
    block = Block("b1", FakeComponent(), pinned=True)
    assert block.pinned is True
    with pytest.raises(AttributeError):
        block.pinned = False  # type: ignore[misc]


def test_block_render_forwards_to_component():
    component = FakeComponent("hello")
    block = Block("b1", component)
    rows = block.render(42)
    assert rows == [Line.from_text("hello")]
    assert component.calls == [42]


def test_block_set_component_works_in_any_state():
    block = Block("b1", FakeComponent("first"))
    block.set_component(FakeComponent("second"))
    assert block.render(10) == [Line.from_text("second")]
    block.seal()
    block.set_component(FakeComponent("third"))  # no state restriction
    assert block.render(10) == [Line.from_text("third")]


def test_block_seal_is_one_shot():
    block = Block("b1", FakeComponent())
    block.seal()
    assert block.state is BlockState.SEALED
    assert block.is_open is False
    with pytest.raises(ValueError):
        block.seal()


def test_block_repr_is_informative():
    block = Block("b1", FakeComponent(), pinned=True)
    assert "b1" in repr(block) and "open" in repr(block) and "True" in repr(block)


# --- Document ----------------------------------------------------------------------


def test_document_starts_empty():
    doc = Document()
    assert len(doc) == 0
    assert doc.blocks() == ()


def test_document_auto_ids_are_unique_and_sequential():
    doc = Document()
    first = doc.add(FakeComponent("a"))
    second = doc.add(FakeComponent("b"))
    assert first.id == "b0"
    assert second.id == "b1"
    assert len(doc) == 2
    assert doc.blocks() == (first, second)


def test_document_auto_ids_avoid_explicit_collisions():
    doc = Document()
    doc.add(FakeComponent(), id="b0")
    auto = doc.add(FakeComponent())
    assert auto.id not in {"b0"}
    assert len({b.id for b in doc.blocks()}) == 2


def test_document_duplicate_id_raises():
    doc = Document()
    doc.add(FakeComponent(), id="dup")
    with pytest.raises(ValueError):
        doc.add(FakeComponent(), id="dup")


def test_document_get_and_remove():
    doc = Document()
    block = doc.add(FakeComponent(), id="keep")
    other = doc.add(FakeComponent(), id="drop")
    assert doc.get("keep") is block
    removed = doc.remove("drop")
    assert removed is other
    assert len(doc) == 1
    assert doc.blocks() == (block,)
    with pytest.raises(KeyError):
        doc.get("drop")


def test_document_get_missing_id_message():
    doc = Document()
    with pytest.raises(KeyError, match="nope"):
        doc.get("nope")


def test_document_remove_missing_id_raises():
    doc = Document()
    with pytest.raises(KeyError):
        doc.remove("ghost")


def test_document_pinned_passthrough():
    doc = Document()
    block = doc.add(FakeComponent(), pinned=True)
    assert block.pinned is True
    assert doc.add(FakeComponent()).pinned is False


def test_document_blocks_is_a_snapshot():
    doc = Document()
    first = doc.add(FakeComponent())
    snapshot = doc.blocks()
    doc.add(FakeComponent())
    doc.remove(first.id)
    assert snapshot == (first,)  # taken before mutation, unchanged


def test_document_add_returns_the_block():
    doc = Document()
    block = doc.add(FakeComponent(), id="b9")
    assert isinstance(block, Block)
    assert doc.get("b9") is block


def test_document_render_through_blocks():
    doc = Document()
    doc.add(FakeComponent("one"), id="a")
    doc.add(FakeComponent("two"), id="b")
    rows = [row for block in doc.blocks() for row in block.render(30)]
    assert rows == [Line.from_text("one"), Line.from_text("two")]


def test_document_components_can_use_styles():
    class StyledComponent:
        def render(self, width: int) -> list[Line]:
            return [Line.from_text("styled", ACCENT)]

    doc = Document()
    doc.add(StyledComponent(), id="s")
    (row,) = doc.get("s").render(10)
    assert row.styled() == ACCENT.prefix() + "styled" + RESET
