"""The 2.0 render contract end to end: a narrow screen never wraps a row.

Two guards make the contract hold: a :class:`Section` clips whatever a
component answers to the constraints it was rendered under, and the
:class:`~motui.terminal.paint.Painter` hard-clips every row to the screen
width before writing bytes.  The regression this file pins is the 20-column
screen fed a 40-column row: without either guard the terminal autowraps the
write onto the next line and every row below it is displaced.
"""

from __future__ import annotations

from motui.kernel.cell import Line, Surface
from motui.kernel.document import Document
from motui.kernel.layout import Constraints
from motui.testing import Emulator, headless_tui
from tests.testing import rows


class _Oversized:
    """A component that answers one row twice as wide as the screen."""

    def __init__(self, char: str = "A") -> None:
        self.char = char

    def render(self, c: Constraints) -> Surface:
        # Deliberately ignores ``c``: the guards, not the component,
        # enforce the contract.
        return Surface(width=c.width, rows=(Line.from_text(self.char * 40),))


def test_a_section_clips_an_oversized_component_to_the_constraints():
    document = Document()
    section = document.add(_Oversized())
    rendered = section.rows(Constraints(width=20))
    assert [row.text for row in rendered] == ["A" * 20]
    assert all(row.width <= 20 for row in rendered)
    # The same component under a wide constraint keeps its whole row.
    assert section.rows(Constraints(width=40))[0].width == 40


def test_a_twenty_column_screen_never_wraps_an_oversized_row():
    tui = headless_tui(width=20, height=6)
    tui.add(_Oversized("A"))
    tui.add(_Oversized("B"))
    tui.paint()

    assert all(row.width <= 20 for row in tui.rows)
    assert rows(tui)[:2] == ["A" * 20, "B" * 20]

    emulator = Emulator(20, 6)
    emulator.feed(tui.screen.output)
    assert "".join(cell.char for cell in emulator.grid[0]) == "A" * 20
    assert "".join(cell.char for cell in emulator.grid[1]) == "B" * 20
    assert all(
        "".join(cell.char for cell in emulator.grid[row]).strip() == ""
        for row in range(2, 6)
    )
