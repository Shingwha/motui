"""Tests for mocode_tui.widgets.markdown (the rule-registry engine).

The two ordered registries classify and render the documented constructs as
dep-free singletons; every prefix renders and no row exceeds the width.
"""

from _doubles import texts

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import (
    CODE,
    INLINE_CODE,
    LINK,
    LIST_MARKER,
    MUTED,
    NONE,
    WARNING,
    Style,
)
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.widgets.markdown import (
    INLINE_RULES,
    Markdown,
    RenderContext,
    ThematicBreakRule,
    default_block_rules,
)


def test_headings_strip_markers_and_share_one_gold():
    styles = [
        Markdown(f"{'#' * level} H").render(80)[0].segments[0].style for level in range(1, 7)
    ]
    assert styles[0] == DEFAULT_THEME.headings[0].merge(Style(underline=True))  # h1 underlines
    assert all(style == DEFAULT_THEME.headings[1] for style in styles[1:])  # h2-h6: one gold
    assert texts(Markdown("## Title"), 80) == ["Title"]
    assert texts(Markdown("### Deep"), 80) == ["### Deep"]  # h3+ keeps its hashes


def test_paragraphs_join_soft_breaks_and_the_block_gap_spaces_them():
    assert texts(Markdown("line one\nline two"), 80) == ["line one line two"]
    assert texts(Markdown("the quick brown fox"), 9) == ["the quick", "brown fox"]
    # Exactly one blank row between adjacent blocks; the source's own blank
    # rows are dropped, so they never add a second gap.
    assert texts(Markdown("one\n\n\n\ntwo"), 80) == ["one", "", "two"]
    assert texts(Markdown("a\n\nb\n\nc"), 80) == ["a", "", "b", "", "c"]
    assert texts(Markdown("1. a\n\n2. b"), 80) == ["1. a", "", "2. b"]  # loose list
    # gap=0 restores direct stacking; a negative value degrades to 0.
    assert texts(Markdown("one\n\ntwo", gap=0), 80) == ["one", "two"]
    assert texts(Markdown("one\n\ntwo", gap=-5), 80) == ["one", "two"]
    # No leading gap before the first block, no trailing gap after the last.
    assert texts(Markdown("solo"), 80) == ["solo"]
    assert texts(Markdown(""), 80) == []


def test_lists_keep_the_marker_verbatim_and_nest_by_indent():
    assert texts(Markdown("- one\n* two\n1. first\n2. second"), 80) == [
        "- one",
        "* two",
        "1. first",
        "2. second",
    ]
    assert Markdown("- one").render(80)[0].segments[0] == Segment("- ", LIST_MARKER)
    # Nesting follows the source indent, two spaces per level, deeper capped.
    assert texts(Markdown("- top\n  - nested\n    - deep"), 80) == [
        "- top",
        "  - nested",
        "  - deep",
    ]


def test_quotes_render_behind_a_muted_bar_and_stack_one_per_level():
    rows = Markdown("> first\n> second").render(80)
    assert texts(Markdown("> first\n> second"), 80) == ["\u2502 first second"]
    assert rows[0].segments[0] == Segment("\u2502 ", MUTED)
    assert rows[0].segments[1].style == Style(italic=True)  # the body is italic
    # Nested quotes stack a bar per level; a >-blank ends a paragraph and the
    # body renders tight (no blank rows inside).
    assert texts(Markdown("> a\n>\n> > b\n>\n> - c\n> - d"), 80) == [
        "\u2502 a",
        "\u2502 \u2502 b",
        "\u2502 - c",
        "\u2502 - d",
    ]


def test_list_items_render_their_continuation_blocks():
    rows = Markdown("1. top\n   > quoted\n   ```js\n   x()\n   ```\n2. next").render(80)
    assert [row.text for row in rows] == [
        "1. top",
        "   \u2502 quoted",
        "   ```js",
        "   x()",
        "   ```",
        "2. next",
    ]  # the item's own blocks indent under the marker, tight


def test_fenced_code_parses_the_tag_injects_the_engine_and_runs_to_end():
    closed = Markdown("```python\nx = 1\n```").render(80)
    assert [row.text for row in closed] == ["```python", "x = 1", "```"]
    assert closed[0].segments == (Segment("```python", MUTED),)
    assert closed[1].segments == (
        Segment("x = ", CODE),  # plain code text keeps the theme's code style
        Segment("1", WARNING),  # a number token
    )
    # The info string's first word is the tag; the rest is ignored.
    tagged = Markdown("```python title=example.py\nn = 1\n```").render(80)
    assert tagged[1].segments == (Segment("n = ", CODE), Segment("1", WARNING))
    # Streaming-safe: an unclosed fence runs to the end of the buffer.
    unclosed = Markdown("```\nunclosed").render(80)
    assert [row.text for row in unclosed] == ["```", "unclosed"]
    assert unclosed[1].segments == (Segment("unclosed", CODE),)  # no tag: monochrome


def test_an_injected_highlighter_reaches_the_fence_rule():
    class Stub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def highlight(self, code: str, lang: str) -> list[Line]:
            self.calls.append((code, lang))
            return [Line.from_text(f"{lang}:{code}", Style(bold=True))]

    stub = Stub()
    md = Markdown("```python\nbody line\n```", highlighter=stub)
    assert [row.text for row in md.render(80)] == ["```python", "python:body line", "```"]
    assert stub.calls == [("body line", "python")]
    # An untagged fence still calls the engine (it owns the fallback).
    assert [row.text for row in Markdown("```\nbody\n```", highlighter=stub).render(80)] == [
        "```",
        ":body",
        "```",
    ]
    # An injected engine keeps its colors even under a custom theme.
    themed = Markdown(
        "```python\nn = 1\n```", theme=Theme(code=Style(fg="#666666")), highlighter=stub
    )
    assert [row.text for row in themed.render(80)] == ["```python", "python:n = 1", "```"]


def test_tables_render_the_grid_and_need_a_delimiter_row():
    rows = Markdown("| Name | Score |\n|---|---|\n| alice | 10 |").render(20)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 Name  \u2502 Score \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 alice \u2502 10    \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]
    assert rows[1].segments[1] == Segment(" Name  ", NONE)  # plain header by default
    # A half-typed table is still a paragraph (both halves degrade).
    assert texts(Markdown("| a | b |"), 40) == ["| a | b |"]
    assert texts(Markdown("|---|---|"), 40) == ["|---|---|"]


def test_table_cells_split_on_unescaped_pipes_and_render_inline_markup():
    rows = Markdown(
        "| **Bold** \u52a0\u7c97 | `code` | [t](u) |\n|---|---|---|\n| x | y | z |"
    ).render(60)
    texts_ = [row.text for row in rows]
    assert texts_[1] == "\u2502 Bold \u52a0\u7c97 \u2502 code \u2502 t \u2502"
    styles = {seg.text: seg.style for seg in rows[1].segments}
    assert styles["Bold"] == Style(bold=True)  # merged onto the (plain) header base
    assert styles["code"] == INLINE_CODE  # a colored run stays absolute
    assert styles["t"] == LINK  # the link label: color + underline, no url tail
    # Data rows: the first column carries the theme's first_column base.
    assert rows[3].segments[1] == Segment(" x         ", DEFAULT_THEME.first_column)
    assert rows[3].segments[3] == Segment(" y    ", NONE)
    # A cell's "\|" is a literal pipe and never splits the row (no mid-grid
    # rule with a single data row).
    escaped = Markdown(
        "| \u8868\u8fbe\u5f0f Expression | \u8bf4\u660e Note |\n| :--- | :--- |\n"
        "| `a \\| b` | \u7ba1\u9053\u7b26\u8f6c\u4e49 escaped pipe |"
    ).render(60)
    assert len(escaped) == 5
    assert escaped[3].text == (
        "\u2502 a | b             \u2502 \u7ba1\u9053\u7b26\u8f6c\u4e49 escaped pipe \u2502"
    )
    assert [seg for seg in escaped[3].segments if seg.style == INLINE_CODE] == [
        Segment("a | b", INLINE_CODE)
    ]
    tail = Markdown("| x | y |\n|---|---|\n| a | b \\| |").render(40)
    assert tail[3].text == "\u2502 a \u2502 b | \u2502"


def test_thematic_breaks_render_a_divider_capped_by_divider_max_width():
    assert texts(Markdown("---"), 10) == ["\u2500" * 10]
    assert texts(Markdown("--"), 10) == ["--"]  # not a break
    # The default cap is 80 columns; None spans the whole width.
    assert texts(Markdown("---"), 120) == ["\u2500" * 80]
    assert texts(Markdown("---", divider_max_width=None), 120) == ["\u2500" * 120]
    assert texts(Markdown("---", divider_max_width=5), 120) == ["\u2500" * 5]
    # The cap survives a custom theme (the rule reads it off the context).
    assert texts(Markdown("---", theme=DEFAULT_THEME), 120) == ["\u2500" * 80]
    ctx = RenderContext(theme=DEFAULT_THEME, divider_max_width=10)
    assert [row.text for row in ThematicBreakRule().render(["---"], 40, ctx)] == [
        "\u2500" * 10
    ]


def test_inline_code_bold_italic_link_and_literals():
    row = Markdown("a `code` **bold** *em* [t](u)").render(80)[0]
    assert row.text == "a code bold em t"  # a link shows its label only
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["code"] == INLINE_CODE
    assert styles["bold"] == Style(bold=True)
    assert styles["em"] == Style(italic=True)
    assert styles["t"] == LINK
    # Unclosed markers stay literal.
    assert Markdown("a*b and 2*3 and `oops").render(80)[0].text == "a*b and 2*3 and `oops"


def test_streaming_every_prefix_is_safe_and_fits():
    source = "# T\n\npara `c` **b** *i*\n\n- item\n  - sub\n\n> q\n\n```\nx\n```\n"
    for size in range(len(source) + 1):
        for row in Markdown(source[:size]).render(24):
            assert row.width <= 24  # no row ever exceeds the width


def test_custom_rules_join_the_registries_and_read_the_context():
    class Strike:
        name = "strike"

        def match(self, text, pos, ctx):
            if not text.startswith("~~", pos):
                return None
            end = text.find("~~", pos + 2)
            if end < 0:
                return None
            return end + 2, [Segment(text[pos + 2 : end], Style(dim=True))]

    row = Markdown("a ~~b~~ c", inline_rules=[Strike(), *INLINE_RULES]).render(80)[0]
    assert row.text == "a b c"
    assert {seg.text: seg.style for seg in row.segments}["b"] == Style(dim=True)
    # A rule may also read its styles off the context it is handed.
    class Accent:
        name = "accent"

        def match(self, text, pos, ctx):
            if text[pos] != "@":
                return None
            end = text.find("@", pos + 1)
            if end < 0:
                return None
            return end + 1, [Segment(text[pos + 1 : end], ctx.theme.headings[0])]

    accent = Markdown("a @b@ c", inline_rules=[Accent(), *INLINE_RULES]).render(80)[0]
    assert {seg.text: seg.style for seg in accent.segments}["b"] == DEFAULT_THEME.headings[0]
    # A custom block rule interrupts a paragraph like a built-in one, and it
    # reaches a quote body too (both follow the live registry in the ctx).
    class Shout:
        name = "shout"

        def match(self, lines, i):
            return 1 if lines[i].startswith("!") else None

        def render(self, lines, width, ctx):
            return [Line.from_text(lines[0][1:].strip().upper()).fit(width)]

    registry = [Shout(), *default_block_rules()]
    md = Markdown("para one\n!shout\npara two", block_rules=registry)
    assert texts(md, 80) == ["para one", "", "SHOUT", "", "para two"]
    quoted = Markdown("> one\n> !shout\n> two", block_rules=registry)
    assert texts(quoted, 80) == ["\u2502 one", "\u2502 SHOUT", "\u2502 two"]
