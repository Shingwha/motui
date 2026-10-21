# W3 · Visual and glyph switch

> 分支 `motui-2/w3-visual`；起点 `main`（W1 + W2a-d 已合并）；写入范围见下。

## 目标

把默认视觉切换为 Ink & Signal 暗色，并完成全部 `Glyphs`/`Border` API 迁移。
本波是**唯一允许改变渲染字节**的波次；重录全部 golden，记录新 render-hash。

## 前置上下文

- 必读：`ref/interfaces.md`（§3.2、§4、§5、§7）→ W1 handoff → 四份 W2 handoff。
- 基线：`uv run pytest -q -p no:cacheprovider` 896 passed；golden 58；hash
  `f872187a…d6e1`。
- 已知 W2 收口点见 `ref/interfaces.md` §7.1。

## 工单

### T1 默认主题切暗色

- `src/motui/kernel/theme.py`：把 10 个 group 的**字段默认值**改为 §3.2 暗色值；
  `DEFAULT_THEME = Theme()`；确保 `Theme() == Theme.dark()`。
- `Theme.flat()` 保持 §3.2 的 flat 覆盖。
- demo `assets.py` 的 THEMES 补 `rows.inactive`，并把 `api_line` 的旧字段说明改为
  新 groups（只在 W3 不改变文本语义的前提下）。

### T2 Glyphs/Border 接线

统一规则：组件新增 `glyphs: Glyphs = GLYPHS`；删除旧的逐字形参数；实例内容覆盖
（`Divider(char=...)`、`Input(prompt=...)`、`Scrollbar(track=/thumb=...)`）保留。

| 文件 | 任务 |
|---|---|
| `widgets/action.py` | Checkbox 用 `glyphs.check_on/off`；删除 `mark_pair` |
| `widgets/choice.py` | Select 用 `glyphs.cursor`；RadioGroup 用 `glyphs.radio_*`；CheckboxGroup 用 `glyphs.check_*`；删除 `marker`/`mark_pair`/`empty`/`filled` |
| `widgets/textfield.py` | Input `prompt=None` 默认 `seat(glyphs.prompt)`；保留显式 prompt 覆盖 |
| `widgets/list.py` | 删 `marker`/`more_up`/`more_down`/`mark_pair`；用 `cursor`/`more_*`/`check_*` |
| `widgets/tree.py` | 删 `expanded`/`collapsed`；用 `fold_*` |
| `widgets/collapsible.py` | 用 `glyphs.fold_*`；删除模块标记常量 |
| `widgets/navlist.py` | 删 `bar`；用 `glyphs.rail`；`bar_space` 保留为布局覆盖 |
| `widgets/tabs.py` / `menubar.py` | 删 `divider`；用 `glyphs.vertical_rule`（组件加两侧空格） |
| `widgets/decor.py` | Divider `char=None` 默认 `glyphs.horizontal_rule` |
| `widgets/rows.py` | ShortcutBar 用 `glyphs.separator`；Notice 用 `glyphs.notice_*` + status 色；新增 `success` level |
| `widgets/indicators.py` | Progress 用 `bar_full/empty`；Slider 用 `slider_track/thumb`；Spinner 用 `spinner` |
| `widgets/table.py` | 删 `mark_pair`；用 `glyphs.check_*`；`grid: Border | None = None` 默认 `glyphs.grid` |
| `widgets/dialog.py` | `border: Border | None = None` 默认 `glyphs.box`；替换旧 6 元组 |
| `widgets/decor.py` Panel | 新增 `border: Border | None = None` 默认 `glyphs.box` |
| `widgets/diff.py` | 用 `glyphs.diff_add/remove/context`；`@@` 与省略行保持 |
| `widgets/markdown/*` | `Markdown(glyphs=GLYPHS)`；`RenderContext` 携带 glyphs；task 用 `check_*`，列表用 `bullets`，quote 用 `quote` |
| `widgets/syntax.py` | token 改读 `theme.syntax.*` |
| `widgets/autocomplete.py` / `combobox.py` / `dialog.py` | 传递 `glyphs=` 给子组件 |
| `interaction/find.py` / `palette.py` | 新增 `glyphs=GLYPHS`；通过 Host 工厂传给 Input/Autocomplete |
| `interaction/scrollbar.py` | 新增 `glyphs=`；`track/thumb` 默认 None -> `bar_empty/bar_full` |

### T3 测试与 golden

- 更新所有因新构造签名/字形/颜色失效的测试；`tests/test_invariants.py` 的
  CASES 必须覆盖新签名。
- `uv run python tools/golden.py --update` 重录 58 topics；`--check` 通过。
- 记录新的 `render-hash`（W3 之后稳定）。
- `uv run python -m motui < /dev/null` 与 `--pages` 必须 exit 0。

### T4 视觉收口

- Select description 改 `text.muted`；Divider label 改 `text.muted`；Table header 改
  `text.muted`；List/Tree unfocused 用 `rows.inactive`。
- Notice 删除文本前缀，统一 `i/✓/!/×`。
- Markdown task 统一 `[ ]/[x]`；列表 bullet 用 `•/◦/▪`。
- Input/Find prompt 统一 `❯`；列表/菜单 cursor 统一 `→`。
- Slider 统一 `━/●`；Scrollbar/Progress 统一 `█/░`。

## 验收

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
```

`pytest` 全绿；golden 58；`--pages` 4130 行（内容可变）；新 hash 记录在 handoff。

## 禁触清单

- 不删除兼容属性/旧 `style.py` 常量/旧 `glyphs.py` 常量/`bands.py`（W4）。
- 不改布局算法、事件模型、Host 协议。
- 不手改 golden；只用 `golden.py --update`。
- 不 merge/push/tag。

## 交接包

`handoff/W3-visual.md`：新 hash、golden 变化类别、每个组件签名变化、测试更新范围、
遗留到 W4 的清理项。
