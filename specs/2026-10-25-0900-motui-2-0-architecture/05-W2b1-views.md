# W2b1 · 数据视图族迁移到 Surface

> 分支 `2.0/w2b1-views`；前置：W2a 已合并（`fddbf93`）；写入范围：`src/motui/widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py`、对应 `tests/widgets/*`
> 权威：`ref/source/10-waves/W2-render-contract.md` §4.2、`02-core-contracts.md` §2、`06-widgets.md`

## 目标

把数据视图族从 `render(width) -> list[Line]` 迁到 `render(Constraints) -> Surface`，**视觉与行为零变化**：

- `List` / `Tree` / `Table` / `Select`/`MultiSelect`/`CheckboxGroup`/`RadioGroup` / `NavList` / `Tabs` / `MenuBar`/`ContextMenu` / `Notice`/`ShortcutBar`/`StatusLine` / `ScrollView` / `strip` 的 cursor 组件；
- 每个 `render` 收 `Constraints | int`（`as_constraints` 归一），返回 `Surface.clipped(rows, c.width)`，按 `c.max_height` 截断；
- 保持 memo/revision/child_at/滚动/窗口/cursor 几何不变；
- 子组件仍用 `child.render(int)`（旧/新都兼容）。

**本波结束：全量 pytest 绿；57 golden 逐字节不变；hash 不变；这些文件无 `def render(self, width`。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2a-surface.md` → 本工单。
- 基线（开工先跑，贴真实输出）：`uv sync --locked`；`uv run pytest -q -p no:cacheprovider`（1045 passed）；`golden --check`（57）；`framebench`（hash a82f7968…）。
- 稳定区（勿改）：`kernel/**`、`terminal/**`、`app/**`、`demo/**`、`widgets/{text,layout,decor}.py`、`widgets/base.py`、未点名的 widgets、`tests/golden/**`、`tools/**`、`pyproject.toml`。
- 迁移模式（照抄 W2a）：
  ```python
  from ..kernel.layout import as_constraints
  from ..kernel.cell import Surface

  def render(self, c: Constraints | int) -> Surface:
      c = as_constraints(c)
      rows = [...]  # 原逻辑，width 用 c.width
      if c.max_height is not None:
          rows = rows[: c.max_height]
      self._rows = rows  # 原有几何表保持
      return Surface.clipped(rows, c.width)
  ```
- 已知坑：
  - 这些组件很多有 `_memo`/`_rows`/`_cells` 几何表；返回 Surface 后仍要保留，`click`/`child_at` 读它们。
  - `Table` 的 `render` 有多段（表头/主体/边框）；只换外层签名与返回，内部行构造不动。
  - `ScrollView` 本波只换签名；横向/ScrollPanel 在 W2.6。
  - `strip.py` 的 `ClampedCursor` 本波不删（W3）。
  - 测试里 `render(width)` 继续可用（int 被接受），**不要**为了让类型好看把测试全改成 Constraints（W2c 统一 codemod）。
- 只改渲染签名/返回与 max_height 截断；不改窗口尺寸、游标、选择、滚动、按键。

## 工单（每族一个 commit）

### T1 `list.py` / `choice.py`（List / Select / MultiSelect / CheckboxGroup / RadioGroup）
- 迁移 `render`；保留 window/cursor 逻辑；`max_height` 截断。
- 测试：`tests/widgets/test_choice.py`、`tests/widgets/test_data.py` 各加一个 Constraints + max_height 用例。
- 验证：`uv run pytest -q tests/widgets/test_choice.py tests/widgets/test_data.py`。

### T2 `tree.py` / `navlist.py`（Tree / NavList）
- 迁移 `render`；保留展开/游标/rail。
- 测试：`tests/widgets/test_navigation.py` 加 Constraints 用例。
- 验证：`uv run pytest -q tests/widgets/test_navigation.py`。

### T3 `table.py`（Table）
- 迁移 `render`；表头/主体/边框逻辑不变；`max_height` 截断。
- 测试：`tests/widgets/test_data.py` 加 Constraints/max_height。
- 验证：`uv run pytest -q tests/widgets/test_data.py`。

### T4 `tabs.py` / `menubar.py`（Tabs / MenuBar / ContextMenu）
- 迁移 `render`；保留选中/展开/宽度预算。
- 测试：`tests/widgets/test_menubar.py`、`tests/widgets/test_navigation.py` 加 Constraints 用例。
- 验证：`uv run pytest -q tests/widgets/test_menubar.py tests/widgets/test_navigation.py`。

### T5 `rows.py` / `strip.py`（Notice / ShortcutBar / StatusLine / strip 基座）
- 迁移 `render`；保留左右对齐/两列/游标。
- 测试：`tests/widgets/test_rows.py` 加 Constraints 用例。
- 验证：`uv run pytest -q tests/widgets/test_rows.py`。

### T6 `scroll.py`（ScrollView）
- 迁移 `render`；保留 height/viewport/bar 逻辑；`max_height` 与 `height` 的优先级保持现状（显式 height 优先）。
- 测试：`tests/widgets/test_scroll.py` 加 Constraints 用例。
- 验证：`uv run pytest -q tests/widgets/test_scroll.py`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `uv run python tools/golden.py --check` → 57 match；`framebench` hash 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `grep -rn "def render(self, width" src/motui/widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py` 为空。
5. `ruff check .` / `pyright` / `lint-imports` 全 0；`tools/api.py --check` 通过；`growth.py --quick` 通过。

## 禁触清单

`kernel/**`、`terminal/**`、`app/**`、`demo/**`、`widgets/{text,layout,decor,base,action,collapsible,combobox,dialog,diff,form,indicators,textbuf,textfield,autocomplete,syntax}.py`、`widgets/markdown/**`、`widgets/__init__.py`、`tests/golden/**`、`tools/**`、`pyproject.toml`、`uv.lock`、`README.md`、`docs/**`。

## 交接包

最后 commit 写 `handoff/W2b1-views.md`：A 节给迁移清单/签名/门禁；B 节给偏差/坑/未迁移项；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W2a 适配器是否被验证）/ 探索审计 / 未决问题。
