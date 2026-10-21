"""The document model: Block forwarding and rows, Document ids, lookup,
removal and pin validation."""

from __future__ import annotations

import pytest

from motui.kernel.block import Block, Document
from motui.kernel.lines import Line, Text
from tests.testing import Rows


def test_block_render_forwards_to_its_component():
    component = Rows("hello")
    block = Block("b1", component)
    assert block.render(42) == [Line.from_text("hello")]
    assert Block("b1", Rows("second")).render(10) == [Line.from_text("second")]


def test_block_rows_follow_the_component_and_the_width():
    block = Block("b", Text("hello world"))
    assert [row.text for row in block.rows(20)] == ["hello world"]
    assert [row.text for row in block.rows(5)] == ["hello", "world"]
    block.component.text = "changed"
    assert [row.text for row in block.rows(20)] == ["changed"]


def test_block_rows_return_a_fresh_list_the_caller_owns():
    block = Block("b", Rows("a", "b"))
    rows = block.rows(10)
    rows.append(Line.from_text("extra"))
    assert [row.text for row in block.rows(10)] == ["a", "b"]


def test_document_auto_ids_skip_explicit_ones():
    doc = Document()
    doc.add(Rows(), id="b0")
    first = doc.add(Rows("a"))
    second = doc.add(Rows("b"))
    assert first.id == "b1"
    assert second.id == "b2"
    assert len({block.id for block in doc.blocks()}) == 3


def test_document_rejects_duplicate_ids():
    doc = Document()
    doc.add(Rows(), id="dup")
    with pytest.raises(ValueError):
        doc.add(Rows(), id="dup")


def test_document_get_and_remove():
    doc = Document()
    block = doc.add(Rows(), id="keep")
    other = doc.add(Rows(), id="drop")
    assert doc.get("keep") is block
    assert doc.remove("drop") is other
    assert doc.blocks() == (block,) and len(doc) == 1
    with pytest.raises(KeyError):
        doc.get("drop")
    with pytest.raises(KeyError):
        doc.remove("ghost")


def test_document_blocks_is_a_snapshot():
    doc = Document()
    doc.add(Rows())
    taken = doc.blocks()
    doc.add(Rows())
    assert taken == (doc.blocks()[0],)


def test_pin_is_validated_and_exposed():
    doc = Document()
    assert doc.add(Rows(), pin="top").pin == "top"
    assert doc.add(Rows()).pin is None
    assert doc.add(Rows(), pin="bottom").pin == "bottom"
    with pytest.raises(ValueError):
        doc.add(Rows(), pin="sideways")
    with pytest.raises(ValueError):
        Block("x", Rows(), pin="middle")
    with pytest.raises(AttributeError):
        Block("x", Rows()).pin = "bottom"  # type: ignore[misc]
