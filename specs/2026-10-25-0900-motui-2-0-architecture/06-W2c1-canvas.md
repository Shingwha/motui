# W2c1 · Canvas + Fill/Sizing + ScrollPanel + snake

> 分支 `2.0/w2c1-canvas`；前置：W2b 已合并 + lead seam fix（`6fdb8a4`）；写入范围：`src/motui/widgets/canvas.py`、`src/motui/kernel/{cell,document,layout}.py`、`src/motui/widgets/{scroll,__init__}.py`、`src/motui/{__init__,app/driver.py,app/application.py}`、`examples/**`、对应 `tests/**`
> 权威：`ref/source/10-waves/W2-render-contract.md` §4.3–4.5、`06-widgets.md` §9、`02-core-contracts.md` §5

## 目标

补齐 W2 的能力面（仍不删 int 兼容）：

1. `Canvas` + `Marker(cell/half/braille)` + `Sparkline`：可变 cell 栅格，只产 `Surface`，不写 escape；
2. `Placement` / `Sizing` / `Fill`：`Document` 至多一个 FILL、在所有 FLOW 之后；FILL 吃掉剩余高度；
3. `ScrollPanel` 取代 `ScrollView`（本波只跑 y，保留 `axis` 参数）；
4. `examples/snake.py` headless 可跑完一局；
5. 测试与导出更新。

**本波结束：全量 pytest 绿；57 golden 逐字节不变；hash 不变；Canvas 80×24 全异色 ≤2.0ms、单色 ≤0.4ms；FILL 填满 pane。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2a-surface.md` → `handoff/W2b1-views.md` → `handoff/W2b2-content.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1078 passed）；`golden --check`（57）；`framebench`（hash a82f7968…）。
- 稳定区（勿改行为）：`kernel/{frame,hit,overlay,selection,style,glyphs,theme,text,events,keymap}.py`、`terminal/**`、`app/{application,focus,pointer,gesture,modal,find,overlays,scrollbar,command_palette}.py`（只允许 add/fill 代理）、`widgets/base.py`、未点名 widgets、`tests/golden/**`、`tools/**`。
- 已定设计：
  - `Section` 增加 `placement: Placement` 与 `sizing: Sizing`，保留 `component`/`pin` 兼容；`widget` 属性是 `component` 的别名。
  - `Document.add(..., pin=None, placement=FLOW, sizing=NATURAL)`：`pin` 与 `placement` 二选一；FILL 只能 FLOW；至多一个 FILL；FILL 之后不能再加 FLOW；TOP/BOTTOM 只能 NATURAL，违反抛 `ValueError`。
  - `Viewport.layout` 遇到 FILL：flow 段按自然高度（受可用高度限制）渲染/滚动，FILL 拿 `available - flow_visible` 的高度；不用 `_BodyIndex` 的 body 路径（flow 直接遍历 section）。FILL 行进入 `row_blocks`（id + 行号）。
  - `Fill(widget)` 是公开值（冻结 dataclass），本波 `Pane.fill` 用“清空文档 + 加 FILL section”实现；真正的 `PaneContent = Document | Fill` 联合留 W4，记录偏差。
  - `ScrollPanel(child, height=None, offset=0, bar=False, axis="y", ...)`；`axis != "y"` 抛 `ValueError`（W2.6 加 x/both）。`ScrollView` 删除，更新所有引用。
  - `Canvas` 只 import `kernel`；`render(c: Constraints | int) -> Surface`；`surface()` 返回缓存 Surface。
- 已知坑：
  - `_BodyIndex` 的 key 是 `(Document.mutation, width)`；FILL 文档不要走它，避免污染。
  - `ScreenLayout` 的 `rows` 必须恰好 height；FILL 预算不足时截断/补空行。
  - `TUI.add` 当前返回 id；保持 id（W4 改 Section）。新增 `TUI.fill -> Section`。
  - `App.add` 会做 theme/focus 遍历；`App.fill` 也要走同样的挂载逻辑（可以复用 `add` 的挂载部分）。
  - 20 列裁剪/Painter 安全网已在 W2a；Canvas 必须自己保证每行 ≤ width。
  - 性能测试用 `time.perf_counter` 中位数，先 warmup；阈值按规格，若 CI 抖动大，用 `--benchmark` 标记并在 handoff 记录实测。

## 工单（每项一个 commit）

### T1 `Canvas` + `Marker` + `Sparkline`

- 新建 `src/motui/widgets/canvas.py`：
  ```python
  class Canvas(Widget):
      def __init__(self, width: int = 0, height: int = 0, *, marker: str = "cell", ...)
      def put(self, x: int, y: int, char: str, style: Style = NONE) -> None
      def text(self, x: int, y: int, text: str, style: Style = NONE) -> None
      def hline(self, x: int, y: int, length: int, char: str = "─", style: Style = NONE) -> None
      def vline(self, x: int, y: int, length: int, char: str = "│", style: Style = NONE) -> None
      def box(self, x: int, y: int, width: int, height: int, *, border=None, style: Style = NONE) -> None
      def blit(self, other: "Canvas", x: int, y: int) -> None
      def plot(self, points, *, marker: str | None = None, style: Style = NONE) -> None
      def clear(self) -> None
      def surface(self) -> Surface
      def render(self, c: Constraints | int) -> Surface
  class Sparkline:
      def __init__(self, values=(), *, marker="half", style=Style(), glyphs=...)
      def render(self, c: Constraints | int) -> Surface
  ```
- 内部：`list[list[Cell]]`，`dirty: set[int]`，每行缓存 `Line`；`surface()` 只重建 dirty 行（用 `fuse` 合并同样式 cell）。`put` 越界忽略/裁剪（写进 docstring）；宽字符占 2 列（第二列空 char）。
- `Marker`：
  - `"cell"`: 每个点一个 `█`（或 `glyphs.bar_full`）。
  - `"half"`: 2 个纵向点/格：`▀`（上）、`▄`（下）、`█`（both）。
  - `"braille"`: 2×4 点/格，用 U+2800..U+28FF 的 8 点映射（给出映射表与测试）。
  - `plot(points, marker=...)` 接受 `(x, y)` 浮点/整数序列，按 canvas 高度归一化到 marker 的分辨率；空序列无操作。
- `Canvas.render(c)`：`c.width`/`c.max_height` 决定可视区域；若 canvas 尺寸更大，裁到矩形；返回 `Surface.clipped`（不 pad），每行 ≤ width。
- `Canvas` 不得 import `terminal`/`app`；`ruff` import-linter 会验。
- 测试 `tests/widgets/test_canvas.py`：
  - put/text/hline/vline/box/blit 的坐标与裁剪；
  - cell/half/braille 的已知点位（小画布逐格断言）；
  - 宽字符占 2 列；
  - dirty 行：只改一行时其他行 Line 对象不变（`is` 断言）；
  - 性能：80×24 全异色循环写满后 `surface()` 中位数 ≤2.0ms；单色 ≤0.4ms（预热 3 次，取 5 次中位数；打印实测值）。
- 只允许改：`widgets/canvas.py`、`widgets/__init__.py`（导出 Canvas/Sparkline）、`tests/widgets/test_canvas.py`。
- 验证：`uv run pytest -q tests/widgets/test_canvas.py`。

### T2 `Placement` / `Sizing` / `Fill` 与 Document 校验

- `kernel/document.py`：
  - `class Placement(Enum): FLOW/TOP/BOTTOM`；`class Sizing(Enum): NATURAL/FILL`。
  - `@dataclass(frozen=True) class Fill: widget: Component`（公开值；本波仅作 API/后续 pane 内容形态）。
  - `Section.__init__(id, component, *, pin=None, placement=None, sizing=NATURAL)`：
    - `pin`/`placement` 二选一（都不给 = FLOW）；映射到 `_pin` 兼容；
    - `placement`/`sizing` 属性；`widget` 属性 = `component`；
    - `sizing` 必须 `Sizing`；`placement` 必须 `Placement`；否则 `ValueError`。
  - `Document.add(component, *, id=None, pin=None, placement=Placement.FLOW, sizing=Sizing.NATURAL) -> Section`：
    - 校验：`sizing=FILL` 只能 `placement=FLOW`；至多一个 FILL；一旦有 FILL，后续 FLOW 抛 `ValueError`；TOP/BOTTOM 只能 NATURAL。
  - `Document.fills()` / `Document.fill()` 辅助（返回 FILL section 或 None）。
- 测试 `tests/kernel/test_document.py`：合法/非法组合、至多一个 FILL、FILL 后加 FLOW 报错、返回 Section 的 `widget/placement/sizing`。
- 只允许改：`kernel/document.py`、`tests/kernel/test_document.py`。
- 验证：`uv run pytest -q tests/kernel/test_document.py`。

### T3 `Viewport` 的 FILL 路径

- `kernel/layout.py` `Viewport.layout`：
  - 无 FILL：保持现有 `_BodyIndex` 路径。
  - 有 FILL：
    - top/bottom 仍按 `pin` 先渲染；
    - `available = max(0, height - len(top_kept) - len(bottom_kept))`；
    - flow sections = placement FLOW 且非 FILL；`flow_natural = sum(section.row_count(Constraints(width=width)))`；
    - `flow_visible = min(available, flow_natural)`；按现有 `ScrollState` 规则 clamp/slice flow rows（offset 基于 flow）；
    - `fill_budget = available - flow_visible`；`fill_rows = fill_section.rows(Constraints(width=width, max_height=fill_budget))`；截断/补空到 `fill_budget`；
    - `body_rows = flow_rows + fill_rows`；`row_blocks` 对应；`total_rows = flow_natural`（FILL 不滚动）；
    - 返回 `ScreenLayout` 仍是 height 行。
  - 不要改变无 FILL 文档的任何 offset/行归属。
- 测试 `tests/kernel/test_layout.py`：flow+fill、fill 预算 0、top/bottom + fill、fill 行归属、无 FILL 路径字节不变（用现有断言）。
- 只允许改：`kernel/layout.py`、`tests/kernel/test_layout.py`。
- 验证：`uv run pytest -q tests/kernel/test_layout.py`。

### T4 `Pane.fill` / `TUI.fill` / `App.fill`

- `kernel/frame.py` `Pane.fill(component) -> Section`：清空该 pane 的 document（逐个 remove），`document.add(component, sizing=Sizing.FILL)`；返回 Section。
- `app/driver.py` `TUI.fill(component, *, pane=None) -> Section`：选内容 pane，调 `Pane.fill`，`refresh()`。
- `app/application.py` `App.fill(component, *, pane=None) -> Section`：调 `TUI.fill`，并执行与 `App.add` 相同的 theme/focus 挂载（抽一个私有 `_mount(component)` 复用，避免复制）。
- `TUI.add`/`App.add` 增加 `placement=None`、`sizing=Sizing.NATURAL` 参数并透传；`pin` 保留。
- 测试 `tests/app/test_driver.py` / `tests/app/test_app.py`：fill 后 `screen` 占用 pane 剩余高度；flow+fill；App.fill 挂 theme/focus。
- 只允许改：`kernel/frame.py`、`app/driver.py`、`app/application.py`、`tests/app/test_driver.py`、`tests/app/test_app.py`。
- 验证：`uv run pytest -q tests/app/test_driver.py tests/app/test_app.py`。

### T5 `ScrollPanel` 取代 `ScrollView`

- `widgets/scroll.py`：`class ScrollPanel(Widget)`，构造 `(child, *, height=None, offset=0, bar=False, axis="y", glyphs=GLYPHS, theme=None, styles=None)`；`axis != "y"` 抛 `ValueError`（W2.6 加 x/both）。内部逻辑不变。
- 删除 `ScrollView`（不留 alias）；更新 `widgets/__init__.py`、`src/motui/__init__.py`、`tests/widgets/test_scroll.py`、`tests/test_invariants.py`、任何引用（`grep ScrollView`）。
- 测试：现有 ScrollView 用例改名为 ScrollPanel；加 `axis="x"` 抛 ValueError 的用例。
- 只允许改：`widgets/scroll.py`、`widgets/__init__.py`、`src/motui/__init__.py`、`tests/widgets/test_scroll.py`、`tests/test_invariants.py`。
- 验证：`uv run pytest -q tests/widgets/test_scroll.py tests/test_invariants.py`。

### T6 `examples/snake.py`

- 新建 `examples/snake.py`（≤120 行）：
  - 一个 `Snake` 组件（`Canvas` + `Fill`），`step()` 移动蛇、吃食物、撞墙/撞自己结束；
  - `main(headless: bool = False)`：headless 模式创建 `headless_tui(40, 20)`，`tui.fill(game)`，手动 `step()` + `paint()` 跑 N 步（不 sleep），最后打印/断言；
  - 可执行：`uv run python examples/snake.py --headless` exit 0，输出一局结果。
- 新增 `tests/test_examples.py`：用 `subprocess.run([sys.executable, "examples/snake.py", "--headless"], cwd=ROOT)` 断言 exit 0 且输出包含 "score"。
- 只允许改：`examples/**`、`tests/test_examples.py`。
- 验证：`uv run python examples/snake.py --headless`；`uv run pytest -q tests/test_examples.py`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `uv run python tools/golden.py --check` → 57 match；`framebench` hash 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. Canvas 性能实测值贴出；阈值满足。
5. FILL：flow+fill、top/bottom+fill、fill 预算 0 测试通过。
6. `uv run python examples/snake.py --headless` exit 0。
7. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿（Canvas 新增公开面需 `api --update`）。

## 禁触清单

`kernel/{frame,hit,overlay,selection,style,glyphs,theme,text,events,keymap}.py`（`frame.py` 的 `Pane.fill` 除外）、`terminal/**`、`app/{focus,pointer,gesture,modal,find,overlays,scrollbar,command_palette}.py`、`widgets/base.py`、未点名 widgets、`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W2c1-canvas.md`：A 节给 Canvas/Fill/ScrollPanel 的实际签名、性能数字、门禁；B 节写偏差（Fill 作为 Section sizing 而非 PaneContent、ScrollPanel 仍用 ScrollState、axis 只 y）、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W2b 适配器是否被验证）/ 探索审计 / 未决问题。
