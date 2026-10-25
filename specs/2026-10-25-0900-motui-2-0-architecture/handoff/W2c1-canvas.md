# W2c1 交接 · Canvas / Fill / ScrollPanel / snake

> 分支 `2.0/w2c1-canvas`；起点 `86e9691`（W2b 合并 + seam fix 之后）。前置：`ref/interfaces.md`、`handoff/W2a-surface.md`、`W2b1-views.md`、`W2b2-content.md`。
> 结论：T1–T6 全部完成；**1115 passed**；57 golden 逐字节不变；render-hash 不变；Canvas 性能达标；snake 可跑。

## A. 交付面、性能与门禁

### Canvas / Sparkline（`widgets/canvas.py`）
- `Canvas(width=0, height=0, *, marker="cell", glyphs=GLYPHS, theme=None, styles=None)`；`width`/`height` 是可赋值属性，另有 `resize(w, h)`。
- `put/text/hline/vline/box/blit/plot/clear/surface/render`；`surface()` 返回缓存的 `Surface`，`render(c|int)` 按 `c.width`/`c.max_height` 裁矩形并以 `Surface.clipped` 返回（不 pad）。
- 每行只重建 dirty 行；未写行返回**同一个 `Line` 对象**（`is` 可断言）。`revision()` 是单调 mutation 计数，可进 Section 行缓存。
- Marker：`cell`（`glyphs.bar_full`）、`half`（`▀▄█`）、`braille`（U+2800 + 标准 8 点位），测试逐点断言。
- `Sparkline(values, *, marker="half", style=Style(), glyphs=GLYPHS)` 自然高 1 行，`max_height` 时填满该预算。
- 写宽字符占 2 列（续列为空 char）；写入宽字符任一半会先清空旧簇，跨右缘的宽写被丢弃；`blit` 不劈开宽字符。
- 性能（本机，5 次中位数，预热 3 次）：80×24 全异色 **0.496 ms**（阈值 2.0）；单色 **0.014 ms**（阈值 0.4）。全异色多次运行区间 0.5–1.8 ms，均 <2.0。

### Placement / Sizing / Fill（`kernel/document.py`）
- `Placement.FLOW/TOP/BOTTOM`、`Sizing.NATURAL/FILL`；`Section(id, component, *, pin=None, placement=None, sizing=NATURAL)`，`pin`/`placement` 二选一。
- `Section.placement/sizing/widget`（`widget is component`）；`pin` 仍回读 `"top"/"bottom"/None`。
- `Document.add(..., placement=FLOW, sizing=NATURAL)`：FILL 只能 FLOW、至多一个、FILL 后不得再加 FLOW（TOP/BOTTOM 仍可）；TOP/BOTTOM 只能 NATURAL；非法组合 `ValueError`。
- `Document.fill() -> Section | None`、`Document.fills() -> tuple[Section, ...]`；`Fill(widget)` 是冻结值（`kernel.document.Fill`）。

### Viewport FILL 路径（`kernel/layout.py`）
- `Document.fill()` 存在时走 `_layout_with_fill`，**不使用 `_BodyIndex`**（避免把 FILL 记成 body 污染前缀和）；直接遍历 pinned/flow sections。
- top/bottom 先占位；`available = height - kept`；flow 用 `ScrollState` 按 `flow_visible = min(available, flow_natural)` clamp/slice；`fill_budget = available - flow_visible`，FILL 以 `Constraints(width, max_height=fill_budget)` 渲染、截断并补空行到预算。
- `total_rows` 只计 flow 自然行（FILL 不滚动）；FILL 行进入 `row_blocks`（id+行号），补空为 `None`；`natural_height` 对 FILL 文档只数自然 sections。
- 无 FILL 文档的 offset/归属/字节完全不变（原测试全绿）。

### Pane / TUI / App
- `Pane.fill(component) -> Section`：清空该 pane 的 document，再 `add(sizing=FILL)`。
- `TUI.fill(component, *, pane=None) -> Section`；`TUI.add/Pane.add` 增加 `placement`、`sizing` 透传，`pin` 保留。
- `App.fill(component, *, pane=None) -> Section`：`TUI.fill` + 与 `add` 共用的私有 `_mount`（theme/focus 环）。
- `ScrollPanel(child, *, height=None, offset=0, bar=False, axis="y", glyphs, theme, styles)`；`axis != "y"` 抛 `ValueError`；内部仍是 `ScrollState`。`ScrollView` 已删除。
- `examples/snake.py`：`Snake`（Canvas + revision）+ `main`；`--headless` 用 `headless_tui(40,20)`、`tui.fill`、逐步 `step()+paint()`，exit 0，输出含 `score`。

### 门禁实测（2026-10-25，本 worktree）
- `pytest -q -p no:cacheprovider`：**1115 passed**。
- `tools/golden.py --check`：`57 topics match`；`framebench`：`render-hash a82f7968…` 不变。
- `python -m motui < /dev/null`：exit 0 / 70 行；`--pages`：exit 0 / 4059 行。
- `ruff check .` 通过；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken；`api.py --check` 181 names match；`growth.py --quick` pass/pass/OK。
- snake：`uv run python examples/snake.py --headless` -> `score 0, steps 19, alive False`，exit 0。
- W2b 适配器复验：`_render_takes_constraints` 对 Input/Canvas/Sparkline/ScrollPanel 为 True，对测试替身 `Rows` 为 False；两类在 `Section.row_count` 下都返回行。

## B. 偏差、取舍与坑

1. **Fill 是 Section 的 sizing，不是 `PaneContent` 联合**（工单既定）：`Fill` 值只是公开 API 雏形，W4 再接 `PaneContent`。`Fill` 只在 `kernel.document`，未进 kernel 根导出（本波写入范围不含 `kernel/__init__.py`）。
2. **`ScrollPanel` 仍用 `ScrollState`**；`axis` 只接受 `"y"`，x/both 留给 W2.6。
3. **golden 字节 vs 旧名**：demo shell 的页脚打印 `type(focused).__name__.lower()`，直接改名会让两个 golden 的 `focus scrollview` 变成 `scrollpanel`。为守住“57 golden 逐字节不变”，两个 topic 模块各留了一个**仅 demo 本地**的 `class ScrollView(ScrollPanel)` 展示子类（库面 `ScrollView` 已删除）；`api_line`/`components` 字符串也保持旧字面。W5 文档/金标重录时一并清掉。`grep -rn ScrollView src` 现在只剩这些 demo 展示串/子类。
4. **Canvas 行构建不走 `fuse`**：`fuse` 对同色长 run 每次 merge 都重建增长字符串（单色行约 250 µs）。Canvas 在写入时缓存每 cell 的 `Segment`，`surface()` 单趟合并 run；同色行/空行用 per-row census 一次生成（`_row_counts`/`_row_rep`），因此单色 0.014 ms。语义仍是“相邻同样式合并”，且不携带 link/action（Canvas 写入 API 没有这两个槽）。
5. **`_spares` 规范值缓存上限 4096**：全异色写满会触发清空；清空只影响对象复用，不影响行内容。
6. **dirty 行身份**：`surface()` 只重建 dirty 行的 `Line`，其余行返回原对象；`render()` 在尺寸完全匹配时直接返回缓存 `Surface`（冻结值，安全共享）。
7. **`max_height` 只裁返回值**：Canvas/Sparkline 的缓存不乘预算；FILL 预算变化不会 thrash 行缓存（Section 的 key 会含 max_height，故 FILL section 每次预算变化会重渲染，符合预期）。
8. **`App.fill` 不清理旧组件的 focus/`_components`**：`Pane.fill` 清 document 时 App 不知道被移除的 section；若对已用 pane 调 `App.fill`，旧 widget 可能仍在焦点环。演示/游戏场景是全新 pane，本波按工单只做挂载复用；W4 Workspace 收口时一并处理。
9. **W2a 临时适配器仍在**：工单目标是“仍不删 int 兼容”，测试替身还写 `render(width)`；桥在 `kernel/document.py:_render_component`，W2c2/W4 删除。
10. **`tests/test_invariants.py` 在 T1 提交**（补 Canvas/Sparkline 用例），否则 T1 提交后矩阵完整性测试会红；T5 又在同一文件改名 ScrollPanel。
11. **`tools/api-2.0.txt` 更新三次**（Canvas 新增、Section 签名、ScrollPanel 改名），acceptance 7 允许 `api --update`。
12. **snake 的 headless 局**：首局第 19 步撞右墙（score 0）；这是真实结束的一局，不是裁掉逻辑。live 模式用 `App.fill` + `every(0.12)` + 方向键。
13. **Canvas 只 import kernel 与 `.base`**，无 terminal/app；每行由 `Surface.clipped` 保证 ≤ width。

## C. 位置与 commit

- 源码：`widgets/canvas.py`（Canvas 64、Sparkline 596）、`kernel/document.py`（Placement/Sizing/Fill、Section 361、Document.add 750）、`kernel/layout.py`（`_layout_with_fill` 646）、`kernel/frame.py:384`（Pane.add/fill）、`app/driver.py:402`（TUI.add/fill）、`app/application.py:347`（App.add/fill/_mount）、`widgets/scroll.py:53`。
- 测试：`tests/widgets/test_canvas.py`、`tests/kernel/test_{document,layout}.py`、`tests/app/test_{driver,app}.py`、`tests/widgets/test_scroll.py`、`tests/test_invariants.py`、`tests/test_examples.py`。
- commit：
  - `aa035de` canvas: draw into a mutable cell grid and render a surface
  - `83e1ac0` canvas: coalesce packed rows in one pass and repair wide clusters
  - `da3cbff` document: place sections and give the last flow section a fill
  - `48c6a5c` layout: give the last flow section the residual viewport height
  - `bf92acc` app: fill a pane from the driver and the application
  - `2517a85` widgets: replace the scroll view with a vertical scroll panel
  - `d15bc1b` examples: play a headless snake game on a canvas fill
  - 本文件（最后一个 commit）
