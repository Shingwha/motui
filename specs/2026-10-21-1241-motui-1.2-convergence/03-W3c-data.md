# W3c · data / navigation 家族迁移（Widget / Styles）

> 分支 `refactor/1.2-w3c-data`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w3c-data`
> 前置：W3b 已合并（`5fc0736`）；写入范围见下；波末必须全量绿。

## 目标

把 data/navigation 家族迁移到 `Widget`/`Styles`：`List`、`Table`、`Tree`、`NavList`、`Tabs`、`MenuBar`、`ContextMenu`、`LabelStrip`、`ScrollView`。删除所有 `*_style` 与 `focused=` 参数；样式在 render 时解析；默认渲染/golden 逐字节不变。**本波不做 Table wrap（W5a）和 ScrollView bar 输入（W5b）。**

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§2 W3a/W3b 实际交付 + §2 W3 冻结）
  3. `handoff/W3a-w3a-widget-base.md`、`handoff/W3b-w3b-forms.md`
  4. 本工单
- 基线命令：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
```

起点 **882 passed / 57 topics match**。
- 稳定区（勿重读/勿改）：`core/**`、`widgets/action.py`、forms 四文件、全部 golden、`docs/**`。
- 已知约束/坑：
  - `Widget` 不继承 `Themed`；迁移控件时基类改 `Widget`，从 `__slots__` 删 `theme/focused/hover` 和 `_*_style` 缓存槽。
  - `focused=` 删除后在 `__init__` 保留旧默认：List `False`；Table/Tree/NavList/Tabs/MenuBar/ScrollView `True`。
  - `revision()` 末尾加 `self.theme, self.styles`。
  - `LabelStrip` 是 Tabs/MenuBar 的私有基类；迁移它时同步处理子类的槽。
  - `ContextMenu` 继承 `Select`（W3b 已迁），必须同步删除它转发给 Select 的旧 style 参数。
  - `ScrollView.scrollbar` 属性名保留；不要实现 bar 鼠标输入。
  - `Table` 不要实现 wrap；保持当前“自然宽度 + 比例收缩 + 省略”的行为。

## 工单（按序执行，每项一个 commit）

### T1 · List / Table / Tree

- `widgets/list.py`：
  - 基类 -> `Widget`；删 `ground_style/focused/disabled_style`，加 `styles`；
  - 行 band `group("rows")`；counter/label/disabled 文字：counter `text.muted`，disabled `text.faint`，label 默认（NONE）读 `text.base`；
  - `focused` 默认 `False`；`revision()` 加 `theme/styles`。
- `widgets/table.py`：
  - 基类 -> `Widget`；删 `header_style/first_column_style/border_style/active_style/ground_style/focused/disabled_style`，加 `styles`；
  - header `text.muted`；first column `text.base`（默认 NONE）；border `borders.grid`（`grid` 结构值仍独立）；行 band `rows`；disabled `text.faint`；
  - `focused` 默认 `True`；`revision()` 加 `theme/styles`。
- `widgets/tree.py`：
  - 基类 -> `Widget`；删 `guide_style/label_style/active_style/ground_style/focused/disabled_style`，加 `styles`；
  - guide `text.faint`；label `text.base`（默认 NONE）；行 band `rows`；disabled `text.faint`；
  - `focused` 默认 `True`；`revision()` 加 `theme/styles`。
- 允许改：`widgets/{list,table,tree}.py`、`tests/widgets/test_data.py`、`tests/test_invariants.py`、`demo/topics/components_data.py`、`demo/topics/reference.py`（仅 Table 构造）。
- 验证：pytest + golden 不变。

### T2 · NavList / Tabs / MenuBar / LabelStrip / ContextMenu / ScrollView

- `widgets/strip.py` 的 `LabelStrip`：基类 -> `Widget`；删 `theme/focused/hover` 槽与 `_*_style` 缓存；加 `styles`；`_layout`/render 时读组。
- `widgets/tabs.py` / `widgets/menubar.py`：
  - 基类保持 `LabelStrip`；删 `active_style/inactive_style/hover_style/disabled_style/divider_style/indicator_style/focused`，加 `styles`；
  - 映射：active `content.accent`、inactive `text.faint`、hover `surfaces.hover`、disabled `text.faint`、divider `text.muted`、indicator `controls.focus`（如有显式 indicator 角色则保持）；
  - `focused` 默认 `True`；`revision()` 加 `theme/styles`。
  - `ContextMenu` 删除转发给 `Select` 的旧 style 参数，改 `styles`。
- `widgets/navlist.py`：
  - 基类 -> `Widget`；删 `group_style/active_style/inactive_style/hover_style/disabled_style/bar_style/bar_active_style/ground_style/focused`，加 `styles`；
  - 映射：group `text.muted`、active `content.accent`、inactive `text.faint`、hover `surfaces.hover`、disabled `text.faint`、bar `content.accent` / bar-active `controls.focus`、ground `rows.base`；
  - `focused` 默认 `True`；`revision()` 加 `theme/styles`。
- `widgets/scroll.py` 的 `ScrollView`：
  - 基类 -> `Widget`；删 `theme` 参数保留（Widget 自带），加 `styles`；
  - track `chrome.scrollbar`、thumb `chrome.scrollbar_thumb`；render 时读 `group("chrome")`；
  - 不实现 bar 输入；`scrollbar` 属性名保留；`revision()` 加 `theme/styles`。
- 允许改：`widgets/{strip,tabs,menubar,navlist,scroll}.py`、`demo/shell.py`、`demo/topics/components_data.py`、`components_layout.py`、`interactions.py`、`tests/widgets/{test_navigation,test_menubar,test_scroll}.py`、`tests/test_invariants.py`。
- 验证：pytest + golden 不变 + demo 两个入口。

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
2. data/navigation 的公共构造器不再有 `*_style` 和 `focused=`。
3. `Table` 构造器只保留 `headers, rows, *, aligns, glyphs, grid, disabled, disabled_items, theme, styles`（+ 未来 W5a 的 wrap 参数）。
4. `ScrollView` 构造器为 `child, *, height, offset, scrollbar, glyphs, theme, styles`（W5b 再改 `bar`）。
5. golden 逐字节不变；render hash 不变。

## 禁触清单

- `core/**`、`widgets/action.py`、forms 文件、`widgets/markdown/**`、content 家族（W3d）。
- `Table` 的 wrap 逻辑（W5a）；`ScrollView` 的 bar 输入（W5b）。
- `app/**` 接线、`docs/**`、README/CHANGELOG/pyproject、root `__all__`、golden。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后写 `handoff/W3c-w3c-data.md`（60-80 行），重点写 data/navigation 的样式映射、LabelStrip 槽处理、调用点清单。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题
