"""PixelCanvas: layer quantization, the erase/fade verbs, geometry, speed."""

from __future__ import annotations

from time import perf_counter

from motui.kernel.layout import Constraints
from motui.kernel.pixel import PixelPalette
from motui.widgets.pixel_canvas import PixelCanvas

PALETTE = PixelPalette(
    slots={
        1: ((255, 255, 255), (140, 140, 160)),  # id: (main, cool)
        2: ((255, 130, 190), (150, 70, 110)),
    },
    bg=(12, 12, 16),
)


def test_the_canvas_quantizes_a_line_layer_over_a_fill_layer_through_the_kernel_palette():
    canvas = PixelCanvas(2, 2, palette=PALETTE)
    canvas.fill_set(0, 0, slot=2)  # upper half of cell (0, 0): art must take it
    canvas.fill_set(0, 6, slot=2)  # lower half of cell (0, 1): subrow 6 = 1*4 + 2
    canvas.set(0, 0, slot=1)  # art dot, cell (0, 0)
    canvas.set(2, 0, slot=1)  # art dot, cell (1, 0)
    surface = canvas.render(Constraints(width=2, max_height=2))
    # The line layer keeps every cell it has ink on; the fill layer shows
    # only where the art is dark, and blanks carry the palette background.
    assert [row.text for row in surface] == ["\u2801\u2801", "\u2584 "]
    top = surface[0].segments
    assert len(top) == 1  # both art cells share one style object: one run
    assert top[0].style.fg == (255, 255, 255) and top[0].style.bg is None
    bottom = surface[1].segments
    assert [(s.text, s.style.fg, s.style.bg) for s in bottom] == [
        ("\u2584", (255, 130, 190), (12, 12, 16)),
        (" ", None, (12, 12, 16)),
    ]


def test_a_marked_sub_cell_is_erased_by_unset_and_fades_to_cool_then_dark_on_decay():
    canvas = PixelCanvas(1, 1, palette=PALETTE)
    for subrow in range(4):
        canvas.set(0, subrow, slot=1)  # the cell's whole left braille column
    assert canvas.render(Constraints(width=1, max_height=1))[0].text == "\u2847"
    canvas.unset(0, 0)
    assert canvas.render(Constraints(width=1, max_height=1))[0].text == "\u2846"
    canvas.decay(63)  # heat 255 -> 192: still fresh, the main colour
    fresh = canvas.render(Constraints(width=1, max_height=1))[0].segments[0]
    assert fresh.style.fg == (255, 255, 255)
    canvas.decay(63)  # heat 192 -> 129: aged past COOL_AT, the cool colour
    aged = canvas.render(Constraints(width=1, max_height=1))[0].segments[0]
    assert aged.style.fg == (140, 140, 160)
    canvas.decay(10)  # heat 129 -> 119: below the lit threshold, gone
    assert canvas.render(Constraints(width=1, max_height=1))[0].text == " "


def test_render_rebuilds_the_buffers_at_a_new_constraint_size_and_keeps_ink_while_it_holds():
    canvas = PixelCanvas(2, 2, palette=PALETTE)
    canvas.set(0, 0, slot=1)
    rebuilt = canvas.render(Constraints(width=4, max_height=1))
    assert canvas.width == 4 and canvas.height == 1
    assert rebuilt.width == 4 and rebuilt.height == 1
    assert rebuilt[0].text == "    "  # a resize drops the ink, by contract
    canvas.set(1, 0, slot=1)
    held = canvas.render(Constraints(width=4))  # natural height: size holds
    assert held.height == 1 and held[0].text == "\u2808   "
    empty = canvas.render(Constraints(width=0))
    assert empty.width == 0 and empty.height == 0


def test_the_full_pixel_pipeline_stays_under_twelve_ms_at_76x24():
    canvas = PixelCanvas(76, 24, palette=PALETTE)
    # The worst case: every cell inked on both layers with mixed slots, a
    # full half-res fill under dense braille lines.
    canvas.fill_rect(0, 0, canvas.fill.width - 1, canvas.fill.height - 1, fill=True, slot=1)
    for row in range(canvas.height):
        canvas.line(0, row * 4, canvas.art.width - 1, row * 4, slot=2)
    canvas.render(Constraints(width=76, max_height=24))  # warm the constants
    samples: list[float] = []
    for _ in range(7):
        started = perf_counter()
        canvas.render(Constraints(width=76, max_height=24))
        samples.append((perf_counter() - started) * 1000.0)
    median = sorted(samples)[len(samples) // 2]
    print(f"pixel canvas 76x24 full pipeline: median {median:.3f} ms {samples}")
    assert median <= 12.0, f"full pixel pipeline median {median:.3f} ms"
