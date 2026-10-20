# W2 · 外围字形与文档
> ✅ 2026-10-20 @ `refactor/120-periphery` — merged (3134fe5)；交接包 `handoff/W2-periphery.md`
> 分支 `refactor/120-periphery`；前置 W1 已合并（`b1bd8fd`）；写入范围
> `src/motui/interaction/scrollbar.py`、`src/motui/widgets/markdown/`、`docs/DESIGN.md`、
> `docs/COMPONENTS.md`、`CHANGELOG.md`、`README.md`、`tests/test_scrollbar.py`、
> `tests/test_widgets_markdown.py`、`specs/2026-10-20-1628-glyph-vocabulary/handoff/W2-periphery.md`

## 目标

把最后两处硬编码字形参数化（Scrollbar 的 track/thumb、Markdown 的任务框），把词汇写进设计文档与
宿主契约，并保持默认渲染逐字节不变。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W1-glyphs.md` → 本工单。
- W1 交付摘要：`kernel/glyphs.py` 已有 15 常量 + `seat/seat_width/pair_seat`；六个行组件已参数化；
  测试 1693 passed / 1 skipped；golden 11 页零重录；render-hash `f872187a…` 不变。
- 接口变更（相对草案）：NavList 增加 `bar_space=None`（separator 语义）；Select 增加 `mark_pair`。
- 基线命令（开工先跑并贴真实输出）：`uv run pytest -q`（期望 1693 passed, 1 skipped）、
  `uv run python tools/golden.py --check`（11 页 match）。
- 稳定区（勿重读）：`kernel/lines.py`、行带合约、`tools/golden.py`、W1 的六个行组件实现。
- 已知坑（来自 W1 handoff）：`Line.styled()` 段间 RESET——不要合并既有分段；CJK 宽度一律
  `visible_width`；golden 的 CRLF 规则；`uv sync --locked` 本机解析到 3.13.16（不影响门禁）。

## 工单（按序执行，每项一个 commit，每个 commit 过五条全量门禁）

### T1 — `Scrollbar(track=glyphs.TRACK, thumb=glyphs.THUMB)`
- `interaction/scrollbar.py`：构造参数化；strip 使用两个字形；**strip 的记忆键加入 track/thumb**
  （换字形不得命中旧条）；删除模块常量 `TRACK`/`THUMB`（无别名），内部改 import glyphs。
- 测试：默认字节不变；自定义字形；空字符串的行为按 `visible_width` 走（若空字形在滚动条上无意义，
  如实报告并保持与现有 `size: 0` 一致的最接近语义）。

### T2 — `Markdown(task_marks=(glyphs.TASK_OPEN, glyphs.TASK_DONE))`
- `widgets/markdown/`：`Markdown` 构造参数 → `RenderContext` 字段 → 内置 task 规则读它；
  任务框的动作跨度仍覆盖「字形 + 空格」整段，`"todo:<n>"` 载荷不变；删除 `TODO_MARK/DONE_MARK`
  常量（无别名）。
- 测试：默认字节不变；自定义 pair；跨度与载荷不变。

### T3 — 文档
- `docs/DESIGN.md`：命名宪章加 "Glyphs" 一行（词汇模块、座位规则、空串语义、字形是内容不是样式）。
- `docs/COMPONENTS.md`：组件参数总表加入全部字形参数（含 W1 的六个组件与 W2 的两个）、默认值、
  关闭规则、pair 对齐规则。
- `CHANGELOG.md` 的 `## [1.1.9]`：Added 记词汇与参数；Changed 记旧模块常量删除（无别名）与
  空串语义。
- `README.md`：若枚举了组件/参数则同步（先 grep）。

### T4 — 门禁
五条全量门禁在最终树上跑一遍并贴真实输出。

## 验收（真实输出进报告）

1. `uv run pytest -q` 全绿（基线 1693 + 新增）。
2. `uv run python tools/golden.py --check` → 11 页 match（**零重录**）。
3. framebench exit 0，render-hash 仍为 `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
4. 两个 demo 管道 exit 0。
5. 文档声明抽查 ≥6 条，逐条附代码行号。

## 禁触清单

`src/motui/kernel/` 全部；`src/motui/widgets/` 除 `markdown/` 外的任何文件；`src/motui/interaction/`
除 `scrollbar.py` 外的任何文件；`demo/`；`tests/golden/`；`tests/` 除
`test_scrollbar.py`/`test_widgets_markdown.py` 外的任何文件；`pyproject.toml`；`uv.lock`；
`specs/` 除自己名下的 `handoff/W2-periphery.md` 外的任何文件。

## 交接包

分支最后一个 commit 写 `specs/2026-10-20-1628-glyph-vocabulary/handoff/W2-periphery.md`
（60–80 行，A/B/C 三节）。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
阻塞即停，不越界自救。
