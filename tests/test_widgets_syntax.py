"""Tests for mocode_tui.widgets.syntax (the built-in highlighter).

Contracts (COMPONENTS.md / W3 ticket): a per-language table of ordered regex
rules colors five token classes -- comment (muted italic), string (success),
number (warning), keyword (accent's hue), builtin (code) -- every value
derived from the theme and none carrying bold; an unknown or missing language
falls back to the theme's ``code`` monochrome; custom tables extend or
override the built-ins; each line is matched on its own and no row ever
shifts a wide character.
"""

from dataclasses import replace

import pytest

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import Style
from mocode_tui.core.text import visible_width
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.syntax import (
    Highlighter,
    RegexHighlighter,
    default_highlighter,
    highlight,
)

COMMENT = DEFAULT_THEME.muted.merge(Style(italic=True))
STRING = DEFAULT_THEME.success
NUMBER = DEFAULT_THEME.warning
KEYWORD = Style(fg=DEFAULT_THEME.accent.fg)
PLAIN = DEFAULT_THEME.code  # plain code and the builtin token share this color


def _tokens(row: Line) -> list[tuple[str, Style]]:
    return [(seg.text, seg.style) for seg in row.segments]


def _first(code: str, lang: str, highlighter=None) -> list[tuple[str, Style]]:
    hl = highlighter if highlighter is not None else RegexHighlighter()
    return _tokens(hl.highlight(code, lang)[0])


# --- python --------------------------------------------------------------------


def test_python_colors_every_token_class():
    row = RegexHighlighter().highlight(
        "# note\n"
        "def f():\n"
        "    return 1\n"
        '    y = "s"',
        "python",
    )
    assert _tokens(row[0]) == [("# note", COMMENT)]
    assert _tokens(row[1]) == [("def", KEYWORD), (" f():", PLAIN)]
    assert _tokens(row[2]) == [
        ("    ", PLAIN),
        ("return", KEYWORD),
        (" ", PLAIN),
        ("1", NUMBER),
    ]
    assert _tokens(row[3]) == [("    y = ", PLAIN), ('"s"', STRING)]


def test_python_strings_swallow_comments_and_keywords():
    # '#' and 'def' inside a string are literal string text, not tokens.
    assert _first('x = "# not a comment"', "python") == [
        ("x = ", PLAIN),
        ('"# not a comment"', STRING),
    ]
    assert _first('y = "def f()"', "python") == [("y = ", PLAIN), ('"def f()"', STRING)]


# --- the rest of the table -----------------------------------------------------


def test_javascript_and_typescript_share_the_c_family_rules():
    assert _first('const x = "hi"; // tail', "javascript") == [
        ("const", KEYWORD),
        (" x = ", PLAIN),
        ('"hi"', STRING),
        ("; ", PLAIN),
        ("// tail", COMMENT),
    ]
    # 'js' is an alias, 'ts' adds the type-level keywords on top of 'js'.
    assert _first("const x = 1;", "js") == _first("const x = 1;", "javascript")
    assert ("number", KEYWORD) in _first("let x: number = 1;", "ts")


def test_bash_colors_builtin_commands_comments_and_strings():
    # builtins share the plain code color, so the two fuse into one segment.
    assert _first('echo "hi" # tail', "bash") == [
        ("echo ", PLAIN),
        ('"hi"', STRING),
        (" ", PLAIN),
        ("# tail", COMMENT),
    ]


def test_json_colors_keys_strings_numbers_and_literals():
    assert _first('{"a": 1, "b": true}', "json") == [
        ("{", PLAIN),
        ('"a"', KEYWORD),  # object key
        (": ", PLAIN),
        ("1", NUMBER),
        (", ", PLAIN),
        ('"b"', KEYWORD),
        (": ", PLAIN),
        ("true", KEYWORD),
        ("}", PLAIN),
    ]


def test_yaml_colors_the_mapping_key_and_comment():
    assert _first("key: value # tail", "yaml") == [
        ("key", KEYWORD),
        (": value ", PLAIN),
        ("# tail", COMMENT),
    ]
    assert _first("key: value", "yml") == _first("key: value", "yaml")  # alias


def test_toml_colors_the_header_key_and_string():
    rows = RegexHighlighter().highlight('[tool]\nname = "x"', "toml")
    assert _tokens(rows[0]) == [("[tool]", KEYWORD)]
    assert _tokens(rows[1]) == [
        ("name", KEYWORD),
        (" = ", PLAIN),
        ('"x"', STRING),
    ]


def test_markdown_headings_and_emphasis():
    assert _first("# title", "markdown") == [("# title", KEYWORD)]
    assert ("`code`", STRING) in _first("`code` **b** y", "md")


def test_diff_colors_added_removed_and_context_lines():
    rows = RegexHighlighter().highlight(" ctx\n-old\n+new", "diff")
    assert _tokens(rows[0]) == [(" ctx", COMMENT)]  # context
    assert _tokens(rows[1]) == [("-old", COMMENT)]  # removed
    assert _tokens(rows[2]) == [("+new", STRING)]  # added


def test_rust_and_go_color_keywords_and_numbers():
    # builtins share the plain code color and fuse with it.
    assert _first("fn main() -> i32 { 1 }", "rust") == [
        ("fn", KEYWORD),
        (" main() -> i32 { ", PLAIN),
        ("1", NUMBER),
        (" }", PLAIN),
    ]
    assert _first("func main() { println(1) }", "go") == [
        ("func", KEYWORD),
        (" main() { println(", PLAIN),
        ("1", NUMBER),
        (") }", PLAIN),
    ]


def test_c_and_cpp_share_rules_and_cpp_adds_its_own_keywords():
    assert _first("#include <stdio.h>", "c") == [("#include", KEYWORD), (" <stdio.h>", PLAIN)]
    assert _first("int x = 1;", "c") == [
        ("int", KEYWORD),
        (" x = ", PLAIN),
        ("1", NUMBER),
        (";", PLAIN),
    ]
    assert _first("auto x = 1;", "cpp") == [
        ("auto", KEYWORD),
        (" x = ", PLAIN),
        ("1", NUMBER),
        (";", PLAIN),
    ]
    assert ("template", KEYWORD) in _first("template <class T> struct S;", "c++")


def test_html_and_css_color_tags_properties_and_numbers():
    # builtins (attribute/property names) share the plain color and fuse.
    assert _first('<a href="u">x</a>', "html") == [
        ("<a", KEYWORD),
        (" href=", PLAIN),
        ('"u"', STRING),
        (">x", PLAIN),
        ("</a", KEYWORD),
        (">", PLAIN),
    ]
    assert _first(".a { color: #fff; }", "css") == [
        (".a", KEYWORD),  # selector
        (" { color: ", PLAIN),  # the property fuses with the plain around it
        ("#fff", NUMBER),  # hex color
        ("; }", PLAIN),
    ]


def test_sql_is_case_insensitive_and_colors_strings_and_comments():
    tokens = _first("SELECT 1 FROM t WHERE a = 'x' -- tail", "sql")
    assert ("SELECT", KEYWORD) in tokens
    assert ("FROM", KEYWORD) in tokens
    assert ("1", NUMBER) in tokens
    assert ("'x'", STRING) in tokens
    assert ("-- tail", COMMENT) in tokens


# --- fallbacks and edge cases --------------------------------------------------


def test_unknown_and_empty_languages_fall_back_to_monochrome():
    for lang in ("", "brainfuck", "py3"):
        assert _first("whatever 42", lang) == [("whatever 42", PLAIN)]


def test_empty_code_is_one_empty_line_per_row():
    assert RegexHighlighter().highlight("", "python") == [Line()]
    assert RegexHighlighter().highlight("\n\n", "python") == [Line(), Line(), Line()]


def test_a_wide_character_line_never_shifts():
    code = 's = "\u4f60\u597d"  # \u4e2d\u6587'
    row = RegexHighlighter().highlight(code, "python")[0]
    assert row.text == code  # nothing dropped, nothing duplicated
    assert row.width == visible_width(code)


def test_block_constructs_are_approximated_per_line():
    # No cross-line state: a triple-quoted opener keeps the rest of its line
    # and every later line uncolored (documented in the module docstring).
    rows = RegexHighlighter().highlight('"""doc\nstill doc\nend"""', "python")
    assert "".join(seg.text for seg in rows[1].segments) == "still doc"
    assert all(seg.style == PLAIN for seg in rows[1].segments)


def test_language_tags_are_normalized_and_may_carry_attributes():
    built = RegexHighlighter()
    assert built.highlight("x = 1", "PY") == built.highlight("x = 1", "python")
    assert built.highlight("x = 1", " Python ") == built.highlight("x = 1", "python")
    assert built.highlight("x = 1", "python title=foo") == built.highlight("x = 1", "python")


# --- configuration -------------------------------------------------------------


def test_token_colors_follow_the_theme():
    theme = replace(DEFAULT_THEME, warning=Style(fg="#abcdef"))
    built = RegexHighlighter(theme=theme)
    assert _tokens(built.highlight("n = 1", "python")[0]) == [
        ("n = ", theme.code),
        ("1", theme.warning),
    ]


def test_custom_languages_extend_and_override_the_table():
    built = RegexHighlighter(
        languages={
            "toy": [(r"#.*", "comment"), (r"\bwow\b", "keyword"), (r"!!", Style(fg="#ff0000"))],
            "python": [(r".*", "string")],
        }
    )
    assert _tokens(built.highlight("wow !! # hi", "toy")[0]) == [
        ("wow", KEYWORD),
        (" ", PLAIN),
        ("!!", Style(fg="#ff0000")),
        (" ", PLAIN),
        ("# hi", COMMENT),
    ]
    assert _tokens(built.highlight("def f(): pass", "python")[0]) == [
        ("def f(): pass", STRING)
    ]
    # Unmentioned built-ins survive; the override is per normalized key, so
    # the 'py' alias still points at the stock Python rules.
    assert _first("const x = 1;", "js", built) == _first("const x = 1;", "javascript")
    assert _first("def f(): pass", "py", built) == _first("def f(): pass", "python")


def test_an_unknown_token_name_fails_at_construction():
    with pytest.raises(ValueError):
        RegexHighlighter(languages={"toy": [("a", "bogus")]})


# --- shared instance and the convenience entry ---------------------------------


def test_default_highlighter_is_built_once_and_is_a_highlighter():
    assert default_highlighter() is default_highlighter()
    assert isinstance(default_highlighter(), Highlighter)


def test_highlight_entry_matches_the_highlighter_and_honors_theme():
    assert highlight("x = 1", "python") == RegexHighlighter().highlight("x = 1", "python")
    theme = replace(DEFAULT_THEME, warning=Style(fg="#abcdef"))
    assert highlight("n = 1", "python", theme=theme) == RegexHighlighter(
        theme=theme
    ).highlight("n = 1", "python")

    class Stub:
        def highlight(self, code, lang):
            return [Line.from_text(f"{lang}:{code}", Style(bold=True))]

    # An explicit highlighter wins and `theme` is ignored.
    stub = Stub()
    assert highlight("body", "python", highlighter=stub, theme=theme) == [
        Line.from_text("python:body", Style(bold=True))
    ]
