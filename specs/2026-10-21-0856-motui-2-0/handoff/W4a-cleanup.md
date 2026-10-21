# W4a 交接包（cleanup and visual closeout）

> 分支 `motui-2/w4a` / 起点 `d661659`（main，W1 + W2a-d + W3 已合并） / 2026-10-21
> 源码/测试/golden 7 个 commit；本文件为最后一个 commit。

## A. 自动事实

### 用例数与门禁真实输出

```text
uv run pytest -q -p no:cacheprovider
1 failed, 889 passed in 4.62s
```

唯一失败是 `tests/test_packaging.py::test_the_version_is_one_number_across_pyproject_metadata_and_fallback`：
本分支把 fallback 改成 `2.0.0`，而 `pyproject.toml` 仍由 W4b 持有、当前是
`1.1.8`。按工单“两者合并后一致”，该用例在 W4a 单独运行时必然红；W4b 把
`pyproject.toml` 提到 2.0.0 后即恢复。除它之外 889 个用例全绿。

```text
uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
stream-single:     0.9 ms/frame
stream-split :     5.2 ms/frame
scroll       :     0.5 ms/notch
scroll-long  :     1.9 ms/notch
text-open    :     0.1 ms/frame
table-open   :     0.1 ms/frame
stream-paragraph:     0.7 ms/frame
replay       :   398 ms total
render-hash  : a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379

uv run python -m motui < /dev/null
exit 0，70 行，stderr 0 行

uv run python -m motui --pages > /tmp/pages.txt
exit 0，4130 行，stderr 0 行
```

基线（开工前同一 worktree 实测）：897 passed、golden 58、hash
`a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。

**render-hash 未变**：仍为
`a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。
framebench 的 `hash_workload` 只组合 Markdown / Scrollbar / 固定滚动脚本，
W4a 改动的 RadioGroup/CheckboxGroup、List counter、Table hover 与 RowStyles
默认路径不在该工作负载上，所以字节摘要不动；这是真实输出，不是漏跑。

用例数 897 -> 890：删除 `tests/widgets/test_bands.py`（8 个用例，模块已删除），
在 `tests/kernel/test_lines.py` 补 2 个 `rest` 用例；删除 2 个兼容属性用例，
新增 1 个“旧属性不存在”用例。没有跳过或删减行为断言。

### Commit 清单

| commit | 内容 |
|---|---|
| `172ede5` | `theme: drop the flat 1.x compatibility properties` |
| `4245e3b` | `widgets: remove RowBands and resolve every row band from theme.rows` |
| `94820f7` | `kernel: delete the 1.x style and glyph constants` |
| `a4206a4` | `widgets: close the group labels, list counters and table hover bridge` |
| `b769ecf` | `api: export Palette, Glyphs and Border from the root` |
| `5f74792` | `golden: re-record the row-bands topic on theme.rows` |
| `b64e7f7` | `widgets: drop the unused List ground cache` |
| 本文件所在 commit | `specs: hand off the W4 cleanup` |

### 变更范围 / 禁触审计

`git diff --stat main...HEAD` 共 44 个文件（不含本交接包）：
518 insertions / 1080 deletions。全部落在 `src/`、`tests/`、`tests/golden/`；
`docs/`、`README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml`、
`uv.lock` 零 diff。未 merge/push/tag。

- 根层：`kernel/{theme,lines,style,glyphs,mark,selection,__init__}.py`。
- 组件：`widgets/{bands(删除),list,choice,tree,navlist,table,indicators,__init__}.py`。
- 驱动/demo：`app.py`、`demo/{session,shell,stage}.py`、4 个 topic。
- 测试：13 个测试文件 + 删除 `tests/widgets/test_bands.py`。
- golden：58 个全部经 `--update` 重录，只有
  `tests/golden/topics/styling--row-bands.txt` 真实变化；其余 57 个字节相同
  （`--update` 写 LF，Git 在 Windows 检出时再转 CRLF，`git diff` 只看到一处）。

## B. 只有存在于脑子里的东西

### T1 兼容属性 / `_pick`

- `Theme` 的 25 个 1.x 平铺属性全部删除：`dim`、`muted`、`accent`、`success`、
  `error`、`warning`、`border`、`code`、`focus`、`selection`、`heading`、`link`、
  `inline_code`、`list_marker`、`hover`、`caret`、`ground`、`ground_active`、
  `table_border`、`first_column`、`scrollbar`、`scrollbar_thumb`、`toast`、
  `headings`、`notice_levels`。没有别名，没有 `__getattr__` shim。
- `Themed._pick` 删除；`Text` 的唯一主题读取改成
  `self.pick(None, self._theme.surfaces.hover)`。
- 全仓（`src/`、`tests/`、`demo/`）grep 旧属性读取清零；`test_theme.py` 新增
  `test_the_flat_1x_names_are_gone`（逐名 `hasattr` 为假，赋值抛
  `AttributeError`）。
- demo 的 `stage.py`/`session.py`/`shell.py`/两个 topic 同步改用 group 路径。

### T2 行带：`RowBands`/`BandedRows`/`bands=` 全部删除

- `rest(row, width, band)` 移到 `motui.kernel.lines`（`__all__` 已导出），
  逐字保留 `fit` + `fill` 与 `NONE` 快路径；`tests/kernel/test_lines.py` 接管
  原 `test_bands.py` 的两个 `rest` 用例。
- `widgets/bands.py` 删除；`widgets/__init__.py` 不再导出 `RowBands`。
- `List`、`Select`、`RadioGroup`、`CheckboxGroup`、`Tree`、`NavList`、`Table`
  删除 `bands: RowBands | None = None` 参数与 `self.bands`。
- 默认路径统一为 `theme.rows.band(...)`；显式
  `ground_style`/`active_style`/`hover_style`/`disabled_style` 仍在构造时
  `replace` 到有效的 `RowStyles` 上，优先级仍是 explicit > theme。
- `List`/`Tree` 不再有 `_band_source`/`_band_seed`/`_themed_bands` 分支；
  `Table` 的 `_row_band` 只剩一条 `self._row_styles.band(...)`。
- demo `styling.py` 的 row-bands topic 改为
  `replace(theme, rows=replace(theme.rows, ...))`，文案、summary、api_line、
  components 全部改写；对应 golden 重录。

### T3 旧常量

- `kernel/style.py` 删除 14 个语义常量（`ACCENT`/`BORDER`/`CODE`/`DIM`/
  `ERROR`/`FOCUS`/`HEADING`/`INLINE_CODE`/`LINK`/`LIST_MARKER`/`MUTED`/
  `SELECTION`/`SUCCESS`/`WARNING`）及 `__all__` 条目；只留 `NONE`、`RESET`、
  颜色/量化/SGR/检测 API。
- `kernel/__init__.py` 同步删除这些导出。
- `app.py` 的 `TUI.system()` 改为 `self.theme.text.muted`。
- `kernel/selection.py` 的 `highlight` 默认样式改为局部
  `Style(reverse=True)`，docstring 改为 `theme.text.selection`。
- `kernel/glyphs.py` 删除 15 个旧字形常量（`CURSOR`、`MENU_CURSOR`、
  `RAIL_BAR`、`EXPANDED`、`COLLAPSED`、`RADIO_EMPTY`、`RADIO_FILLED`、
  `MARKED`、`UNMARKED`、`MORE_UP`、`MORE_DOWN`、`TRACK`、`THUMB`、
  `TASK_OPEN`、`TASK_DONE`）及 `__all__`；保留
  `Glyphs`/`Border`/`GLYPHS`/`pair_seat`/`seat`/`seat_width`。
- `kernel/mark.py` 的 `mark_prefix` 默认值改为 `GLYPHS.check_on/off`。
- `widgets/indicators.py` 删除未使用的 `DEFAULT_FRAMES`/`FILL`/`EMPTY`，
  `__all__` 只留三个组件。
- `widgets/scroll.py`、`menubar.py` 的旧常量 docstring 引用改成 Glyphs 字段。

### T4 最终视觉收口（逐条）

- `RadioGroup`: mark（`(•)`/`( )` 的 pair seat）在 cursor 行用
  `content.accent`，label 用 `text.base`（显式 `label_style` 只改 label；
  disabled 行 mark/label 仍 `disabled_style`）。
- `CheckboxGroup`: cursor seat 与 `[x]`/`[ ]` mark 用 `content.accent`，
  label 用 `text.base`；其余同 RadioGroup。
- `List` counter 行（`↑ N more` / `↓ N more`）从 `text.faint` 改为
  `text.muted`。
- Table 的 `rows.hover is NONE -> surfaces.hover` 兼容桥删除；`rows.hover`
  直接作为 hover 令牌。默认暗色主题下两者同值，golden 文本不变。
- 额外收口：`Select`/`RadioGroup`/`CheckboxGroup` 的 unfocused cursor 现在
  走 `rows.inactive`（`RowStyles.band` 的既有优先级），不再保留
  `RowBands` 的 active.merge(dim) 规则；这是 §3.3 的 2.0 语义。

### T5 公开面

- `motui.kernel` 新增导出 `Palette`、`Glyphs`、`Border`、`GLYPHS`
  （`__all__` 同步）。
- `motui` 根新增 `Glyphs`、`Border`，`Palette` 改指 **主题创作层**
  `kernel.theme.Palette`。这是有意的 2.0 破坏性改名：interaction 的命令面板
  `Palette` 仍在 `motui.interaction.Palette`，只是不再占据根名。demo 两处
  旧的根导入已改为 interaction 导入。
- 根 `__all__` 从 34 个名字变为 36 个；fallback 版本 `2.0.0`
  （`pyproject` 由 W4b 同步）。

### 最终签名 / 删除清单

```python
# motui.kernel.lines
def rest(row: Line, width: int, band: Style) -> Line: ...

# Theme / Themed
Theme(text=..., surfaces=..., borders=..., controls=..., rows=...,
      status=..., content=..., chrome=..., overlays=..., syntax=...)
Themed.pick(explicit, fallback)          # 只有 pick；_pick 已删除
```

- 删除参数：`List/Select/RadioGroup/CheckboxGroup/Tree/NavList/Table` 的
  `bands=`。
- 删除属性：`Theme` 的 25 个 1.x 平铺属性。
- 删除模块/类：`motui.widgets.bands`、`RowBands`、`BandedRows`、
  `resolve_band`（`rest` 迁入 `kernel.lines`）。
- 删除常量：14 个 style 语义常量、15 个旧 glyph 常量、
  `DEFAULT_FRAMES`/`FILL`/`EMPTY`。
- 删除测试文件：`tests/widgets/test_bands.py`（由 `test_lines.py` 的
  `rest` 用例接替）。

### 偏差、取舍与已知风险

1. **`test_packaging` 在 W4a 单独运行时红**：fallback `2.0.0` vs
   `pyproject.toml` `1.1.8`。不是代码缺陷，是 W4b 的顺序依赖；两分支合并
   （或 W4b 先改 pyproject）后恢复。不要在 W4a 改 `pyproject.toml` 绕过。
2. **render-hash 未动**：见 A 节；改动不在 `hash_workload` 的路径上。
   不要为了“让 hash 变”而扩大本波范围。
3. **根 `Palette` 语义变了**：`from motui import Palette` 现在是主题
   Palette。仓库内没有旧用法；下游 1.x 代码若把根 `Palette` 当命令面板，
   需要改 `motui.interaction.Palette`（2.0 发布说明由 W4b 记录）。
4. **Select 的 unfocused cursor 带**：W2/W3 的 `RowBands` 规则是
   “active 无背景时 merge dim”，2.0 `RowStyles.band` 的规则是
   `rows.inactive`。默认暗色下从 `surface_active` 变为
   `surface_inactive`；这是 §3.3 的预期语义，相关测试已改为
   `rows.inactive`。
5. **disabled 行带**：List/Tree/Table/NavList 的 band 从旧的
   `text.faint` 改为 `rows.disabled`（暗色默认 `NONE`）；disabled 的**文字**
   仍是 `disabled_style`（`text.faint`），所以颜色可见行为不变，只有填充
   SGR 变了。
6. **group label 的显式样式**：`RadioGroup`/`CheckboxGroup` 的显式
   `label_style` 现在只作用于 label；mark 保持 accent/`label_style`（非
   cursor 行）/`disabled_style`。这与 Checkbox 的“显式 style 同时画 mark 和
   label”不同，是 group 的既有参数面限制（group 没有单独的 mark_style）。
7. **§5 仍有未收口项**（本波 T4 未点名，未改，列在这里避免静默）：
   `NavList`/`Tabs`/`MenuBar` 的 inactive 仍是 `text.faint`（§5 写
   `text.muted`）；`Tabs`/`MenuBar` 的 divider 仍是 `text.muted`（§5 写
   `chrome.divider`）；`Tree` 的 fold 仍随 `guide_style`（`text.faint`，§5
   写 `text.muted`）；`Collapsible` 的 title 仍是 `content.accent`（§5 写
   `text.base`）、marker 未单独用 `text.muted`；`Form` 的 label 仍是
   `content.accent`（§5 写 `text.muted`）；`ShortcutBar`/`StatusLine` 的
   label 仍是 `text.faint`（§5 写 `text.muted`）；`Button`/`Checkbox` 的
   hover/disabled 仍读 `surfaces.hover`/`text.faint`（§5 的 control 族写
   `controls.hover`/`controls.disabled`）。这些都不在本波硬性清单内，改动会
   扩大视觉 diff，留给后续波次决定。
8. **golden 重录**：58 个全部重写，但只有 `styling--row-bands.txt` 内容
   变化；统计时不要把 CRLF 工作树噪声当成 58 处改动。
9. **`Theme.flat()` 不变**：本波没有改 flat 的显式 `NONE` 构造；相关契约
   测试仍绿。

## C. 指针

- 工单：`specs/2026-10-21-0856-motui-2-0/04-W4a-cleanup.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md`
  §3.2/§3.3/§3.4/§4/§5
- 主题：`src/motui/kernel/theme.py`
- 行模型 / `rest`：`src/motui/kernel/lines.py`
- 字形：`src/motui/kernel/glyphs.py`
- 行带组件：`src/motui/widgets/{list,choice,tree,navlist,table}.py`
- 公开面：`src/motui/kernel/__init__.py`、`src/motui/__init__.py`
- 契约测试：`tests/kernel/test_theme.py`、`test_lines.py`、
  `tests/test_api.py`、`tests/test_invariants.py`
- 视觉门禁：`uv run python tools/golden.py --check`、
  `uv run python tools/framebench.py`
- 基线：897 passed / golden 58 / hash `a82f7968…`
- 本波 HEAD：本文件所在 commit
