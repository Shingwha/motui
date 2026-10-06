# Spec interaction-model · 命中带列（波次 W2）
> 分支 `im2-hit`；前置：**W1 已合并**；深读：`00-overview.md`（宪法第 1 条、决策 D1）、
> `ref/audit-interaction.md`（现状清单：每个 `click` 实现、全部调用点、测试锚点）。
> **最高约束：`click` 的列语义必须在组件内部消化，宿主只说"点到哪一格"。**
>
> ✅ **2026-10-07 已合并** @ `im2-hit`（终态 `868 passed, 1 skipped`）。

## 目标

`Clickable.click(row, col) -> bool` 全量替换 row-only 签名，并把 `Tabs` 的"列 → tab 序号"算术
**从宿主收回组件**——展示台里手写的 `_tab_at()` 删除。这是协议裂缝的修补，不是 demo 的补丁。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 协议本体 | `src/mocode_tui/core/block.py` 的 `Clickable`（docstring + `click(row)`） |
| 行式实现 | `widgets/choice.py` 的 `Select.click`（title 偏移 + 窗口偏移）、`Confirm.click`（转发）；`widgets/tree.py` 的 `Tree.click` |
| 列式语义被挤到宿主 | `widgets/tabs.py` 的 `Tabs.click(ordinal)` 文档写着"由 host 解析格子"；`examples/showcase/session.py` 的 `_tab_at()` 就是那段宿主算术 |
| 规范示例 | `app.py` 的 `hit_test` docstring、`README.md` 的鼠标段、`docs/DESIGN.md` 的点击示例、`docs/COMPONENTS.md` 的交互表——四处都写着 `click(hit.row)` |
| 测试调用点 | `tests/test_widgets_choice.py`、`tests/test_widgets_autocomplete.py`、`tests/test_widgets_basics.py`（Tabs/Tree）——清单在 ref |

## 工单（按序执行，每项一个 commit）

### T1 协议与四个实现

- `core/block.py`：`Clickable.click(self, row: int, col: int) -> bool`（**col 无默认值**，D1）。
  docstring 写清：坐标是**块内**的 0-based `(行, 列)`，与 `app.Hit` 报的一致；
  行式组件忽略列时**必须在自己的 docstring 写明"忽略 col"**；返回是否消费。
- `widgets/choice.py`：`Select.click(row, col)` / `Confirm.click(row, col)`（忽略 col，写明；
  现有 title/窗口/计数行算术一字不改）。
- `widgets/tree.py`：`Tree.click(row, col)`（忽略 col，写明）。
- `widgets/tabs.py`：`Tabs.click(row, col)` —— **列算术搬进来**：
  - `row != 0` → False（strip 只有一行；空 strip 也 False）；
  - 用**自己的渲染结果**定位：`self.render(self._last_width)` 的 segment 顺序与
    `visible_width` 累计，把 `col` 映射成 tab 序号；落在分隔符/两端空格/超出 → False；
  - `_last_width` 是本工单引入的组件字段：`render(width)` 里记下宽度，默认 `80`
    ——与 `TextBuffer.last_width` 同一惯例（"首次渲染前按 80 列"），docstring 写明；
  - 命中即 `self.select(index)`：**`Tabs.activate(index)` 在本波改名 `select(index)`**
    （`move` / `click` 内部调用点一起改）。理由：本波正在重写这个类的命中面，
    旧名在这里失去最后一个调用点是本仓的替换铁律；`activate` 这个名字留给 W3 的协议
    （见 `00-overview.md` 命名宪法，W2 淘汰行）。`click` 的旧"收序号"语义同时消灭。
- 验证：`tests/test_widgets_basics.py` 的 Tabs 用例改为 `select(...)` 并补列映射；
  `Select`/`Tree` 加"col 任意值不影响结果"。

### T2 宿主与消费者

- `app.py` 的 `hit_test` docstring 示例 → `hit.block.component.click(hit.row, hit.col)`。
- `examples/showcase/session.py`：
  - 删除 `_tab_at`（以及只为它存在的 `visible_width` import）；
  - `_play_click` 的派发统一成 `component.click(hit.row, hit.col)`，`isinstance(component, Tabs)` 特例分支删除；
  - `script.py` 的点击坐标脚本不需要改（它按屏幕格子点）。
- 文档四处同步：`README.md` 鼠标段、`docs/COMPONENTS.md` 交互表、`docs/DESIGN.md` 命名表与示例。

### T3 测试

- 全量更新既有 `click(...)` 调用点（加 `col` 实参；ref 里有逐条清单）。
- 新增：`Tabs` 列→序号（首个 / 中间 / 末个 / 分隔符上 / 两端空格 / 越界 / 空 strip /
  含宽字符 label）；`Select` 的窗口 + 计数行映射在带 col 后不变；`Tree` 不变。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 全绿（总数 = 基线 + 本波新增）。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0（脚本里含 Tabs 点击）。
3. `uv run python examples/demo.py --pages | grep -c 'overview │ components │ keys'` → 1（页面渲染不变）。
4. `uv run python tools/framebench.py` → render-hash 不变。
5. 真机：点 Tabs 的第 2/第 3 个 → active 跟着走；点分隔符 → 不动。

## 禁触清单

- `core/events.py`、`keys/`（事件模型本波不动）。
- `widgets/{table,textbuf,field,input,editor}.py`（W5/W6 的领地）。
- `chat/`（W3 的领地）。
- `specs/`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 行为变化 A/B（`Tabs.click` 的语义从"序号"变"格子"——
这是**破坏性**签名变更，需在报告里点名所有调用点都已更新）/ 偏差与取舍 / 未决问题。
