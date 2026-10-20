# W1 交接包 — the glyph vocabulary
> 分支 `refactor/120-glyphs` / 起点 `58dbd09` / 2026-10-20

## A. 自动事实（命令与代码）

- `git diff --stat 58dbd09..HEAD`：15 files, +1337 / -153。
  新增 `src/motui/kernel/glyphs.py`（110 行常量+3 helper）、`tests/test_glyphs.py`（99）、
  `tests/test_glyph_vocabulary.py`（467，契约矩阵 7 cases × 5 scenarios = 35 instances）；
  改 `kernel/mark.py`、`widgets/{list,choice,navlist,tree,table}.py` 与对应 6 个测试文件。
- 公开接口（全部 keyword-only）：
  - `motui.kernel.glyphs`：15 常量 + `seat(glyph)->str`、`seat_width(glyph)->int`、
    `pair_seat(glyph, other)->str`；未进任何门面 `__all__`。
  - `List(items, *, ..., marker=glyphs.CURSOR, more_up=glyphs.MORE_UP,
    more_down=glyphs.MORE_DOWN, mark_pair=(MARKED, UNMARKED))`
  - `Select(..., marker=glyphs.MENU_CURSOR, mark_pair=(MARKED, UNMARKED))`；
    `Radio(..., empty=glyphs.RADIO_EMPTY, filled=glyphs.RADIO_FILLED)`；
    `CheckGroup(..., mark_pair=(MARKED, UNMARKED))`
  - `NavList(..., bar=glyphs.RAIL_BAR, bar_space=None)`（None = 派生 separator）
  - `Tree(..., expanded=glyphs.EXPANDED, collapsed=glyphs.COLLAPSED)`
  - `Table(..., mark_pair=(MARKED, UNMARKED))`
  - `mark_prefix(marked, *, marked_glyph=MARKED, unmarked_glyph=UNMARKED)` 返回 `seat(glyph)`。
- 门禁（HEAD `b4de15a` 上真实结果）：`uv run pytest -q` → `1693 passed, 1 skipped`；
  `uv run python tools/golden.py --check` → `golden: 11 pages match`；
  framebench exit 0，`render-hash : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`；
  `python -m motui`（stdin DEVNULL）exit 0；`python -m motui --pages` exit 0。
- T8 清理证明：`grep -rn "MARKER\|EMPTY_MARK\|FILLED_MARK\|MORE_UP\|MORE_DOWN" src/motui/widgets/`
  仅剩 `list.py:171 glyphs.MORE_UP`、`list.py:172 glyphs.MORE_DOWN`；旧常量零残留。

## B. 只存在于脑子里的东西

- **NavList 与票据字面式的偏差（有意）**：票据写 `bar_space = " " * seat_width(bar)`。
  实际拆成「bar 列（glyph 自身宽度）+ separator（默认 1 空格，bar 为空时 0）」，
  存储的 `self.bar_space` 是两者之和，默认值正好等于 `" " * seat_width(bar)`。
  原因：`demo/shell.py` 传 `bar_space=" "` 且 demo 禁触；只有这个模型能同时让
  demo 文本零 diff、宽 glyph 对齐、空 bar 折成 0 格。`bar_space` 参数的新语义是
  「separator 的宽度」，其值宽度决定 separator，勿再当整条 gutter 用。
- **List 计数行 token**：`_layout()` 用私有对象 `_ABOVE/_BELOW`，不能用 glyph 当 token
  ——host 可把 `more_up` 与 `more_down` 传成同一串。
- **Radio**：不再给 base 传 `FILLED_MARK.rstrip()`，改为 `marker=""` 并自行渲染 pair；
  `empty/filled` 放在 Radio 自己的 slots，`_revision()` 覆写追加这两个字形。
  `Select._revision()` 已含 `mark_pair`；`Select` 的新 `mark_pair` 参数是 interfaces 表
  未列的必要扩展（`multi=True` 与 CheckGroup 共用）。
- **空 pair 的 Table**：prefix 为 `""` 时不插入零宽 Segment；`_measure_widths` 加 0，
  因此空 pair 下标记完全不可见且几何不变。
- **坑（按成本排序）**：① `Line.styled()` 每段之间发 RESET，改变分段会改变 styled 字节；
  NavList 特意保留旧分段（bar / separator+label），不要“顺手”合并。② golden 只比纯文本，
  但 CRLF 规则照旧（只接受 LF→CRLF），本波零重录。③ `visible_width` 对 CJK 是 2，
  一切宽度断言必须用它；`str.index` 是码点不是列。④ `uv sync --locked` 在本机解析到
  CPython 3.13.16（不是文档里的 3.12），锁定包不变、测试全绿。
- **W2 边界**：`glyphs.TRACK/THUMB/TASK_OPEN/TASK_DONE` 已就位但 W1 未消费；
  `interaction/scrollbar.py` 与 `widgets/markdown/` 未动（其 `TRACK/THUMB/TODO_MARK/DONE_MARK`
  仍存在，W2 删除并改 import `motui.kernel.glyphs`）。`ref/interfaces.md` 需 lead 按现实回写
  （尤其 NavList 的 `bar_space` 语义与 Select 的 `mark_pair`）。

## C. 指针

- 词汇与 helper：`src/motui/kernel/glyphs.py:83-110`。
- 座位规则落点：`list.py:450-480`（`_row`/pair）、`choice.py:531-575`（Select `_row`）、
  `choice.py:775-806`（Radio pair + revision）、`navlist.py:178-192`（seat 派生）、
  `tree.py:510-535`（indicator pair）、`table.py:648-664`（`_mark_width`/`_mark_seat`）。
- 契约矩阵：`tests/test_glyph_vocabulary.py`（每 case 的 `custom/empty/wide/pair` check 是
  下一波改组件时最先会红的测试）。
- commit：`d9d3261` T1 → `3b1e49c` T2 → `7cced2b` T3 → `e941741` T4 → `33fd8ae` T5 →
  `1b405aa` T6 → `aa898c5` T7 → `b4de15a` T8（每 commit 独立过五条门禁）。
- 稳定区（勿重读）：`kernel/lines.py` 行模型、行带合约、`tools/golden.py`。
