# W2c2a · 渲染签名收口（只收 Constraints）

> 分支 `2.0/w2c2-signatures`；前置：W2c1 已合并（`25cb08c`）；写入范围：`src/motui/**`、`tests/**`、`examples/**`、`tools/api-2.0.txt`
> 权威：`ref/source/10-waves/W2-render-contract.md` §4.1–4.2、`02-core-contracts.md` §2

## 目标

把 W2a–W2c1 的过渡形态收口成 2.0 契约：

1. 所有组件只有一个渲染签名：`render(c: Constraints) -> Surface`；不再接受 `int`；
2. 删除 `Section` 的临时组件适配器（`_render_component` / `_render_takes_constraints` / `_as_constraints`）与 `as_constraints` 归一；
3. 全仓调用点（src/tests/examples）改为传 `Constraints`；
4. `Section.render/rows/rows_view/row_count` 只收 `Constraints`；
5. `Painter.paint` 接受 `Surface`（保留 `ScreenLayout` 兼容入口）；`ScreenLayout.surface` 提供 Surface 视图；
6. `CommandPalette.render(c) -> Surface`；
7. 全量门禁绿，视觉零变化。

**本波结束：1115+ 用例全绿；57 golden 逐字节不变；hash 不变；`grep "def render(self, width" src/motui` 为空；`grep "as_constraints" src/motui` 为空（或仅保留无调用者的私有 helper 并说明）。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2a-surface.md` → `handoff/W2b1-views.md` → `handoff/W2b2-content.md` → `handoff/W2c1-canvas.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1115 passed）；`golden --check`（57）；`framebench`（hash a82f7968…）。
- 稳定区（行为勿改）：渲染算法、滚动、游标、编辑、markdown、高亮、焦点、demo 页面；本波只改签名/调用形态。
- 迁移事实：
  - 所有组件当前签名是 `render(self, c: Constraints | int)` 或 `render(self, width: int)`（W2a 前未迁移的已由 W2b 全迁）。
  - 组件内部第一行多为 `c = as_constraints(c)`；返回 `Surface.clipped(rows, c.width)`。
  - `Section._render_component` 目前按参数名判断新旧；所有组件迁移后可以删除。
  - `Painter.paint(layout: ScreenLayout)` 仍用 `layout.rows`；`ScreenLayout` 有 `width/height/rows`。
  - `CommandPalette.render(width) -> list[Line]`，内部 `[*input.render(width), *list.render(width)]`。
  - 测试有 306 处 `.render(...)`；src 约 30 处；examples 少量。
- 已知坑：
  - 不要盲替换 `render(...)`：`demo.render_topic`、`render_topic`、`Renderer` 等不是组件方法；只处理 `x.render(...)` / `self.render(...)` / `super().render(...)` 且参数是宽度表达式。
  - `Section.render` 返回 `list[Line]` 的便捷入口可以保留，但只收 `Constraints`；`Section.rows` 等同样。
  - `Viewport` 内部 `entry_rows/row_count` 的 `width` 参数要换成 `Constraints` 或以 `width` 构造一次 Constraints 复用。
  - `tests/testing/doubles.Rows` 是假组件，也要改 `render(c)`；`tests/app/test_command_palette.py` 的 `list(input.render(...))` 保持可用。
  - `demo/topics/{components_layout,interactions}.py` 有 demo-local `ScrollView` 子类（保 golden），本波不要改其行为/字符串。
  - `tools/growth.py` 会把 `Constraints` 加字段后跑测试，签名收口后仍应通过。
  - pyright 目前 basic；不要为了类型把行为改坏；必要时用精确注解。
  - ruff 的 ratchet 仍排除 widgets/app/demo；kernel/terminal/testing/tools 仍受检。新增 import 要排序。

## 工单（建议一个批次一个 commit）

### T1 组件签名收口

- 全仓 `src/motui` 的组件 `def render(self, c: Constraints | int)` → `def render(self, c: Constraints)`；删除 `c = as_constraints(c)` 行；保留 `c.width`/`c.max_height`。
- 未迁移的 `def render(self, width: int)`（若有）→ `def render(self, c: Constraints)`，内部用 `c.width`。
- `widgets/base.Widget.render` 同步改为 `render(self, c: Constraints) -> Surface`。
- `CommandPalette.render(c: Constraints) -> Surface`：内部 `[*self.input.render(c), *self.list.render(c)]`，返回 `Surface.clipped(rows, c.width)`。
- `Section.render/rows/rows_view/row_count/_refresh` 只收 `Constraints`；删除 `_render_takes_constraints`/`_render_component`/`_as_constraints`，直接 `component.render(c)` 并取 `.rows`。
- `kernel/layout.py`：删除公开 `as_constraints`（若仍有调用者，先全部改完）；`Viewport` 内部构造 `Constraints`。
- 验证：`grep -rn "Constraints | int\|as_constraints\|_render_takes_constraints\|_render_component" src/motui` 为空；`uv run pytest -q tests/kernel`。

### T2 src 调用点改 Constraints

- 用一次性 codemod（AST 或 tokenize，跑完删除）把 `src/motui` 中组件的 `.render(<宽度表达式>)` 改为 `.render(Constraints(width=<宽度表达式>))`；跳过已经是 `Constraints(...)` 的参数。
- 同步处理 `Section.rows/rows_view/row_count` 的宽度调用（若调用点传 int）。
- 重点文件：`app/{driver,application,command_palette,find,modal,overlays}.py`、`demo/{shell,stage}.py`、`widgets/**`（容器对子组件的调用）。
- 子组件调用如果当前传 `inner`/`width`，改成 `Constraints(width=inner)`；不要重复构造同一个 Constraints 多次时，可在循环外构造一次复用（行为不变）。
- 验证：`uv run pytest -q tests/app tests/widgets tests/kernel`；`python -m motui --pages > /dev/null`。

### T3 tests/examples 调用点改 Constraints

- 同上 codemod 处理 `tests/**`、`examples/**` 的 `.render(...)`、`.rows(...)`、`.rows_view(...)`、`.row_count(...)`。
- `tests/test_invariants.py` 的矩阵调用改为 `render(Constraints(width=width))`；`other` 同理。
- `tests/testing/doubles.Rows.render(c)`；`tests/testing/layout.py` 若构造假组件也改。
- `tests/app/test_command_palette.py` 的 `list(input.render(...))` 改 Constraints。
- 人工抽查：`grep -rn "\.render([0-9]" tests` 应为空；`grep -rn "\.render(width)" tests` 应为空。
- 验证：`uv run pytest -q -p no:cacheprovider` 全绿。

### T4 Painter 接受 Surface

- `kernel/layout.py` `ScreenLayout` 增加：
  ```python
  @property
  def surface(self) -> Surface:  # Surface.clipped(self.rows, self.width)
  ```
- `terminal/paint.py` `paint(self, target: ScreenLayout | Surface)`：
  - `Surface` → `rows = list(target.rows)`, `width = target.width`；
  - `ScreenLayout` → 现有路径；
  - 其余行为（diff、sync、anchor、裁剪）不变。
- `app/driver.py` 的 `_paint_at` 传 `layout.surface`（或保持 layout，但验收要求至少有一条 Surface 路径被真实使用；用 surface）。
- 测试 `tests/terminal/test_painter.py` 加 `Painter.paint(Surface)` 用例，字节与 ScreenLayout 路径一致。
- 验证：`uv run pytest -q tests/terminal/test_painter.py tests/app/test_driver.py`；golden/hash 不变。

### T5 收口与快照

- `tools/api.py --update`（签名变化：render、Section、CommandPalette、ScreenLayout.surface）。
- 确认 `tools/growth.py --quick` 通过。
- `grep -rn "def render(self, width" src/motui` 为空；`grep -rn "render(width" src/motui tests examples` 为空（文档字符串除外，报告列出）。
- 验证：全量验收。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `uv run python tools/golden.py --check` → 57 match；`framebench` hash 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. 签名 grep：无 `def render(self, width`、无 `Constraints | int`、无 `as_constraints`、无 `_render_takes_constraints`。
5. `Painter.paint(Surface)` 用例通过，且 `TUI` 走 Surface 路径。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。

## 禁触清单

`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`；不改变渲染/滚动/编辑/焦点算法。

## 交接包

最后 commit 写 `handoff/W2c2-signatures.md`：A 节给最终签名、Painter Surface 路径、门禁；B 节写 codemod 策略、漏网与手工修复、未决；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W2c1 事实）/ 探索审计 / 未决问题。
