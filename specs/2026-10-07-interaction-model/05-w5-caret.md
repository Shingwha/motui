# Spec interaction-model · 点击落光标（波次 W5）
> 分支 `im5-caret`；前置：**W2 已合并**（硬依赖 `click(row, col)`）；调度上排在 W4 之后——
> 落工时 `examples/showcase/components.py` 已带焦点环接线，本波只能在其之上改。
> 深读：`00-overview.md`（宪法第 4 条）、`ref/audit-interaction.md`。
> **最高约束：cell → offset 的反向映射只写一次。** 落点是"格子的逆运算"，不是一个新算法。

## 目标

`Input` / `Editor` 成为 `Clickable`：点在文本上，块光标落在那一格。机制只有一条：
`TextBuffer` 的"渲染格子 → 文本偏移"反向映射；两个 shell 只负责把自己的行/列策略
（窗口偏移、prompt 缩进）还原掉。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 行几何已完整 | `widgets/textbuf.py` 的 `visual_rows(width, indent)`、`locate(rows)`、`cursor_position(...)`、`_VisualRow(start, end, text, line_start, line_end)` |
| 已有三处各算各的换算 | `locate`（flat → 视觉行/列）、`cursor_position`（→ 屏幕格）、`move_up`/`move_down`（借 `locate` 保列）——**本波不许再添第四套** |
| 字段的两种行策略 | `Input._row_prefix`（第 0 行是 prompt，缩进 = `visible_width(prompt)`）；`Editor._window_start`/`_row_cap`（`max_rows` 居中窗口，`editor.py`） |
| 块内坐标从哪来 | `app.Hit.row/col` 是**块内** 0-based（`app.py` 的 `Hit`）；`hit.col` 已把屏幕列映射进 `[0, width-1]` |
| 现状 | 字段**没有** `click`：点文本无效；展示台 fields 页只能靠方向键挪光标 |

## 工单（按序执行，每项一个 commit）

### T1 `TextBuffer.place(visual_row, col) -> bool`

- 契约（docstring 写全）：
  - 入参 = **渲染后**的视觉行号与显示列（`indent` 已含在 `col` 里）；
  - `visual_row` 越界 → `False`，不动状态；命中 → 停靠光标并返回 `True`（与 `move_*` 同契约）；
  - 列映射按**显示宽度**走：落在宽字符的后半格归到该字符；落在行尾之后归到行尾（`row.end`）；
    空行归到 `line_start`；`col < indent` 归到该行起点；
  - 落点是**逻辑**位置：`_VisualRow.line_start` 给出该视觉行所属逻辑行的起点，
    坐标必须换算回 `self._row` / `self._col`（**不许假设视觉行号 == 逻辑行号**）。
- **反屎山条款**：动手前先看 `locate()` / `cursor_position()` / `move_up()` 里现有的换算。
  若 `place()` 需要第四份 flat-offset ↔ (row, col) 算术，**先把它们收敛成一对私有助手**
  （例如 `_position_of(offset) -> (row, col)` 与 `_offset_of(row, col) -> int`），让四个调用者共用，
  再落 `place()`。不收敛不准合并。
- 单测（`tests/test_widgets_editing.py` 或就近的新文件）：首格 / 中间 / 行尾 / 行尾之后一格 /
  空行 / 跨包裹行的第二段 / 宽字符（`"中"`）的前半与后半格 / emoji / `indent>0`（prompt）/
  越界行（−1、len(rows)）/ 超长列。

### T2 字段的点击入口（两个 shell）

- `widgets/field.py`：`_TextField.click(row: int, col: int) -> bool` —— 把**块内**坐标还原成
  buffer 的视觉坐标，再委托 `place`：
  - `Editor`：`row` 加回窗口起点。窗口起点用与 `render` 相同的算式
    （`self._window_start(len(rows), cursor_index)`，`cursor_index` 由当前光标现算），
    这样"屏幕上第几行"与"buffer 里第几行"始终对齐；
  - `Input`：`col` 与 prompt 缩进的关系交给 `place` 处理（`indent` 已在 buffer 上）；
    多行残留文本（宿主显式 `insert("\n")` 的历史行为）按视觉行照常接受；
  - `focused` 为假时也落点（先聚焦是宿主/焦点环的事，组件不做焦点策略——D4）。
- `Input` / `Editor` 因此满足 `Clickable`（不需要新方法：继承 `_TextField.click`）。
- 单测：`Editor` 在 `max_rows` 窗口滚动后点窗口内第 3 行 → 落点正确（与 `render` 的行逐行对照）；
  `Input` 点 prompt 右侧第 2 格 → 光标在字符 2；点 prompt 上 → 行首；`row` 越界 → False。

### T3 消费者与文档

- `examples/showcase/components.py` 的 fields 页：hint/文案改为"点在你想要的位置"，
  并让 `windowed` 编辑器也进焦点环时仍可点（焦点环的 click 会先聚焦再派发——W4 的规则）。
- `docs/COMPONENTS.md`：交互表 `click(row) -> bool` 一行改为 `click(row, col) -> bool` 并把
  `Input` / `Editor` 加进组件列；两行组件表补"点击落光标（`place`）"；
  `docs/DESIGN.md` 的"Text and cursor"行补一句落点契约。
- `README.md`：`Input` / `Editor` 两行补"click(row, col) places the caret"。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 全绿（含 T1/T2 新用例）。
2. 探针（不依赖渲染）：对同一个 buffer，`place(r, c)` 后再 `cursor_position(...)`
   应回到同一格 —— 写一条**往返性质**的测试（覆盖宽字符与多视觉行），这是"逆运算正确"的最强证据。
3. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；
   `--pages` dump 的 fields 页文本不变。
4. `uv run python tools/framebench.py` → render-hash 不变（本波不改渲染）。
5. 真机：`/fields` 页点第三行中间 → 块光标落在那格；点行尾右侧 → 落在行尾。

## 禁触清单

- `widgets/choice.py` / `tree.py` / `tabs.py` / `table.py`（本波只碰字段与 buffer）。
- `core/`、`keys/`、`app.py`（坐标来源已就绪）。
- `chat/`（composer 的编辑器继承新能力即可，不改代码；若要接线先上报）。
- `specs/`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 往返性质测试的输出 / 换算收敛的记录
（"改了哪三处旧调用点"或"确认无需收敛"的举证） / 偏差与取舍 / 未决问题。
