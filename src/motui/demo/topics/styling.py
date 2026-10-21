"""Styling topics: theme tokens, custom themes, glyphs and row bands."""

from __future__ import annotations

from dataclasses import replace

from motui import DEFAULT_THEME, Button, List, Segment, Style, Text
from motui.core.glyphs import GLYPHS, seat_width
from motui.widgets import Column, Table

from ..assets import THEMES
from ..stage import topic

_TOKEN_ROWS = [
    ("content.accent", lambda t: t.content.accent, "active labels and bars"),
    ("content.headings[0]", lambda t: t.content.headings[0], "Markdown headings"),
    ("content.link", lambda t: t.content.link, "links"),
    ("text.faint", lambda t: t.text.faint, "summary and hint rows"),
    ("text.muted", lambda t: t.text.muted, "dividers and group rows"),
    ("status.success", lambda t: t.status.success, "progress and insertions"),
    ("status.warning", lambda t: t.status.warning, "warnings"),
    ("status.danger", lambda t: t.status.danger, "errors and deletions"),
    ("text.selection", lambda t: t.text.selection, "selected ranges and find matches"),
    ("overlays.toast", lambda t: t.overlays.toast, "toasts and the find row"),
    ("rows.active", lambda t: t.rows.active, "cursor rows"),
    ("rows.hover", lambda t: t.rows.hover, "pointer rows"),
    ("chrome.scrollbar", lambda t: t.chrome.scrollbar, "the scrollbar track"),
    ("chrome.scrollbar_thumb", lambda t: t.chrome.scrollbar_thumb, "the scrollbar thumb"),
]

_GLYPHS = [
    ("prompt", GLYPHS.prompt, "Input / Find"),
    ("cursor", GLYPHS.cursor, "List / Select / Autocomplete"),
    ("rail", GLYPHS.rail, "NavList"),
    ("fold_open", GLYPHS.fold_open, "Tree / Collapsible open"),
    ("fold_closed", GLYPHS.fold_closed, "Tree / Collapsible closed"),
    ("radio_off", GLYPHS.radio_off, "RadioGroup"),
    ("radio_on", GLYPHS.radio_on, "RadioGroup"),
    ("check_off", GLYPHS.check_off, "Checkbox / CheckboxGroup / Markdown tasks"),
    ("check_on", GLYPHS.check_on, "Checkbox / CheckboxGroup / Markdown tasks"),
    ("more_up", GLYPHS.more_up, "List counter"),
    ("more_down", GLYPHS.more_down, "List counter"),
    ("bar_full", GLYPHS.bar_full, "Progress / Scrollbar"),
    ("bar_empty", GLYPHS.bar_empty, "Progress / Scrollbar"),
    ("slider_track", GLYPHS.slider_track, "Slider"),
    ("slider_thumb", GLYPHS.slider_thumb, "Slider"),
    ("horizontal_rule", GLYPHS.horizontal_rule, "Divider"),
    ("vertical_rule", GLYPHS.vertical_rule, "Tabs / MenuBar"),
    ("quote", GLYPHS.quote, "Markdown quote"),
    ("separator", GLYPHS.separator, "ShortcutBar"),
    ("bullets", " ".join(GLYPHS.bullets), "Markdown lists"),
    ("notice_info", GLYPHS.notice_info, "Notice"),
    ("notice_success", GLYPHS.notice_success, "Notice"),
    ("notice_warn", GLYPHS.notice_warn, "Notice"),
    ("notice_error", GLYPHS.notice_error, "Notice"),
    ("diff_add", GLYPHS.diff_add, "Diff"),
    ("diff_remove", GLYPHS.diff_remove, "Diff"),
    ("spinner", " ".join(GLYPHS.spinner), "Spinner"),
]

_BAND_OVERRIDES = {
    "active": Style(bg="#1b3a5b"),
    "hover": Style(bg="#26303c"),
    "disabled": Style(dim=True),
}


def _rows_theme(theme, **overrides):
    """The theme with its row tokens re-aimed (the 2.0 way to band a row view)."""
    return replace(theme, rows=replace(theme.rows, **overrides))


def _theme_tokens(b) -> None:
    theme = b.theme
    rows = []
    for label, getter, where in _TOKEN_ROWS:
        style = getter(theme)
        rows.append([label, [Segment("\u2588\u2588\u2588\u2588\u2588\u2588", style)], where])
    table = Table(["token", "swatch", "where it lands"], rows, theme=b.theme)
    b.preview(table)


def _custom_theme(b) -> None:
    variants = Column(
        [
            Text("default", style=THEMES[0][1].content.accent),
            Text("amber", style=THEMES[1][1].content.accent),
            Text("violet", style=THEMES[2][1].content.accent),
        ]
    )
    b.preview(
        Column(
            [
                Button("default accent", style=THEMES[0][1].content.accent, theme=b.theme),
                Button("amber accent", style=THEMES[1][1].content.accent, theme=b.theme),
                Button("violet accent", style=THEMES[2][1].content.accent, theme=b.theme),
            ]
        ),
        variants,
    )
    b.variants(
        ("replace(DEFAULT_THEME, content=replace(..., accent=Style(fg='#e8a020')))",
         Button("amber", style=replace(DEFAULT_THEME, content=replace(DEFAULT_THEME.content, accent=Style(fg="#e8a020"))).content.accent, theme=b.theme)),
        ("the same recipe for violet",
         Button("violet", style=replace(DEFAULT_THEME, content=replace(DEFAULT_THEME.content, accent=Style(fg="#9d7cd8"))).content.accent, theme=b.theme)),
    )


def _glyphs(b) -> None:
    rows = [
        [name, glyph, str(seat_width(glyph)), where]
        for name, glyph, where in _GLYPHS
    ]
    b.preview(Table(["glyphs field", "glyph", "seat", "used by"], rows, theme=b.theme))


def _row_bands(b) -> None:
    items = [f"row {index:02d}" for index in range(1, 9)]
    banded = List(
        items,
        window=6,
        disabled_items=[4],
        theme=_rows_theme(b.theme, **_BAND_OVERRIDES),
    )
    banded.index = 1
    banded.render(60)  # establish the row geometry hover_at resolves against
    banded.hover_at(2, 0)  # paint the pointer's row without a pointer
    plain = List(items, window=4, theme=b.theme)
    b.preview(
        Column(
            [
                Text("active: rows.active \u00b7 hovered: rows.hover \u00b7 disabled: rows.disabled", style=b.theme.text.faint),
                banded,
            ]
        )
    )
    b.variants(
        ("no bands (theme seed)", plain),
        (
            "active only",
            List(
                items,
                window=4,
                theme=_rows_theme(b.theme, active=Style(bg="#1b3a5b")),
            ),
        ),
    )
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
        api_line="Theme(text, surfaces, borders, controls, rows, status, content, chrome, overlays, syntax)",
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
        api_line="replace(DEFAULT_THEME, content=replace(..., accent=Style(fg='#e8a020')))",
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
        api_line="Glyphs(prompt, cursor, rail, fold_*, check_*, bullets, ...) · glyphs= on components",
        components=("Table",),
        build=_glyphs,
    ),
    topic(
        key="row-bands",
        title="Row bands",
        summary="Row bands live on theme.rows: base, active, hover, inactive, selected, marked, disabled.",
        group="Glyphs & bands",
        section="styling",
        try_line="up/down move the active row; the hovered and disabled rows keep their bands",
        api_line="replace(theme, rows=replace(theme.rows, active=...)) · rows.band(...)",
        components=("Theme", "List"),
        build=_row_bands,
    ),
)
