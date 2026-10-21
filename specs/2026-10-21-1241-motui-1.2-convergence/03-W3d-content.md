# W3d · content / layout / markdown 家族迁移（Widget / Styles）

> 分支 `refactor/1.2-w3d-content`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w3d-content`
> 前置：W3c 已合并（`06b54fa`）；写入范围见下；波末必须全量绿。

## 目标

把最后一批控件迁移到 `Widget`/`Styles`：`Divider`、`Panel`、`Dialog`/`ButtonSpec`、`Diff`、`ProgressBar`、`Slider`、`Spinner`、`Padding`、`Collapsible`、`StatusLine`、`ShortcutBar`、`Notice`、`Markdown`。删除 `*_style`/`focused=`，样式在 render 时解析；默认渲染/golden 逐字节不变。

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§2 W3a/W3b/W3c 实际交付 + §2 W3 冻结）
  3. `handoff/W3a-w3a-widget-base.md`、`handoff/W3b-w3b-forms.md`、`handoff/W3c-w3c-data.md`
  4. 本工单
- 基线命令：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
```

起点 **882 passed / 57 topics match**。
- 稳定区（勿重读/勿改）：`core/**`、已迁移的 action/forms/data 文件、全部 golden、`docs/**`。
- 已知约束/坑：
  - `Widget` 不继承 `Themed`；迁移控件时基类改 `Widget`，从 `__slots__` 删 `theme/focused/hover` 和 `_*_style` 缓存槽。
  - `focused=` 删除后在 `__init__` 保留旧默认：Slider/Collapsible `False`；其余无焦点语义的控件保持 False 即可。
  - `revision()` 末尾加 `self.theme, self.styles`。
  - Markdown 的规则层大量读 `ctx.theme.<group>`；不要改每个规则。`Markdown` 用 `_effective_theme()` 把 `Styles` 的非 None 组合成 `replace(self._theme, **overrides)`，再传给 `RenderContext`。
  - `RegexHighlighter` 是 helper 不是 widget，可继续 `Themed`；但 `Markdown` 的 `highlighter` 传入的 theme 应是 effective theme。
  - `ButtonSpec` 是值对象，不是 widget；把 `style/hover_style/focus_style` 换成 `styles: Styles | None`，`danger` 保留；`Dialog._new_button` 已有一版转换逻辑，按其扩展。
  - `Panel` 的 `style` 在 framed 时是边框色、borderless 时是填充色；映射为 framed `borders.base` + borderless `surfaces.base`（默认都是 NONE，渲染不变）。用户若要同时覆盖，传两个组。
  - `Padding` 目前不是 Themed；迁移到 `Widget` + `styles`，fill 用 `surfaces.base`（默认 NONE）。`Row`/`Column`/`Spacer` 保持普通 Component，不必继承 Widget。

## 工单（按序执行，每项一个 commit）

### T1 · Divider / Panel / Dialog / Diff / indicators

- `widgets/decor.py`：
  - `Divider`：删 `style/label_style`，加 `styles`；render 读 `group("borders").base` / `group("text").muted`；`char/label/max_width` 保留；`revision` 加 theme/styles。
  - `Panel`：删 `style`，加 `styles`；framed 读 `group("borders").base`，borderless 读 `group("surfaces").base`；`frame/border/glyphs/title` 保留；`revision` 加 theme/styles。
- `widgets/dialog.py`：
  - `ButtonSpec`：`style/hover_style/focus_style` -> `styles: Styles | None = None`；`danger` 保留。
  - `Dialog`：删 `border_style/title_style`，加 `styles`；border `borders.base`（danger 时 `status.danger`），title `content.headings[1]`；`shade/frame/border/align/width/glyphs` 保留。
  - `_new_button`：`spec.styles` 优先；`danger` 且无 styles 时给 `controls.base` 默认 `status.danger`；保持旧默认输出。
- `widgets/diff.py`：删 style 缓存，`Del` `status.danger`、`Ins` `status.success`、`hunk` `text.muted`；`revision` 加 theme/styles。
- `widgets/indicators.py`：
  - `ProgressBar`：删 `done_style/todo_style`，加 `styles`；done `status.success`、todo `text.faint`。
  - `Slider`：删 `filled_style/empty_style/hover_style/focus_style/disabled_style/focused`，加 `styles`；filled `content.accent`、empty `text.faint`、hover `surfaces.hover`、focus `controls.focus`、disabled `text.faint`；`focused` 默认 False。
  - `Spinner`：删 `style`，加 `styles`；`content.accent`。
- 允许改：`widgets/{decor,dialog,diff,indicators}.py`、`demo/topics/{components_text,components_layout,components_overlays,styling,patterns}.py`、`tests/widgets/{test_dialog,test_diff,test_indicators}.py`、`tests/test_invariants.py`、`tests/interaction/test_modal.py`（仅 ButtonSpec 构造）。
- 验证：pytest + golden 逐字节不变。

### T2 · Padding / Collapsible / rows / Markdown

- `widgets/layout.py`：`Padding` 基类 -> `Widget`，删 `fill_style`，加 `styles`；fill `group("surfaces").base`；`revision` 加 theme/styles；`Row/Column/Spacer` 不动。
- `widgets/collapsible.py`：基类 -> `Widget`；删 `title_style/hover_style/focus_style/disabled_style/focused`，加 `styles`；title `content.accent`、hover `surfaces.hover`、focus `controls.focus`、disabled `text.faint`；`focused` 默认 False。
- `widgets/rows.py`：
  - `StatusLine`：删 `gap_style`，加 `styles`；元素默认/gu gutter `text.faint`。
  - `ShortcutBar`：删 `key_style/label_style`，加 `styles`；key `content.accent`、label `text.faint`。
  - `Notice`：无 style 参数（level 在 render 解析）；保留，但 `revision` 加 theme/styles；level info `text.base`、success/warn/error `status.*`。
- `widgets/markdown/component.py`：
  - `Markdown` 基类 -> `Widget`；加 `styles`；`_effective_theme()` 用 `replace` 合并非 None 组；`hover_style` 从 effective theme 取 `surfaces.hover`；`RenderContext(theme=effective_theme)`；
  - `revision` 加 theme/styles；`block_rules/inline_rules/highlighter/glyphs/gap/divider_max_width/max_width/text` 保留。
  - `RegexHighlighter` 不动。
- 允许改：`widgets/{layout,collapsible,rows}.py`、`widgets/markdown/component.py`、`demo/shell.py`、`demo/session.py`（仅 StatusLine/ShortcutBar 构造）、`demo/topics/{components_text,components_layout,patterns,styling,overview,reference}.py`、`tests/widgets/{test_containers,test_rows,test_markdown}.py`、`tests/test_invariants.py`、`tests/app/test_driver.py`（仅构造）。
- 验证：pytest + golden 逐字节不变。

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
2. content/layout/markdown 的公共构造器不再有 `*_style` 和 `focused=`（`Row/Column/Spacer` 无样式参数）。
3. `Markdown` 接受 `styles=`，规则层仍通过 `ctx.theme` 工作。
4. golden 逐字节不变；render hash 不变。
5. 若迁移 Markdown 的 effective theme 导致 golden 变化，停下来报告，不要重录。

## 禁触清单

- `core/**`、已迁移的 action/forms/data 文件、`app/**` 接线。
- `Table` wrap（W5a）、`ScrollView` bar 输入（W5b）。
- `docs/**`、README/CHANGELOG/pyproject、root `__all__`、golden。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后写 `handoff/W3d-w3d-content.md`（60-80 行），重点写 content/layout/markdown 样式映射、Markdown effective theme、ButtonSpec 迁移、调用点清单。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题
