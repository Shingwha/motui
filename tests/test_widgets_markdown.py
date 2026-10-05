"""Tests for mocode_tui.widgets.markdown (the rule-registry engine).

Contracts (COMPONENTS.md): the two ordered registries classify and render the
documented constructs -- headings on the accent ladder, lists with verbatim
markers, quotes with a muted bar, fenced code with its language tag parsed
and handed to the syntax highlighter (``CODE`` monochrome when untagged),
GFM tables through the ``Table`` component, thematic breaks as dividers,
paragraphs soft-joining lines, and inline code/bold/italic/link.  Streaming
is safe by construction: every prefix renders and no row exceeds the width.
"""

from mocode_tui.widgets.markdown import (
    INLINE_RULES,
    Markdown,
    default_block_rules,
)
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import ACCENT, CODE, MUTED, NONE, WARNING, Style
from mocode_tui.core.theme import DEFAULT_THEME

# The highlighter's token colors, derived from DEFAULT_THEME (the same
# derivation the engine itself performs).
COMMENT = DEFAULT_THEME.muted.merge(Style(italic=True))
KEYWORD = DEFAULT_THEME.accent
NUMBER = DEFAULT_THEME.warning
STRING = DEFAULT_THEME.success


def _texts(rows):
    return [row.text for row in rows]


def test_headings_strip_markers_and_share_the_accent_ladder():
    styles = [
        Markdown(f"{'#' * level} H").render(80)[0].segments[0].style for level in range(1, 7)
    ]
    assert styles[0] == ACCENT  # h1: the accent constant
    assert styles[1] == ACCENT.merge(Style(underline=True))  # h2: accent + underline
    assert styles[2] == MUTED and not styles[2].bold and not styles[2].dim  # h3
    assert styles[3] == MUTED.merge(Style(dim=True))  # h4-h5
    assert styles[5] == MUTED.merge(Style(dim=True, italic=True))  # h6
    assert _texts(Markdown("## Title").render(80)) == ["Title"]


def test_paragraphs_join_soft_breaks_and_wrap():
    assert _texts(Markdown("line one\nline two").render(80)) == ["line one line two"]
    assert _texts(Markdown("the quick brown fox").render(9)) == ["the quick", "brown fox"]
    assert _texts(Markdown("one\n\ntwo").render(80)) == ["one", "two"]  # no extra gaps


def test_lists_keep_the_marker_verbatim_and_nest_by_indent():
    rows = Markdown("- one\n* two\n1. first\n2. second").render(80)
    assert _texts(rows) == ["- one", "* two", "1. first", "2. second"]
    assert rows[0].segments[0] == Segment("- ", MUTED)
    nested = Markdown("- top\n  - nested\n    - deep").render(80)
    assert _texts(nested) == ["- top", "  - nested", "  - deep"]  # deeper indent caps at level 2


def test_quote_prefixes_every_line_with_a_muted_bar():
    rows = Markdown("> first\n> second").render(80)
    assert _texts(rows) == ["\u2502 first", "\u2502 second"]
    assert rows[0].segments[0] == Segment("\u2502 ", MUTED)


def test_fenced_code_parses_the_tag_highlights_and_runs_to_end_when_unclosed():
    # W3 changed the semantics: the info string is no longer dropped, it is
    # the language tag driving the highlighter.  Row text is unchanged; only
    # the code lines' colors now come from the syntax engine.
    closed = Markdown("```python\nx = 1\n```").render(80)
    assert _texts(closed) == ["x = 1"]
    assert closed[0].segments == (
        Segment("x = ", CODE),  # plain code text keeps the theme's code style
        Segment("1", WARNING),  # a number token
    )
    unclosed = Markdown("```\nunclosed").render(80)
    assert _texts(unclosed) == ["unclosed"]  # streaming-safe: body to the end
    assert unclosed[0].segments == (Segment("unclosed", CODE),)  # no tag: monochrome


def test_tables_need_header_and_delimiter_and_render_the_grid():
    rows = Markdown("| Name | Score |\n|---|---|\n| alice | 10 |").render(20)
    assert _texts(rows) == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 Name  \u2502 Score \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 alice \u2502 10    \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]
    assert rows[1].segments[1] == Segment(" Name  ", Style(bold=True))
    # A half-typed table is still a paragraph (both halves degrade).
    assert _texts(Markdown("| a | b |").render(40)) == ["| a | b |"]
    assert _texts(Markdown("|---|---|").render(40)) == ["|---|---|"]


def test_table_alignment_markers():
    rows = Markdown("| l | c | r |\n|:--|:-:|--:|\n| a | bb | c |\n| longer | x | ccc |").render(30)
    texts = [row.text for row in rows]
    assert texts[1] == "\u2502 l      \u2502 c  \u2502   r \u2502"  # header: left/center/right
    assert texts[3] == "\u2502 a      \u2502 bb \u2502   c \u2502"
    # One mid-grid rule now separates every two data rows (W1 grid change).
    assert texts[4] == "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2524"
    assert texts[5] == "\u2502 longer \u2502 x  \u2502 ccc \u2502"


def test_table_cells_render_inline_markup():
    # W1: a cell is no longer plain text -- bold, code and links render as
    # styled runs; attribute-only runs are merged onto the column base
    # (bold header / first column), colored runs stay absolute.
    rows = Markdown(
        "| **Bold** \u52a0\u7c97 | `code` | [t](u) |\n|---|---|---|\n| x | y | z |"
    ).render(60)
    texts = [row.text for row in rows]
    assert texts[1] == "\u2502 Bold \u52a0\u7c97 \u2502 code \u2502 t (u) \u2502"
    styles = {seg.text: seg.style for seg in rows[1].segments}
    assert styles[" Bold \u52a0\u7c97 "] == Style(bold=True)  # merged onto the header base
    assert styles["code"] == CODE  # a colored run stays absolute
    assert styles["t"] == ACCENT.merge(Style(underline=True))  # the link label
    assert styles[" (u)"] == MUTED  # the url suffix (W3 drops it)
    # Data rows: the first column carries the theme's first_column base.
    assert rows[3].segments[1] == Segment(" x         ", DEFAULT_THEME.first_column)
    assert rows[3].segments[3] == Segment(" y    ", NONE)


def test_table_cell_escaped_pipe_stays_one_cell():
    # W1: splitting only happens on unescaped pipes, and a cell's "\|"
    # comes back as a literal "|" -- one inline-code cell, grid intact.
    rows = Markdown(
        "| \u8868\u8fbe\u5f0f Expression | \u8bf4\u660e Note |\n| :--- | :--- |\n"
        "| `a \\| b` | \u7ba1\u9053\u7b26\u8f6c\u4e49 escaped pipe |"
    ).render(60)
    texts = [row.text for row in rows]
    assert len(texts) == 5  # one data row: no mid-grid rule
    assert texts[3] == (
        "\u2502 a | b             \u2502 \u7ba1\u9053\u7b26\u8f6c\u4e49 escaped pipe \u2502"
    )
    codes = [seg for seg in rows[3].segments if seg.style == CODE]
    assert codes == [Segment("a | b", CODE)]  # exactly one inline-code cell
    # A row whose last pipe is escaped keeps it inside the cell.
    tail = Markdown("| x | y |\n|---|---|\n| a | b \\| |").render(40)
    assert tail[3].text == "\u2502 a \u2502 b | \u2502"


def test_thematic_break_renders_a_divider():
    assert _texts(Markdown("---").render(10)) == ["\u2500" * 10]
    assert _texts(Markdown("--").render(10)) == ["--"]  # not a break


def test_inline_code_bold_italic_link_and_literals():
    row = Markdown("a `code` **bold** *em* [t](u)").render(80)[0]
    assert row.text == "a code bold em t (u)"
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["code"] == CODE
    assert styles["bold"] == Style(bold=True)
    assert styles["em"] == Style(italic=True)
    assert styles["t"] == ACCENT.merge(Style(underline=True))
    assert styles[" (u)"] == MUTED
    literal = Markdown("a*b and 2*3 and `oops").render(80)[0]
    assert literal.text == "a*b and 2*3 and `oops"  # unclosed markers stay literal


def test_streaming_every_prefix_is_safe_and_fits():
    source = "# T\n\npara `c` **b** *i*\n\n- item\n  - sub\n\n> q\n\n```\nx\n```\n"
    for size in range(len(source) + 1):
        for row in Markdown(source[:size]).render(24):
            assert row.width <= 24  # no row ever exceeds the width


def test_custom_rules_join_the_registries():
    class Strike:
        name = "strike"

        def match(self, text, pos):
            if not text.startswith("~~", pos):
                return None
            end = text.find("~~", pos + 2)
            return None if end < 0 else (end + 2, [Segment(text[pos + 2 : end], Style(dim=True))])

    row = Markdown("a ~~b~~ c", inline_rules=[Strike(), *INLINE_RULES]).render(80)[0]
    assert row.text == "a b c"
    assert {seg.text: seg.style for seg in row.segments}["b"] == Style(dim=True)
    # A custom block rule interrupts a paragraph like a built-in one.
    class Shout:
        name = "shout"

        def match(self, lines, i):
            return 1 if lines[i].startswith("!") else None

        def render(self, lines, width):
            return [Line.from_text(lines[0][1:].strip().upper()).fit(width)]

    md = Markdown("para one\n!shout\npara two", block_rules=[Shout(), *default_block_rules()])
    assert _texts(md.render(80)) == ["para one", "SHOUT", "para two"]
