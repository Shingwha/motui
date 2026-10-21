"""Styling topics: theme tokens, custom themes, glyphs and row bands."""

from __future__ import annotations

from dataclasses import replace

from motui import DEFAULT_THEME, Button, List, Segment, Style, Text
from motui.kernel import glyphs
from motui.widgets import Column, RowBands, Table

from ..assets import THEMES
from ..stage import topic

_TOKEN_ROWS = [
    ("accent", "accent", "active labels and bars"),
    ("heading", "heading", "Markdown headings"),
    ("link", "link", "links"),
    ("dim", "dim", "summary and hint rows"),
    ("muted", "muted", "dividers and group rows"),
    ("success", "success", "progress and insertions"),
    ("warning", "warning", "warnings"),
    ("error", "error", "errors and deletions"),
    ("selection", "selection", "selected ranges and find matches"),
    ("toast", "toast", "toasts and the find row"),
    ("ground_active", "ground_active", "cursor rows"),
    ("hover", "hover", "pointer rows"),
    ("scrollbar", "scrollbar", "the scrollbar track"),
    ("scrollbar_thumb", "scrollbar_thumb", "the scrollbar thumb"),
]

_GLYPHS = [
    ("CURSOR", glyphs.CURSOR, "List"),
    ("MENU_CURSOR", glyphs.MENU_CURSOR, "Select / Autocomplete"),
    ("RAIL_BAR", glyphs.RAIL_BAR, "NavList"),
    ("EXPANDED", glyphs.EXPANDED, "Tree open"),
    ("COLLAPSED", glyphs.COLLAPSED, "Tree closed"),
    ("RADIO_EMPTY", glyphs.RADIO_EMPTY, "RadioGroup"),
    ("RADIO_FILLED", glyphs.RADIO_FILLED, "RadioGroup"),
    ("MARKED", glyphs.MARKED, "marks"),
    ("UNMARKED", glyphs.UNMARKED, "marks"),
    ("MORE_UP", glyphs.MORE_UP, "List counter"),
    ("MORE_DOWN", glyphs.MORE_DOWN, "List counter"),
    ("TRACK", glyphs.TRACK, "Scrollbar"),
    ("THUMB", glyphs.THUMB, "Scrollbar"),
    ("TASK_OPEN", glyphs.TASK_OPEN, "Markdown tasks"),
    ("TASK_DONE", glyphs.TASK_DONE, "Markdown tasks"),
]

_BANDS = RowBands(
    active=Style(bg="#1b3a5b"),
    hover=Style(bg="#26303c"),
    disabled=Style(dim=True),
)


def _theme_tokens(b) -> None:
    theme = b.theme
    rows = []
    for label, field, where in _TOKEN_ROWS:
        style = getattr(theme, field)
        rows.append([label, [Segment("\u2588\u2588\u2588\u2588\u2588\u2588", style)], where])
    table = Table(["token", "swatch", "where it lands"], rows, theme=b.theme)
    b.preview(table)


def _custom_theme(b) -> None:
    variants = Column(
        [
            Text("default", style=THEMES[0][1].accent),
            Text("amber", style=THEMES[1][1].accent),
            Text("violet", style=THEMES[2][1].accent),
        ]
    )
    b.preview(
        Column(
            [
                Button("default accent", style=THEMES[0][1].accent, theme=b.theme),
                Button("amber accent", style=THEMES[1][1].accent, theme=b.theme),
                Button("violet accent", style=THEMES[2][1].accent, theme=b.theme),
            ]
        ),
        variants,
    )
    b.variants(
        ("replace(DEFAULT_THEME, accent=Style(fg='#e8a020'))",
         Button("amber", style=replace(DEFAULT_THEME, accent=Style(fg="#e8a020")).accent, theme=b.theme)),
        ("the same recipe for violet",
         Button("violet", style=replace(DEFAULT_THEME, accent=Style(fg="#9d7cd8")).accent, theme=b.theme)),
    )


def _glyphs(b) -> None:
    rows = [
        [name, glyph, str(glyphs.seat_width(glyph)), where]
        for name, glyph, where in _GLYPHS
    ]
    b.preview(Table(["constant", "glyph", "seat", "used by"], rows, theme=b.theme))


def _row_bands(b) -> None:
    items = [f"row {index:02d}" for index in range(1, 9)]
    banded = List(items, window=6, disabled_items=[4], bands=_BANDS, theme=b.theme)
    banded.index = 1
    banded.render(60)  # establish the row geometry hover_at resolves against
    banded.hover_at(2, 0)  # paint the pointer's row without a pointer
    plain = List(items, window=4, theme=b.theme)
    b.preview(
        Column(
            [
                Text("active: ground_active \u00b7 hovered: hover \u00b7 disabled: dim", style=b.theme.dim),
                banded,
            ]
        )
    )
    b.variants(("no bands (theme seed)", plain), ("active only", List(items, window=4, bands=RowBands(active=Style(bg="#1b3a5b")), theme=b.theme)))
    b.focus(banded)
    echo = b.echo("picked")

    def note(report) -> None:
        if report.source is banded:
            echo.set(report.value)

    b.note(note)


TOPICS = (
    topic(
        key="theme-tokens",
        title="Theme tokens",
        summary="One frozen Theme: named styles for labels, links, bands and chrome.",
        group="Theme",
        section="styling",
        try_line="press c-t to cycle default, amber and violet; every row follows",
        api_line="Theme(accent, heading, link, dim, muted, success, warning, error, selection)",
        components=("Table",),
        build=_theme_tokens,
    ),
    topic(
        key="custom-theme",
        title="Custom theme",
        summary="Build a variant with dataclasses.replace; nothing global is mutated.",
        group="Theme",
        section="styling",
        try_line="c-t switches the whole shell; the variants show one replaced field",
        api_line="replace(DEFAULT_THEME, accent=Style(fg='#e8a020'), selection=Style(bg=...))",
        components=("Button", "Text", "Column"),
        build=_custom_theme,
    ),
    topic(
        key="glyphs",
        title="Glyphs",
        summary="The structural mark vocabulary: one constant per component seat.",
        group="Glyphs & bands",
        section="styling",
        try_line="none -- glyphs are content; components take them as keyword parameters",
        api_line="glyphs: CURSOR, MENU_CURSOR, RAIL_BAR, MARKED, seat, seat_width, pair_seat",
        components=("Table",),
        build=_glyphs,
    ),
    topic(
        key="row-bands",
        title="Row bands",
        summary="One RowBands value per row widget: ground, active, hover, dim, text, disabled.",
        group="Glyphs & bands",
        section="styling",
        try_line="up/down move the active row; the hovered and disabled rows keep their bands",
        api_line="RowBands(ground, active, hover, dim, text, disabled) · bands= on row views",
        components=("RowBands", "List"),
        build=_row_bands,
    ),
)
