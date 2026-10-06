# Spec W2 · `visible_width` measures grapheme clusters

> Branch `fix/w2-cluster-width`; 前置: W1 and W3 merged into `main`; 深读:
> `specs/2026-10-06-preview-fidelity/00-overview.md` (report 4),
> `src/mocode_tui/core/text.py`, `src/mocode_tui/core/lines.py`.

## 目标

Rows that carry emoji wrap and cut a few columns early, so text after them
drifts — the "slight offset" the owner saw in the preview pane. Measured on
the fixture's own row at `HEAD`: the toolkit counts **95** columns where a
terminal renders **90**, because `visible_width` rides `wcswidth`, which
joins `👨‍👩‍👧‍👦` correctly but counts `🧑🏽‍💻` as 4 and `🏳️‍🌈` as 4 instead
of 2 each. 最高约束: `visible_width` stays the toolkit's single source of
truth for display width and the runtime dependency stays `wcwidth` only —
the cluster rules are expressed with code points, no new dependency, no
second copy of the measure.

## 工单（按序，每项一个 commit）

### T1 聚簇测量

- `src/mocode_tui/core/text.py`: make `visible_width` measure grapheme
  clusters. A cluster contributes the width of its first printing cell and
  every continuation character contributes 0:

  | Rule | Characters |
  |---|---|
  | ZWJ join | U+200D followed by a base: the following cell joins the cluster |
  | variation selector | U+FE00–U+FE0F |
  | skin-tone modifier | U+1F3FB–U+1F3FF |
  | regional-indicator pair | two U+1F1E6–U+1F1FF form one flag cell |
  | combining mark | anything `wcwidth` reports as 0 or -1 (except tab, which keeps `TAB_WIDTH`) |

  Keep the existing contract in the docstring (tab = `TAB_WIDTH`, other
  non-printable = 0, empty = 0) and state the cluster rule beside it. A
  lone combining mark at a string's start contributes 0. Do not change
  `fit_text`, `wrap_text` or `wrap_spans` — they all measure through
  `visible_width` already.

### T2 回归锚点

- `tests/test_core_text.py`: add **one** test with the fixture's real
  sequences — family `👨‍👩‍👧‍👦` (2), technologist `🧑🏽‍💻` (2), rainbow flag
  `🏳️‍🌈` (2), `👋🏽` (2), a regional-indicator flag (2), `✅` (2), plain
  ASCII (n), and the full fixture emoji row (90 at a 78-column pane) —
  asserting `visible_width` per case and that the row wraps as a terminal
  would place it. Follow the file's conventions.
- Where the corrected numbers move an existing pinned value elsewhere,
  update **that** expectation and list it in the report with the before /
  after pair. No assertion may be weakened or deleted to make the change
  pass; if a pinned value cannot be reconciled, stop and report.

### T3 文档口径

- `src/mocode_tui/core/text.py` docstring only (no `docs/**`, no
  `README.md`): `visible_width` now says it measures by grapheme cluster,
  with the rules it applies.

## 验收（自测，报告真实结论）

1. `uv run pytest -q` — paste the real counts, and the
   list of every expectation you moved with its before → after value.
2. `uv run python examples/pi_demo.py < /dev/null; echo exit=$?`
   — must exit 0; note whether the final screen changed and why.
3. A probe printing `visible_width` for the six cases above (before the
   change they read 11 / 8 / 9 / 9 / … for their substrings).

## 禁触清单

`src/mocode_tui/core/frame.py`, `src/mocode_tui/app.py`,
`src/mocode_tui/chrome.py`, `src/mocode_tui/selection.py`,
`examples/pi_demo.py`, `docs/**`, `README.md`, `.zcode/**`. Beyond
`core/text.py`, the only files you may touch are `tests/test_core_text.py`
and the expectation files T2 lists. If the blast radius looks larger than
that, stop and report.

## 最终报告格式

Task table / commits (hash + message) / the three real outputs above /
every expectation moved (before → after) / deviations & trade-offs / open
questions.
