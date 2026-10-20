# W1 · The glyph vocabulary and the row components
> 分支 `refactor/120-glyphs`；前置 main（无 handoff）；写入范围 `src/motui/kernel/glyphs.py`（新）、
> `src/motui/kernel/mark.py`、`src/motui/widgets/{list,choice,navlist,tree,table}.py`、`tests/`、
> `specs/2026-10-20-1628-glyph-vocabulary/handoff/W1-glyphs.md`（新）

## 目标

**默认渲染逐字节不变**（golden 零 diff、render-hash 不变）的前提下，把全库的结构字形收敛为
一个词汇模块 + 三个座位 helper，并给六个行组件加字形参数：每个字形一个构造参数，空串即关闭、
几何塌缩，宽度一律走 `visible_width`。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（期望 1623 passed, 1 skipped）、
  `uv run python tools/golden.py --check`（11 页 match）。
- 稳定区（已验收，勿重读）：`kernel/lines.py` 的行模型与 `fit/fill/filled`；行带合约
  （`ground`/`ground_active`/`hover` 的解析与药丸宽度）。
- 已知坑：golden 的 CRLF 规则（`--update` 后只有换行 diff 的文件要 `git checkout --` 还原）；
  List 的座位用 `len(MARKER)`（宽字符错位，本波修复）；Radio 内部把 `FILLED_MARK` 冒充 base 的
  `marker`（本波去掉这个 hack）。

## 工单（按序执行，每项一个 commit，每个 commit 过全量门禁）

### T1 — `kernel/glyphs.py`（新）+ 测试
- 15 个常量：`CURSOR="▸"`、`MENU_CURSOR="→"`、`RAIL_BAR="▌"`、`EXPANDED="▾"`、`COLLAPSED="▸"`、
  `RADIO_EMPTY="( )"`、`RADIO_FILLED="(•)"`、`MARKED="[x]"`、`UNMARKED="[ ]"`、`MORE_UP="↑"`、
  `MORE_DOWN="↓"`、`TRACK="░"`、`THUMB="█"`、`TASK_OPEN="☐"`、`TASK_DONE="☑"`（后四个由 W2 消费）。
- 三个纯函数（`visible_width` 来自 `kernel/text.py`）：
  - `seat(glyph) -> str`：`glyph + " "`，空串 → `""`。
  - `seat_width(glyph) -> int`：`visible_width(glyph) + 1`，空串 → 0。
  - `pair_seat(glyph, other) -> str`：`seat(glyph)` 按 `max(seat_width(glyph), seat_width(other))` 补空格。
- 模块 docstring 一句话原则：字形是内容不是样式，不进出 Theme。
- 测试：空串、单格、宽字符（CJK）、pair 对齐（含空成员）。
- 不新增任何门面 `__all__` 名字（`motui.kernel.glyphs` 可直接 import）。

### T2 — `kernel/mark.py` 的 pair
- `MARKED/UNMARKED` 改为从 glyphs 导入；`mark_prefix(marked, *, marked_glyph=MARKED, unmarked_glyph=UNMARKED)`
  返回 `seat(glyph)`。默认输出不变（`[x] ` / `[ ] `）。
- 消费者（List/Table/CheckGroup）的默认行为不变（它们的参数在 T3/T4/T7 加）。
- 测试：默认字节不变 + 自定义 pair。

### T3 — `List`
- 新参数（keyword-only）：`marker=CURSOR`、`more_up=MORE_UP`、`more_down=MORE_DOWN`、
  `mark_pair=(MARKED, UNMARKED)`。
- 座位宽度改用 `seat_width(marker)`（修掉 `len()`）；计数行用 `more_up/more_down`；标记列用
  `pair_seat` 且列宽 = pair 宽度；`revision()` 纳入四个字形；docstring 说明空串语义；
  `__all__` 去掉 `MARKER`（旧常量删除，无别名）。
- 测试：默认逐字节不变（现有断言原样通过）；自定义字形；空字形塌缩；宽字形对齐。

### T4 — `Select` / `Radio` / `CheckGroup`（`widgets/choice.py`）
- `Select`：`marker=MENU_CURSOR`；座位一律 `seat(marker)` / `seat_width(marker)`；**空串 → 0 格、
  无悬空空格**（当前 `f"{marker} "` 会留一格）；`revision()` 纳入 marker。
- `Radio`：`empty=RADIO_EMPTY`、`filled=RADIO_FILLED`；自己渲染这个 pair 列（`pair_seat`），
  不再把 `FILLED_MARK` 冒充 base 的 `marker`；`revision()` 纳入。
- `CheckGroup`：`mark_pair=(MARKED, UNMARKED)`；保留 `marked=`（初始下标集）；标记列宽 = pair 宽度；
  `revision()` 纳入。
- 旧常量 `MARKER`/`EMPTY_MARK`/`FILLED_MARK` 删除（无别名），消费者同 commit 更新。
- 测试：默认不变 + 各自的自定义/空/宽字符用例。

### T5 — `NavList`
- `bar=RAIL_BAR`（默认指向常量）；`bar_space` = `" " * seat_width(bar)`；`bar=""` 保持 0 格。
- 测试：默认不变、自定义、空串。

### T6 — `Tree`
- `expanded=EXPANDED`、`collapsed=COLLAPSED`；指示列 = `pair_seat(indicator, other)`，
  叶子/空状态按 pair 宽度留空列（标签对齐）；`revision()` 纳入两个字形。
- 测试：默认不变、自定义、空串（列塌缩）、宽字符。

### T7 — `Table`
- `mark_pair=(MARKED, UNMARKED)`；标记列宽 = pair 宽度；`revision()` 纳入。
- 测试：默认不变、自定义、空串。

### T8 — 契约矩阵 + 清理证明
- 新文件 `tests/test_glyph_vocabulary.py`：参数化覆盖六个组件 × 五种情形
  （默认逐字节、自定义、空串塌缩、CJK 宽字形、pair 对齐），断言都落在 `Line` 的段/宽度上。
- `grep -rn "MARKER\|EMPTY_MARK\|FILLED_MARK\|MORE_UP\|MORE_DOWN" src/motui/widgets/` 只剩 glyphs 导入；
  报告贴真实输出。
- 各组件 docstring 补齐字形参数与空串语义；`README`/`docs` 本轮不动（W2）。

## 验收（真实输出进报告）

1. `uv run pytest -q` 全绿（贴用例数与失败项；基线 1623 + 新增）。
2. `uv run python tools/golden.py --check` → 11 页 match（**零重录**）。
3. framebench 包装命令 exit 0，render-hash 仍为 `f872187a…`。
4. 两个 demo 管道 exit 0。
5. T8 的 grep 输出与契约矩阵用例数。

## 禁触清单

`kernel/` 除 `glyphs.py`（新）与 `mark.py` 外的任何文件；`interaction/`；`widgets/` 除
`{list,choice,navlist,tree,table}.py` 外的任何文件（含 `markdown/`）；`demo/`；`docs/`；
`CHANGELOG.md`；`README.md`；`tests/golden/`；`pyproject.toml`；`uv.lock`；
`specs/` 除你自己名下的 `handoff/W1-glyphs.md` 外的任何文件。

## 交接包

完成后在分支最后一个 commit 写 `specs/2026-10-20-1628-glyph-vocabulary/handoff/W1-glyphs.md`
（60–80 行，按 SKILL.md 的 Handoff 协议：A 自动事实 / B 只存在于脑子里的东西 / C 指针）。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
阻塞即停，不越界自救。
