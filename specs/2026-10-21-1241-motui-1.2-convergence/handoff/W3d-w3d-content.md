# W3d 交接包
> 分支 `refactor/1.2-w3d-content` / 起点 `3776e16`（W3c merge `06b54fa` + 工单提交）/ 2026-10-21

## A. 自动事实（从命令与代码生成，别凭记忆）

- commits：`58f577c`（T1）、`ee28fa3`（T2）、本文件所在 commit（T3）。
- `git diff --stat 3776e16..HEAD`：12 files, +461/-462（不含本文件）：`widgets/{decor,dialog,diff,
  indicators,layout,collapsible,rows}.py`、`widgets/markdown/component.py`、`tests/kernel/test_theme.py`、
  `tests/widgets/{test_containers,test_indicators,test_rows}.py`。
- 签名实测（`inspect.signature`，均无 `*_style` / `focused=`；`glyphs` 默认 GLYPHS 从略）：
  - `Divider(*, char, label, glyphs, theme, styles, max_width)`
  - `Panel(child, *, title, frame, border, glyphs, theme, styles)`；`ButtonSpec(label, value, styles, danger)`
  - `Dialog(title, body, buttons, *, danger, width, align, border, shade, frame, glyphs, theme, styles)`
  - `Diff(before, after, *, context, numbers, glyphs, theme, styles)`；`Padding(child, *, left, right, top, bottom, theme, styles)`
  - `ProgressBar(fraction, *, label, width_chars, glyphs, theme, styles)`；`Spinner(text, *, frames, glyphs, theme, styles)`
  - `Slider(value, *, minimum, maximum, step, glyphs, disabled, theme, styles)`；`Collapsible(title, body, *, open, glyphs, disabled, theme, styles)`
  - `StatusLine(*, left, right, theme, styles)`；`ShortcutBar(items, *, glyphs, theme, styles)`；`Notice(text, *, level, glyphs, theme, styles)`
  - `Markdown(text, *, block_rules, inline_rules, theme, styles, highlighter, glyphs, gap, divider_max_width, max_width)`
- `__slots__` 实测：13 个类均不含 `theme/focused/hover` 与任何 `_*_style` 缓存槽；基类全部 `Widget`
  （`Row/Column/Spacer` 未动）。`Markdown` 新增 `_user_highlighter`。
- `focused` 旧默认：Slider/Collapsible `False`，由 `Widget.__init__` 直接提供。
- 全波真实结果（本 worktree，CPython 3.13）：`pytest -q -p no:cacheprovider` -> **882 passed**
  （与起点相同，未增删测试）；`golden.py --check` -> **57 topics match**（未重录）；`framebench.py` ->
  render hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（同 W3a/W3b/W3c）；
  `python -m motui < /dev/null` -> exit 0；`--pages` -> exit 0，4059 行。

## B. 只存在于脑子里的东西（W5/W6 直接复用）

**content 家族样式映射（render 时 `self.group(...)`，不缓存）**

| 控件 | 映射 |
|---|---|
| Divider / Panel | 规则 `borders.base`，label `text.muted`；Panel framed `borders.base`，borderless `surfaces.base`（默认 NONE = 无 ground，同旧 `style=None`） |
| Dialog / ButtonSpec | border `borders.base`，danger 时 `status.danger`；title `content.headings[1]` |
| Diff | Del `status.danger` 去 bold；Ins `status.success`；hunk/elide `text.muted`；context `NONE` |
| ProgressBar / Spinner | done `status.success`，todo `text.faint`；Spinner `content.accent` |
| Slider | filled `content.accent`；empty `text.faint`；suffix `text.muted`；hover `surfaces.hover`；focus `controls.focus`；disabled `text.faint` |
| Padding / Collapsible | fill `surfaces.base`（NONE 走旧无填充分支）；title `content.accent`，hover/focus/disabled 同上 |
| StatusLine / ShortcutBar / Notice | 裸元素与 gutter `text.faint`；key `content.accent`、label `text.faint`；info `text.base`，其余 `status.*` |

**Markdown effective theme（关键实现）**
- `_effective_theme()`：遍历 10 个组名，`styles.<组> is not None` 的组 `replace(self._theme, **overrides)`；
  无覆盖返回 `self._theme`（零分配）。规则层一行未改，仍读 `ctx.theme`。
- `_sync_theme()` 在 `render()` 入口：effective != `_ctx.theme` 时重建 `RenderContext`（默认 highlighter 也按
  新 effective 重建；用户传入的 highlighter 原样保留），并丢弃 `_StreamCache` 与 `_stamp_key`。必须丢缓存：
  `_StreamCache` 只按 `(text, width)` 键，否则换主题发旧行。`revision()` 含 `theme/styles`；hover band
  改为 `self._ctx.theme.surfaces.hover`（`_hover_style` 槽删除）。

**ButtonSpec / Dialog**
- tuple 第三项现在是 `Styles`（旧的是 `Style`）。`_new_button`：`spec.styles` 原样交给 `Button`；
  `spec.styles is None and spec.danger` 时 `Styles(controls=replace(theme.controls, base=theme.status.danger))`。
- `Diff` 删除自己的 `theme` property（会与 `Widget.theme` 槽 + `_theme` property 递归）；render 缓存键改为
  `(width, theme, styles)`，保证换主题后同宽度重绘。旧 `border_style/title_style` 删除。

**调用点清单（`rg` 扫描 + 实测）**
- 改了：`tests/kernel/test_theme.py`（Divider `style=` -> `Styles(borders=...)`）；`test_containers.py`
  （Panel `style=`/Padding `fill_style=` -> `Styles(surfaces=...)`；Collapsible 三个 style -> 三个组）；
  `test_indicators.py`（Slider `disabled_style=` -> `Styles(text=...)`）；`test_rows.py`
  （StatusLine `gap_style=` -> `Styles(text=...)`）。
- 无需改：`demo/shell.py`、`demo/session.py`、`demo/topics/**`、`demo/stage.py`、`tests/test_invariants.py`、
  `tests/interaction/*`、`tests/app/**`、`widgets/markdown/blocks.py`（只传 `theme/glyphs/...`）。
- 坑：`demo/topics/components_layout.py` 的 Divider `api_line`、`components_data.py` 的 ProgressBar/Spinner
  `api_line` 仍是旧签名（渲染内容，进 golden），本波刻意未改，W6 更新文案时一并重录。

**偏差与取舍**
- `tests/kernel/test_theme.py` 与 `tests/widgets/test_containers.py` 不在 T1 允许清单，但它们是
  `Divider(style=)` / `Panel(style=)` 的唯一库外调用点，按“更新所有调用点”最小处理（仅构造方式）。
- Dialog 构造器 3 位置 + 10 keyword-only（工单要求保留 shade/frame/border/align/width），与 W3b `Select`
  同类，W6 若严格执行“≤10”需再收。
- `Padding` 把 `NONE` 当“无填充”而非“用 NONE 填满”，保持旧 `fill_style=None` 的逐字节输出。
- 未加新测试（工单要求）；`Markdown.theme = Theme.light()` 与 `styles` 覆盖已手工验证重绘。
- 未做 Table wrap（W5a）、ScrollView bar 输入（W5b）；root `__all__`/docs/golden 未动。

## C. 指针
- `src/motui/widgets/markdown/component.py`：`_effective_theme`、`_sync_theme`、`render`、`revision`。
- `src/motui/widgets/decor.py::Panel.render`（framed/borderless 分支）、`dialog.py::_new_button`。
- `src/motui/widgets/indicators.py::Slider.render`、`diff.py::Diff.render`（缓存键）。
- 稳定区（下一波不必重读）：`core/**`、`app/**`、全部 golden、`tools/**`、`docs/**`。
