# W2a · 渲染契约地基（Surface / Constraints / 裁剪）

> 分支 `2.0/w2a-surface`；前置：W1 已合并（`636917c`）；写入范围：`src/motui/kernel/{cell,document,layout}.py`、`src/motui/terminal/paint.py`、`src/motui/widgets/{text,layout,decor}.py`、`tests/kernel/**`、`tests/widgets/**`、`tests/terminal/test_painter.py`、`tests/test_invariants.py`、`tools/api-2.0.txt`
> 权威：`ref/source/10-waves/W2-render-contract.md` §1–4.1、`02-core-contracts.md` §2

## 目标

把渲染契约从 `render(width) -> list[Line]` 迁到 `render(Constraints) -> Surface` 的**地基**，并让裁剪不变量在 painter 前生效：

1. `Surface` 成为组件返回类型（可迭代、可比较、可哈希；行宽 ≤ width）；
2. `Constraints` 进入组件签名；迁移 `Text`、`Row/Column/Spacer/Padding`、`Divider/Panel`；
3. `Section`/`Viewport` 接受 `Constraints`，块缓存 key 加 `max_height`；
4. **20 列屏 + 40 列内容不再换行/破坏邻行**；
5. 未迁移组件通过临时适配器继续工作（W2b/W2c 收口）。

**本波结束：1019 个用例全绿；57 golden 逐字节不变；render-hash 不变；迁移的组件全部 `render(c|width) -> Surface`。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W1-kernel.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider     # 1019 passed
  uv run python tools/golden.py --check    # 57 topics match
  uv run python tools/framebench.py        # hash a82f7968…
  ```
- 稳定区（勿改行为）：`kernel/{frame,hit,overlay,selection,style,glyphs,theme,text,events,keymap}.py`、`terminal/{screen,render,ansi,capability}.py`、`widgets/base.py`、`widgets/{action,choice,list,tree,table,textfield,...}.py`、`app/**`、`demo/**`、`tests/golden/**`。
- 已知事实：
  - `Surface(width, rows)` 已有 `of(rows, width)`（clip+pad）、`blank(size)`、`height`；`Line.clip/pad/fill` 可用。
  - `Section.rows/rows_view/row_count/render` 当前收 `width: int`，缓存 key `(width, revision)`。
  - `Viewport.layout(width,height)` 通过 `_BodyIndex` 调 `Section` 的 rows 门；`Painter` 收到 `ScreenLayout`。
  - `Painter` 每行写 `CUP + CLEAR_LINE + styled_line(row)`；空行只清行。**不要**用 `Surface.of` 的补齐改变现有行的宽度，否则 golden 会变。
  - 迁移组件的 `_rows` 表（Text/Row/Column/Panel）用于 hit/child_at；返回 `Surface` 后仍要保留这些几何表。
- 已知坑：
  - `Surface` 必须可迭代（`for row in surface`、`len(surface)`、`surface[i]`），否则 `tests/test_invariants.py` 的现有矩阵要全改；本波先加迭代协议，W2c 再决定是否清理。
  - 旧组件仍返回 `list[Line]` 且只收 `int`；`Section` 需要临时适配器（按 `render` 参数名/注解判断），W2c 删除。
  - 迁移组件的 `render` 允许 `Constraints | int`（`as_constraints` 归一），这样现有测试的 `component.render(width)` 继续可用；W2c 收窄为只收 `Constraints`。
  - 不要用 `Surface.of` 的默认 pad 直接返回；本波用 `Surface.of(rows, width, pad=False)`（或 `Surface.clipped`）保持字节不变。pad 的调用留给 W2c。
  - `Painter` 的安全裁剪用 `cut_line(row, 0, width)`（硬裁、不加省略号）。

## 工单（按序执行，每项一个 commit）

### T1 `Surface` 迭代协议 + `as_constraints`

- `kernel/cell.py`：
  - `Surface` 增加 `__iter__`（遍历 `rows`）、`__len__`（`height`）、`__getitem__`（索引/切片返回 `Line`/tuple）。
  - `Surface.of(rows, width, *, pad: bool = True)`：`pad=True` 时 clip+pad（现行为）；`pad=False` 时只 `clip`，短行保持原宽。默认保持 `True`（契约）。
  - 增加 `Surface.clipped(rows, width)` 类方法（= `of(..., pad=False)`）供迁移组件用。
  - `Surface` 的 `__post_init__` 仍只校验 width；不强制 rows 已合法（`of`/`clipped` 是构造入口；直接构造是给内部/测试的逃生口）。
- `kernel/layout.py`：
  ```python
  def as_constraints(value: Constraints | int) -> Constraints
  ```
  `int` → `Constraints(width=value)`；`Constraints` 原样返回；负数抛 `ValueError`。
- 测试 `tests/kernel/test_surface.py`：迭代/len/索引；`of` pad True/False；`clipped` 不改短行；`as_constraints` 两态。
- 只允许改：`kernel/cell.py`、`kernel/layout.py`、`tests/kernel/test_surface.py`、`tests/kernel/test_scroll_values.py`（导出检查）。
- 验证：`uv run pytest -q tests/kernel/test_surface.py tests/kernel/test_scroll_values.py`。

### T2 `Component`/`Section`/`Viewport` 接 Constraints

- `kernel/document.py`：
  - `Component` Protocol 改为：
    ```python
    def render(self, c: Constraints) -> Surface: ...
    ```
  - `Section.render/rows/rows_view/row_count/_refresh` 接受 `Constraints | int`；`_refresh` 归一为 `Constraints`，缓存 key `(width, max_height, revision)`。
  - 新增模块私有 `_render_component(component, c) -> Surface`：
    - 用 `inspect.signature(type(component).render)`（按类缓存）判断第二个参数名是否为 `c`/`constraints` 或注解为 `Constraints`；
    - 是 → 调 `component.render(c)`，结果为 `Surface` 或 rows（容错）；
    - 否 → 调 `component.render(c.width)`，rows 用 `Surface.clipped(rows, c.width)` 包。
    - 明确注释：这是 W2b/W2c 的临时桥，W2c 删除。
  - `Section.render(width)` 保留为便捷入口（内部调 `rows`），不加入 Protocol。
- `kernel/layout.py`：
  - `Viewport.layout(width, height)` 内部构造 `Constraints(width=width, max_height=None)`；`_BodyIndex.ensure(width)` 改为 `ensure(c: Constraints)` 或保留 width 并让 rows 调用收 `Constraints`；`entry_rows(block, c)`、`row_count(c)` 相应改。
  - `natural_height(width)` 用 `Constraints(width=width)`。
  - **不要**改滚动算法/offset/行归属；只换调用形态。
- 测试：`tests/kernel/test_document.py`、`tests/kernel/test_layout.py` 增加 `Constraints` 路径（现有 int 路径保持）。
- 只允许改：`kernel/document.py`、`kernel/layout.py`、`tests/kernel/test_document.py`、`tests/kernel/test_layout.py`。
- 验证：`uv run pytest -q tests/kernel/test_document.py tests/kernel/test_layout.py`。

### T3 Painter 安全裁剪

- `terminal/paint.py`：在 `paint()` 归一化 rows 后、写字节前，对每一行 `if row.width > width: row = cut_line(row, 0, width)`。导入 `cut_line` from `..kernel.cell`。
- 新增 `tests/terminal/test_painter.py` 用例：
  - 20 列 headless 屏 + 一个返回 40 列 `Line` 的假 layout → 输出字节中不出现换行（无 `\n`），且 `painter.rows` 每行宽度 ≤20；
  - 邻行不被覆盖（写两行，第二行仍正确）。
- 只允许改：`terminal/paint.py`、`tests/terminal/test_painter.py`。
- 验证：`uv run pytest -q tests/terminal/test_painter.py`。

### T4 迁移 `Text`

- `widgets/text.py`：
  - `render(self, c: Constraints | int) -> Surface`；`c = as_constraints(c)`；`rows = self._rows_for(c.width)`；若 `c.max_height is not None` 截断；`self._rows = rows`；hover 变换不变；返回 `Surface.clipped(rows, c.width)`。
  - `_rows_for` 仍收 int（内部 seam 不变）。
  - `revision()` 不变。
- 测试 `tests/widgets/test_rows.py` / `tests/test_invariants.py` 继续传 int（`as_constraints` 接受）；新增 `Constraints(width=..., max_height=...)` 路径。
- 只允许改：`widgets/text.py`、`tests/widgets/test_rows.py`、`tests/test_invariants.py`（只加 Text 的 Constraints 用例）。
- 验证：`uv run pytest -q tests/widgets/test_rows.py tests/test_invariants.py`。

### T5 迁移 `Row` / `Column` / `Spacer` / `Padding`

- `widgets/layout.py`：
  - 四个类的 `render` 改为 `render(c: Constraints | int) -> Surface`；`c = as_constraints(c)`。
  - 子组件调用保持 `child.render(inner_width)`（子组件可能是旧/新；新组件接受 int）。**不要**在这一波把子调用改成 Constraints（避免双重适配）。
  - `Row`/`Column` 的输出行 `fit(width)` 后返回 `Surface.clipped(rows, width)`；`max_height` 截断最终 rows。
  - `Padding` 的顶部/底部空白、fill 合并、memo 键保持现状；返回 `Surface.clipped(rows, width)`。
  - `Spacer` 返回 `Surface.clipped([Line()...], width)`。
  - `child_at`/memo/revision 不变。
- 测试：`tests/widgets/test_containers.py` 增加 Constraints/max_height 用例；现有 int 路径保持。
- 只允许改：`widgets/layout.py`、`tests/widgets/test_containers.py`。
- 验证：`uv run pytest -q tests/widgets/test_containers.py`。

### T6 迁移 `Divider` / `Panel`

- `widgets/decor.py`：`Divider.render`/`Panel.render` 改 `render(c: Constraints | int) -> Surface`；`c = as_constraints(c)`；子组件仍收 int；返回 `Surface.clipped(rows, c.width)`；`max_height` 截断；memo/revision/child_at 不变。
- 测试：`tests/widgets/test_containers.py` 或 `tests/widgets/test_rows.py` 增加 Divider/Panel 的 Constraints 用例。
- 只允许改：`widgets/decor.py`、对应测试。
- 验证：`uv run pytest -q tests/widgets/test_containers.py tests/widgets/test_rows.py`。

### T7 20 列裁剪回归 + 文档收口

- 新增 `tests/kernel/test_render_contract.py`：
  - 一个 `Oversized` 组件返回 40 列 `Line`，挂进 `Document`，用 `headless_tui(width=20, height=6)` 渲染；
  - 断言 `tui.rows()` 每行 `width <= 20`；`Emulator(20,6)` 喂 `screen.output` 后第 0/1 行不出现 40 个 A 的自动换行错位；
  - 断言 `Section.rows(Constraints(width=20))` 每行 ≤20。
- `ref/interfaces.md` 由 lead 更新（你不需要改 spec；在 handoff 里写）。
- 只允许改：`tests/kernel/test_render_contract.py`、`tools/api-2.0.txt`（`uv run python tools/api.py --update`）。
- 验证：`uv run pytest -q tests/kernel/test_render_contract.py`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴真实数字）。
2. `uv run python tools/golden.py --check` → `57 topics match`；`framebench` hash `a82f7968…` 不变。
3. `uv run python -m motui < /dev/null` / `--pages` exit 0（70 / 4059 行）。
4. `grep -rn "def render(self, width" src/motui/widgets/{text,layout,decor}.py` 为空；三文件返回 `Surface`。
5. 20 列回归测试通过；`tui.rows()` 全部 ≤20。
6. `uv run ruff check .`、`uv run pyright`、`uv run lint-imports` 全 0。
7. `uv run python tools/api.py --check` 通过（快照已更新）。
8. `uv run python tools/growth.py --quick` 通过。

## 禁触清单

`kernel/{frame,hit,overlay,selection,style,glyphs,theme,text,events,keymap}.py`、`terminal/{screen,render,ansi,capability,decoder,keys,win32,clipboard}.py`、`widgets/base.py`、其余未点名的 widgets、`app/**`、`demo/**`、`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `specs/2026-10-25-0900-motui-2-0-architecture/handoff/W2a-surface.md`：A 节给新签名、Section 适配器规则、门禁真实结果；B 节写偏差（`Surface.of(pad=False)`、临时桥、未迁移清单）、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W1 哪些事实被验证）/ 探索审计 / 未决问题。
