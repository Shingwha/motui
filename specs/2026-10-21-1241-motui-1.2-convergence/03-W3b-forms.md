# W3b · forms 家族迁移（Widget / Styles）

> 分支 `refactor/1.2-w3b-forms`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w3b-forms`
> 前置：W3a 已合并（`4653802`）；写入范围见下；波末必须全量绿。

## 目标

把 forms 家族迁移到 W3a 的 `Widget`/`Styles` 模式：`Select`、`Autocomplete`、`RadioGroup`、`CheckboxGroup`、`ComboBox`、`Form`、`Input`、`Editor`。删除所有 `*_style` 与 `focused=` 参数，样式在 render 时解析；默认渲染/golden 逐字节不变。

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§2 W3a 实际交付 + §2 W3 冻结）
  3. `specs/2026-10-21-1241-motui-1.2-convergence/handoff/W3a-w3a-widget-base.md`
  4. 本工单
- 基线命令（开工先跑）：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
```

起点 **880 passed / 57 topics match**。
- 稳定区（勿重读/勿改）：`core/widget.py`、`widgets/action.py`（已迁移）、`core/scroll.py`、`core/cursor.py`、`core/block.py`、全部 golden、`docs/**`。
- 已知约束/坑（来自 W3a handoff）：
  - `Widget` 不继承 `Themed`；迁移控件时把基类改为 `Widget`，从 `__slots__` 删 `"theme"/"focused"/"hover"`。
  - `focused=` 参数删除后，在 `__init__` 里保留旧默认值：Input/Select/Editor 默认 `True`；RadioGroup/CheckboxGroup 默认 `False`。调用点传 `focused=` 的改成构造后赋值。
  - `revision()` 末尾加 `self.theme, self.styles`。
  - `Dialog`/`MenuBar` 本身不是本波目标；只更新它们对 forms 控件的构造点。
  - `app/find.py`/`app/command_palette.py` 直接构造 `Input`/`Autocomplete`，签名若变必须同步。
  - `ComboBox` 当前没有 style 参数，内部直接构造 `Input`/`Autocomplete`；如果两者新增 `styles`，ComboBox 可以选择接受 `styles` 并转发（保持参数 ≤10），但不得改变默认渲染。

## 工单（按序执行，每项一个 commit）

### T1 · Select / Autocomplete / RadioGroup / CheckboxGroup

- `widgets/choice.py`：
  - `Select` 基类 `Themed` -> `Widget`；`__slots__` 删 `theme/focused/hover` 与 `_row_styles/_label_style/_cursor_text_style/_description_style/_title_style/_disabled_style/_form_label_style/_dim` 等缓存槽。
  - 删除构造器 `focused`、`label_style`、`cursor_text_style`、`description_style`、`title_style`、`ground_style`、`disabled_style`；加 `styles: Styles | None = None`。
  - 样式映射（默认渲染不变）：
    - 光标文字：`group("content").accent`
    - 描述：`group("text").muted`
    - 普通标签/标题：`group("text").base`（默认 NONE）
    - disabled 文字/未聚焦 cursor 的 dim：`group("text").faint`
    - 行 band：`group("rows").band(...)`
    - 表单组标签：`group("text").base`
  - `focused` 默认保持 `True`（在 `__init__` 里 `self.focused = True`）。
  - `revision()` 加 `theme/styles`。
- `widgets/autocomplete.py`：删除 `label_style/cursor_text_style/description_style`，改为 `styles` 并转发给 `Select`。
- `widgets/choice.py` 的 `RadioGroup`/`CheckboxGroup`：
  - 删除 `label_style/active_style/hover_style/ground_style/disabled_style/focused`，改为 `styles`；
  - 表单 band 通过 `group("rows")`；标签 `group("text").base`；disabled `group("text").faint`；
  - `focused` 默认保持 `False`。
- **MultiSelect（优先尝试）**：
  - 把 `multi=True` / `marked=` 从 `Select` 拆成 `MultiSelect(Select)`；`Select` 只保留单选语义（`commit`/`window`/`wrap`/`title`/`max_rows`/`glyphs`/`disabled`/`disabled_items`/`theme`/`styles`）。
  - `MultiSelect` 提供 `marked` 与 `toggle()`，渲染/结果语义与旧 `Select(multi=True)` 逐字节一致。
  - 更新 demo/tests 的 `Select(..., multi=True, marked=...)` -> `MultiSelect(...)`；`widgets/__init__.py` 导出 `MultiSelect`。
  - **诚实出口**：若拆分需要改动超过 3 个测试文件或 golden 变化，保留 `multi/marked` 两个参数并在 handoff 记为 W6 遗留；不要为此拖垮本波。
- 允许改：`widgets/choice.py`、`widgets/autocomplete.py`、`widgets/__init__.py`、`demo/topics/components_forms.py`、`tests/widgets/test_choice.py`、`tests/widgets/test_autocomplete.py`、`tests/test_invariants.py`、`tests/interaction/test_pointer.py`、`tests/interaction/test_focus.py`、`tests/app/test_hit.py`。
- 验证：pytest + golden 不变。

### T2 · Input / Editor / ComboBox / Form

- `widgets/textfield.py`：
  - `_TextField`、`Input`、`Editor` 基类 -> `Widget`；删 `style/caret_style/prompt_style/focused`，加 `styles`；
  - 样式映射：正文 `group("text").base`（默认 NONE）、caret `group("text").caret`、prompt `group("content").accent`、placeholder/dim `group("text").faint`、selection `group("text").selection`、hover `group("surfaces").hover`；
  - `focused` 默认保持 `True`；
  - `revision()` 加 `theme/styles`；
  - `TextBuffer` 是编辑引擎，不必继承 Widget；把解析后的样式传给它。
- `widgets/combobox.py`：
  - 如 `Input`/`Autocomplete` 新增 `styles`，ComboBox 可接受 `styles` 并转发；保持默认渲染不变；参数 ≤10。
- `widgets/form.py`：
  - `Form` 基类 -> `Widget`；删除样式缓存，加 `styles`；标签 `group("content").accent`，错误 `group("status").danger`；`revision()` 加 `theme/styles`。
  - `Field` 是值对象，不改。
- `widgets/dialog.py`：只更新 `prompt_dialog` 里 `Input(...)` 的构造点（若签名变化）；不迁移 Dialog 本身。
- `app/find.py` / `app/command_palette.py`：只更新 `Input`/`Autocomplete` 构造点（若签名变化）。
- 允许改：`widgets/textfield.py`、`widgets/textbuf.py`（仅样式传递）、`widgets/combobox.py`、`widgets/form.py`、`widgets/dialog.py`（仅 Input 构造）、`app/find.py`/`app/command_palette.py`（仅构造）、`demo/topics/components_forms.py`、`demo/topics/patterns.py`、`demo/topics/components_overlays.py`、`tests/widgets/test_editing.py`、`test_combobox.py`、`test_form.py`、`test_invariants.py`。
- 验证：pytest + golden 不变。

### T3 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 五条门禁全绿；报告贴真实用例数/失败项。
2. forms 家族的公共构造器不再有 `style/hover_style/focus_style/disabled_style/ground_style/label_style/cursor_text_style/description_style/title_style/active_style/inactive_style` 和 `focused=`。
3. `Select` 构造器 ≤10 参数（若 MultiSelect 拆分成功）；否则记录遗留。
4. 同一实例改 `theme` 后重绘使用新主题（不必新增测试，现有 action 样板已覆盖模式；如 forms 有缓存风险，可在现有 test 文件加 1 个最小用例）。
5. golden 逐字节不变；framebench render hash 不变。

## 禁触清单

- 其它未迁移控件（data/navigation/content 属 W3c）。
- `core/**`（除非只加 import）、`app/**` 的接线逻辑。
- `docs/**`、README/CHANGELOG/pyproject、root `__all__`。
- golden 文件、`.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W3b-w3b-forms.md`，按 Handoff 协议，60-80 行；重点写清 forms 的样式映射、MultiSelect 取舍、调用点清单。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题
