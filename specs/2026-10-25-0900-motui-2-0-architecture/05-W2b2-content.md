# W2b2 · 编辑/内容族迁移到 Surface

> 分支 `2.0/w2b2-content`；前置：W2a 已合并（`fddbf93`）；写入范围：`src/motui/widgets/{action,collapsible,combobox,dialog,diff,form,indicators,textbuf,textfield,autocomplete,syntax}.py`、`src/motui/widgets/markdown/**`、对应 `tests/widgets/*`
> 权威：`ref/source/10-waves/W2-render-contract.md` §4.2、`02-core-contracts.md` §2、`06-widgets.md`

## 目标

把编辑/内容族从 `render(width) -> list[Line]` 迁到 `render(Constraints) -> Surface`，**视觉与行为零变化**：

- `Button` / `Checkbox` / `Link`；`Collapsible`；`ComboBox`；`Dialog`；`Diff`；`Form`；`ProgressBar` / `Slider` / `Spinner`；`TextBuffer` / `Input` / `Editor`；`Autocomplete`；`Syntax`（`Highlighter` 的行渲染）；`Markdown`（component/blocks/inline/nested/tables）；
- 每个 `render` 收 `Constraints | int`（`as_constraints` 归一），返回 `Surface.clipped(rows, c.width)`，按 `c.max_height` 截断；
- 保持 memo/revision/child_at/编辑几何/语法高亮/markdown 规则不变；
- 子组件仍用 `child.render(int)`（旧/新都兼容）。

**本波结束：全量 pytest 绿；57 golden 逐字节不变；hash 不变；这些文件无 `def render(self, width`。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2a-surface.md` → 本工单。
- 基线（开工先跑，贴真实输出）：`uv sync --locked`；`uv run pytest -q -p no:cacheprovider`（1045 passed）；`golden --check`（57）；`framebench`（hash a82f7968…）。
- 稳定区（勿改）：`kernel/**`、`terminal/**`、`app/**`、`demo/**`、`widgets/{text,layout,decor,base,list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py`、`tests/golden/**`、`tools/**`、`pyproject.toml`。
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
  - `TextBuffer` 是编辑引擎，不是组件；只迁 `Input`/`Editor` 的 render，不要改 buffer 的 wrap/cursor 算法。
  - `Markdown` 的 render 在 `markdown/component.py`；`blocks/inline/nested/tables` 若也有 render/行装配，一并迁签名，但规则/解析不动。
  - `Dialog`/`Form` 有 child_at/字段路由；返回 Surface 后几何表保持。
  - `Diff` 的长行截断保持现状（W2.5 再改默认）。
  - `syntax.py` 只有 Highlighter/行渲染辅助，若有 `render` 就迁；没有则只更新返回 Surface 的调用链。
  - `Autocomplete`/`ComboBox` 可能委托 List/Input；子调用仍传 int。
  - 测试里 `render(width)` 继续可用（int 被接受），**不要**全改 Constraints（W2c 统一 codemod）。
- 只改渲染签名/返回与 max_height 截断；不改编辑/解析/高亮/弹层/焦点行为。

## 工单（每族一个 commit）

### T1 `action.py`（Button / Checkbox / Link）
- 迁移 `render`；保留 hover/focus/checked/link。
- 测试：`tests/widgets/test_action.py` 加 Constraints + max_height 用例。
- 验证：`uv run pytest -q tests/widgets/test_action.py`。

### T2 `collapsible.py` / `form.py` / `dialog.py`
- 迁移三个 render；保留折叠、字段路由、按钮布局、child_at。
- 测试：`tests/widgets/test_dialog.py`、`tests/widgets/test_form.py` 加 Constraints 用例。
- 验证：`uv run pytest -q tests/widgets/test_dialog.py tests/widgets/test_form.py`。

### T3 `textbuf.py` / `textfield.py`（Input / Editor）
- 只迁 `Input.render` / `Editor.render`；`TextBuffer` 的 wrap/cursor/mask 逻辑不动。
- 测试：`tests/widgets/test_editing.py` 加 Constraints + max_height。
- 验证：`uv run pytest -q tests/widgets/test_editing.py`。

### T4 `combobox.py` / `autocomplete.py`
- 迁移 render；保留过滤/下拉/委托。
- 测试：`tests/widgets/test_combobox.py`、`tests/widgets/test_autocomplete.py` 加 Constraints 用例。
- 验证：`uv run pytest -q tests/widgets/test_combobox.py tests/widgets/test_autocomplete.py`。

### T5 `indicators.py`（ProgressBar / Slider / Spinner）
- 迁移三个 render；保留比例/步进/帧。
- 测试：`tests/widgets/test_indicators.py` 加 Constraints。
- 验证：`uv run pytest -q tests/widgets/test_indicators.py`。

### T6 `diff.py` / `syntax.py`
- 迁移 render（Diff 的长行仍截断；Syntax 若有 render/helper 一并改）。
- 测试：`tests/widgets/test_diff.py`、`tests/widgets/test_syntax.py` 加 Constraints。
- 验证：`uv run pytest -q tests/widgets/test_diff.py tests/widgets/test_syntax.py`。

### T7 `markdown/**`
- 迁移 `component.py` 的 render；`blocks/inline/nested/tables` 中装配行/返回行的入口按需改 Surface（保持规则与渲染结果）。
- 测试：`tests/widgets/test_markdown.py` 加 Constraints + max_height。
- 验证：`uv run pytest -q tests/widgets/test_markdown.py`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `uv run python tools/golden.py --check` → 57 match；`framebench` hash 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `grep -rn "def render(self, width" src/motui/widgets/{action,collapsible,combobox,dialog,diff,form,indicators,textbuf,textfield,autocomplete,syntax}.py src/motui/widgets/markdown` 为空。
5. `ruff check .` / `pyright` / `lint-imports` 全 0；`tools/api.py --check` 通过；`growth.py --quick` 通过。

## 禁触清单

`kernel/**`、`terminal/**`、`app/**`、`demo/**`、`widgets/{text,layout,decor,base,list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py`、`widgets/__init__.py`、`tests/golden/**`、`tools/**`、`pyproject.toml`、`uv.lock`、`README.md`、`docs/**`。

## 交接包

最后 commit 写 `handoff/W2b2-content.md`：A 节给迁移清单/签名/门禁；B 节给偏差/坑/未迁移项；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W2a 适配器是否被验证）/ 探索审计 / 未决问题。
