"""The document model: Section forwarding and rows, Document ids, lookup,
removal and pin validation."""

from __future__ import annotations

import pytest

from motui.kernel.cell import Line, Surface
from motui.kernel.document import Document, Fill, Placement, Section, Sizing
from motui.kernel.layout import Constraints
from motui.widgets.text import Text
from tests.testing import Rows


class _SurfaceRows:
    """A component already on the 2.0 render shape: Constraints -> Surface."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.constraints: list[Constraints] = []

    def render(self, c: Constraints) -> Surface:
        self.constraints.append(c)
        rows = [Line.from_text(text) for text in self.texts]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def revision(self) -> object:
        return tuple(self.texts)


def test_block_render_forwards_to_its_component():
    component = Rows("hello")
    block = Section("b1", component)
    assert block.render(42) == [Line.from_text("hello")]
    assert Section("b1", Rows("second")).render(10) == [Line.from_text("second")]


def test_block_rows_follow_the_component_and_the_width():
    block = Section("b", Text("hello world"))
    assert [row.text for row in block.rows(20)] == ["hello world"]
    assert [row.text for row in block.rows(5)] == ["hello", "world"]
    block.component.text = "changed"
    assert [row.text for row in block.rows(20)] == ["changed"]


def test_block_rows_return_a_fresh_list_the_caller_owns():
    block = Section("b", Rows("a", "b"))
    rows = block.rows(10)
    rows.append(Line.from_text("extra"))
    assert [row.text for row in block.rows(10)] == ["a", "b"]


def test_block_rows_view_borrows_the_same_list_on_a_hit():
    block = Section("b", Text("hello world"))
    first = block.rows_view(20)
    second = block.rows_view(20)
    assert first is second  # the cache list itself: borrowed, not copied
    assert [row.text for row in first] == ["hello world"]
    block.component.text = "changed"
    assert [row.text for row in block.rows_view(20)] == ["changed"]


def test_block_row_count_matches_len_rows_in_both_cache_states():
    block = Section("b", Text("hello world"))  # cacheable
    for _ in range(2):  # first pass fills the cache (miss), second reads it (hit)
        assert block.row_count(5) == len(block.rows(5)) == 2
    plain = Section("p", Rows("a", "b", "c"))  # no revision protocol: never cached
    for _ in range(2):
        assert plain.row_count(20) == len(plain.rows(20)) == 3


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


def test_document_blocks_reuses_one_tuple_until_a_mutation():
    doc = Document()
    first = doc.add(Rows("a"))
    snapshot = doc.blocks()
    assert doc.blocks() is snapshot  # unchanged: the very same tuple object
    second = doc.add(Rows("b"))
    fresh = doc.blocks()
    assert fresh is not snapshot
    assert fresh == (first, second)
    assert snapshot == (first,)  # the old snapshot keeps what it held
    doc.remove(first.id)
    after = doc.blocks()
    assert after is not fresh and after == (second,)
    assert fresh == (first, second)  # immune to the later mutation too


def test_document_mutation_increases_monotonically():
    doc = Document()
    assert doc.mutation == 0
    doc.add(Rows("a"))
    after_add = doc.mutation
    assert after_add == 1
    doc.add(Rows("b"))
    doc.remove(doc.get("b0").id)
    assert doc.mutation > after_add  # adds and removes count alike, never reset
    assert doc.mutation == 3


def test_pin_is_validated_and_exposed():
    doc = Document()
    assert doc.add(Rows(), pin="top").pin == "top"
    assert doc.add(Rows()).pin is None
    assert doc.add(Rows(), pin="bottom").pin == "bottom"
    with pytest.raises(ValueError):
        doc.add(Rows(), pin="sideways")
    with pytest.raises(ValueError):
        Section("x", Rows(), pin="middle")
    with pytest.raises(AttributeError):
        Section("x", Rows()).pin = "bottom"  # type: ignore[misc]


# -- the Constraints seam ----------------------------------------------------


def test_a_section_takes_constraints_and_forwards_them_to_a_surface_component():
    component = _SurfaceRows("alpha", "beta", "gamma")
    block = Section("b", component)
    constraints = Constraints(width=7, max_height=2)
    rows = block.rows(constraints)
    assert [row.text for row in rows] == ["alpha", "beta"]
    assert component.constraints[-1] is constraints  # passed through unchanged


def test_the_height_budget_is_part_of_the_section_cache_key():
    component = _SurfaceRows("a", "b", "c")
    block = Section("b", component)
    assert len(block.rows(Constraints(width=5, max_height=1))) == 1
    assert len(block.rows(Constraints(width=5, max_height=2))) == 2
    assert len(block.rows(Constraints(width=5, max_height=1))) == 1
    assert len(component.constraints) == 3  # the third call missed the cache


def test_a_legacy_component_is_wrapped_in_a_clipped_surface():
    block = Section("b", Rows("x" * 40, "short"))
    rows = block.rows(Constraints(width=20))
    assert [row.width for row in rows] == [20, 5]
    assert rows[0].text == "x" * 20


def test_section_render_stays_a_list_convenience_door():
    block = Section("b", Rows("hello"))
    rendered = block.render(Constraints(width=10))
    assert isinstance(rendered, list)
    assert rendered == [Line.from_text("hello")]
    assert block.render(10) == rendered


# -- placement, sizing and fill ---------------------------------------------


def test_placement_replaces_pin_and_keeps_it_readable():
    doc = Document()
    flow = doc.add(Rows("body"))
    top = doc.add(Rows("head"), pin="top")
    bottom = doc.add(Rows("foot"), placement=Placement.BOTTOM)
    assert flow.placement is Placement.FLOW and flow.pin is None
    assert top.placement is Placement.TOP and top.pin == "top"
    assert bottom.placement is Placement.BOTTOM and bottom.pin == "bottom"
    assert top.widget is top.component


def test_pin_and_placement_are_exclusive():
    doc = Document()
    with pytest.raises(ValueError):
        doc.add(Rows(), pin="top", placement=Placement.BOTTOM)
    with pytest.raises(ValueError):
        Section("x", Rows(), pin="top", placement=Placement.TOP)


def test_section_rejects_non_enum_placement_and_sizing():
    with pytest.raises(ValueError):
        Section("x", Rows(), placement="top")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Section("x", Rows(), sizing="fill")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Section("x", Rows(), pin="middle")


def test_a_fill_section_owns_the_rule_and_is_found_by_the_document():
    doc = Document()
    doc.add(Rows("head"))
    fill = doc.add(Rows("game"), sizing=Sizing.FILL)
    assert fill.sizing is Sizing.FILL and fill.placement is Placement.FLOW
    assert fill.widget is fill.component
    assert doc.fill() is fill
    assert doc.fills() == (fill,)
    assert doc.add(Rows("top"), placement=Placement.TOP).placement is Placement.TOP


def test_a_document_holds_at_most_one_fill():
    doc = Document()
    doc.add(Rows(), sizing=Sizing.FILL)
    with pytest.raises(ValueError):
        doc.add(Rows(), sizing=Sizing.FILL)


def test_no_flow_section_may_follow_a_fill():
    doc = Document()
    doc.add(Rows(), sizing=Sizing.FILL)
    with pytest.raises(ValueError):
        doc.add(Rows())
    with pytest.raises(ValueError):
        doc.add(Rows(), sizing=Sizing.NATURAL)
    # Pinned sections live outside the flow and stay legal.
    assert doc.add(Rows("foot"), pin="bottom").pin == "bottom"
    assert doc.add(Rows("head"), pin="top").pin == "top"


def test_a_fill_section_must_be_in_the_flow():
    doc = Document()
    with pytest.raises(ValueError):
        doc.add(Rows(), pin="top", sizing=Sizing.FILL)
    with pytest.raises(ValueError):
        doc.add(Rows(), placement=Placement.BOTTOM, sizing=Sizing.FILL)
    with pytest.raises(ValueError):
        Section("x", Rows(), placement=Placement.TOP, sizing=Sizing.FILL)


def test_fill_is_a_frozen_value():
    component = Rows("body")
    value = Fill(component)
    assert value.widget is component
    with pytest.raises(AttributeError):
        value.widget = Rows()  # type: ignore[misc]
