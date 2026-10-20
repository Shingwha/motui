# W4b · row views、共享行带与 rows/decor
> 分支 `w4b-rowviews`；前置：W4a 已合并 @ `aa362e4`；写入范围见下。
> 深读：`00-overview.md` D5/D9、`ref/interfaces.md` §3、`docs/CONTRACT.md` §5。

## 目标

把 List/Table/Tree/Tabs/NavList 迁到同一套 cursor/result/disabled 契约；用 `RowBands` / `CursorWindow`
收掉 5 份行带与窗口算术；修 `Tree.filter` 过期 hover、`NavList.bar_space`、`Tabs._tab_at` 重 render；
补齐 `Divider`/`Panel`/`Notice`/`StatusLine`/`ShortcutBar` 的 `Revisioned`。**渲染字节不变**，golden 不动。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §3 → `handoff/W4a-components.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1777 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（勿重读）：W1–W4a 的 kernel/driver/events/keys/value semantics；W4a 的 action/choice/textfield/
  dialog/collapsible/indicators/markdown。
- W4a 已知约束：`Resultful.take_result()` 是结果门；`Controller.handle` consumed；
  `RadioGroup`/`CheckboxGroup` 已改名；`Select` 已有 `disabled/disabled_items`；
  demo 的 `registry/notes/views` 文案含旧名但属渲染内容，W4b 不改文案；demo kit/session 对 row views
  仍保留 `getattr(..., "chosen")` 回退，本波完成后删除。

## 工单（按序执行；HEAD 全绿即可，commit 粒度不限）

### T1 `widgets/bands.py`（新）+ `widgets/__init__.py`：共享 RowBands

- 新建 `RowBands`（frozen dataclass, slots）：
  ```python
  @dataclass(frozen=True, slots=True)
  class RowBands:
      ground: Style = NONE
      active: Style = NONE
      hover: Style = NONE
      focus: Style = NONE
      text: Style = NONE
      disabled: Style = NONE
      @classmethod
      def from_theme(cls, theme: Theme, **overrides: Style) -> "RowBands": ...
      def band(self, *, current: bool, hovered: bool, focused: bool, disabled: bool) -> Style: ...
  ```
- 优先级：`disabled`（若 true）→ `hover` → `current & focused` 的 `active` → `ground`；form 组若“永不为 pick 变暗”，
  可只用 tokens 自己组合，但默认规则必须与现行为逐字节一致。
- 提供 `rest(row: Line, width: int, band: Style) -> Line`：`fit(width)` 后，band 非 NONE 时
  `fill(fitted.width, band)`（与现有 `_rest` 同义）。
- `motui.widgets` 导出 `RowBands`；`tests/test_api_root.py` 同步。
- 测试：优先级矩阵、NONE fast path、fill 宽度。

### T2 `widgets/choice.py`：Select/RadioGroup/CheckboxGroup 接入 RowBands

- `Select`/`RadioGroup`/`CheckboxGroup` 加 `bands: RowBands | None = None`；`None` 时由 theme + 现有
  `ground_style`/`active_style`/`hover_style`/`disabled_style` 构造。
- 把 `_band`/`_rest`/`_row` 的行带部分改为 `RowBands.band` + `rest`；显式样式参数仍覆盖 token。
- 保持渲染字节不变（golden 不动）；`revision()` 包含 `bands`。
- 测试：bands 覆盖、默认与旧行为一致。

### T3 `widgets/list.py`：take_result、RowBands、CursorWindow

- 删除 `chosen`，实现 `take_result()`；`activate` 写 pending，`move` 按现有语义清 pending。
- 使用 `CursorWindow`（`kernel/cursor.py`）替换手写 `_visible_range`；确认 start/stop 与现行为一致。
- 加 `bands: RowBands | None = None`、`disabled: bool = False`、`disabled_items: Iterable[int] = ()`；
  `move` 跳过 disabled 项，`click`/`activate`/`toggle` 拒绝 disabled 项；`disabled_style` 渲染。
- `_band`/`_rest` 改用 `RowBands`；`handle` 的 `prefix_jump` 保持 case-insensitive。
- 测试：take_result 读一次清空、disabled 跳过/拒绝、CursorWindow 窗口一致、RowBands。

### T4 `widgets/table.py`：take_result、RowBands、disabled

- 删除 `chosen`，实现 `take_result()`（返回当前行 index）；`activate` 写 pending。
- `selected_style` → `active_style`（行带）；加 `bands: RowBands | None = None`。
- 加 `disabled: bool = False`、`disabled_items: Iterable[int] = ()`（数据行）；`move` 跳过，
  `click`/`activate`/`toggle` 拒绝；disabled 行用 `disabled_style` 渲染。
- `_row_band`/`_rest` 改用 `RowBands`；保持 `sort_by`/`set_widths`/`header_line` 行为。
- 测试：take_result、disabled 跳过/拒绝、RowBands、sort/widths 回归。

### T5 `widgets/tree.py`：take_result?、disabled、hover、RowBands

- **不加** `take_result`（树的 activate 是展开/折叠，不是一次性结果）；`activate` 继续返回 bool。
- `TreeNode` 加 `disabled: bool = False`；`Tree` 加 `disabled: bool = False`；
  `move` 跳过 disabled 节点，`click`/`activate` 拒绝 disabled 节点；disabled 节点用 `disabled_style`。
- `cursor_style` → `active_style`（行带）；加 `bands: RowBands | None = None`。
- **修 P0 遗留**：`filter(query)` 清空 `_hover_index`（与 Autocomplete 同规则）。
- `_band`/`_rest` 改用 `RowBands`。
- 测试：filter 清 hover、disabled 跳过/拒绝、active_style 命名、RowBands。

### T6 `widgets/tabs.py` + `widgets/navlist.py`：index、disabled_items、命中表

- `Tabs.active` → `index`（只读 property；`select(index)` 是移动门）。
- `Tabs.disabled` → `disabled_items: Iterable[int]`；新增全局 `disabled: bool = False`；
  `select`/`move`/`click` 在 disabled 时拒绝；保留逐项 disabled 语义。
- **修 P0**：`_tab_at` 不再调用 `self.render(...)`；`render` 时记住上次的 span 表，hit 读表。
- `NavList.active` → `index`；`disabled` → `disabled_items` + 全局 `disabled`；
  `bar_space` 改为只读 property（内部 `_bar_space`），`revision` 用内部值。
- `NavList` 的 `_rest`/bands 改用 `RowBands`（若适用）；组行保持现状。
- 测试：active→index、disabled_items、Tabs hit 不重 render、NavList.bar_space 只读。

### T7 `widgets/decor.py` + `widgets/rows.py` + `widgets/layout.py` + `widgets/delegate.py`

- `Divider`/`Panel`/`Notice`/`StatusLine`/`ShortcutBar` 实现 `Revisioned.revision`：
  - `Divider`: `(char, style, label, label_style, max_width, theme)`
  - `Panel`: `(title, style, frame, theme, child revision/identity)`
  - `Notice`: `(text, level, theme)`
  - `StatusLine`: `(tuple(left), tuple(right), gap_style, theme)`
  - `ShortcutBar`: `(tuple(items), separator, key_style, label_style, theme)`
- `StatusLine`/`ShortcutBar` 构造时把序列复制为 tuple，避免宿主原地改动绕过快照。
- `Row`/`Column`/`Padding`/`Spacer` 加 `Revisioned`（快照包含 gap/widths/padding/fill_style 与子组件
  revision/identity），保证 sealed block 下的可变参数能重绘。
- `Delegate` 已有转发；确认 `child_at` 不接收负坐标（与 Row/Column 一致）。
- 测试：每个组件在 sealed block 中改一个可变输入后 `Block.rows` fresh；容器子组件 revision 变化。

### T8 demo、测试、文档、handoff

- demo kit/session 删除 `getattr(..., "chosen")` 回退，row views 全部用 `take_result()`；
  `active` → `index`、`disabled` → `disabled_items` 的代码调用点迁移。
- **不改 demo 的渲染文案**（`registry/notes/views` 旧名保留，W7 统一）；golden 不得移动。
- `tests/test_api_root.py` 同步 `RowBands`；相关测试迁移。
- `docs/COMPONENTS.md`/`README.md` 只改与本波冲突的条目；W7 重写整篇。
- 跑 `## 验收`，写 `handoff/W4b-rowviews.md`。
- 不 merge / push / tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1777 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match（行带重构不应移动渲染）
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`：exit 0
5. `uv run python -m motui --pages`：exit 0
6. P0 测试：Tree.filter 清 hover、NavList.bar_space 只读、Tabs hit 不重 render、
   decor/rows sealed 突变 fresh
7. `grep -rn "\.chosen\|\.active\b\|disabled=" src/motui/widgets/{list,table,tree,tabs,navlist}.py`：
   零命中（旧名/旧语义；历史文档除外）
8. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`widgets/{action,autocomplete,combobox,textfield,textbuf,dialog,collapsible,indicators}.py`、
  `widgets/markdown/**`、`kernel/**`（`kernel/cursor.py` 只允许在必要时修 docstring，不改语义）、
  `app.py`、`keys/**`、`kernel/events.py`、`tests/golden/**`、`pyproject.toml`、`uv.lock`、`docs/CONTRACT.md`。
- 禁加：兼容 alias、旧名 re-export、deprecated 转发。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `handoff/W4b-rowviews.md`（60–80 行，A/B/C）：

- A：`git diff --stat`、新增/变更公开签名、基线真实结果
- B：与 spec 的偏差、踩坑、W5 必须遵守的隐式约束、未决问题
- C：关键文件:行号、commit、稳定区

## 最终报告

工单状态表（T1–T8）/ commit 清单 / 自测真实输出 / 组件 API 变更清单 / 测试改动清单 /
P0 修复证据 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
