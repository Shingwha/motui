# W3c 交接包
> 分支 `refactor/1.2-w3c-data` / 起点 `4018b12` / 2026-10-21

## A. 自动事实（从命令与代码生成，别凭记忆）
- commits：`d5c49e6`（T1）、`4a78caa`（T2）、本文件所在 commit（T3）。
- `git diff --stat 4018b12..HEAD`：13 files, +312/-426（不含本文件）。文件：
  `widgets/{list,table,tree}.py`、`widgets/{strip,tabs,menubar,navlist,scroll}.py`、
  `demo/shell.py`、`demo/topics/components_data.py`、`tests/widgets/{test_data,test_navigation}.py`、
  `tests/kernel/test_theme.py`。
- 签名实测（`inspect.signature`，均无 `*_style` / `focused=`）：
  - `List(items=(), *, window=8, prefix_jump=True, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)`
  - `Table(headers, rows, *, aligns=None, glyphs=GLYPHS, grid=None, disabled=False, disabled_items=(), theme=None, styles=None)`
  - `Tree(root_nodes, *, indent=2, glyphs=GLYPHS, disabled=False, theme=None, styles=None)`
  - `NavList(items, *, groups=(), index=0, disabled_items=(), disabled=False, glyphs=GLYPHS, bar_space=None, theme=None, styles=None)`
  - `Tabs(tabs, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False, theme=None, styles=None)`
  - `MenuBar(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False, theme=None, styles=None)`
  - `ContextMenu(options=(), *, title='', max_rows=8, glyphs=GLYPHS, **kwargs)`（未变；`**kwargs` 继续转发 Select 的 `theme/styles`）
  - `ScrollView(child, *, height=None, offset=0, scrollbar=False, glyphs=GLYPHS, theme=None, styles=None)`
- `__slots__` 实测：九个类均不再含 `theme/focused/hover` 与任何 `_*_style` 缓存槽；行为状态槽保留
  （`Tabs` 只剩 `tabs`，`MenuBar` 只剩 `_pending/items`，`NavList` 只剩 bar/gutter/group/index，`ScrollView` 只剩 `_state/_last_*/_rendered`）。
- 基类实测：`List/Table/Tree/ScrollView -> Widget`；`NavList/LabelStrip -> (ClampedCursor, Widget)`；`Tabs/MenuBar -> LabelStrip`。
- 全波真实结果（CPython 3.13）：`pytest -q -p no:cacheprovider` -> **882 passed**（与起点相同，未增删测试）；
  `golden.py --check` -> **57 topics match**（未重录）；`framebench.py` -> render hash
  `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（W3a/W3b/W2 同值）；
  `python -m motui < /dev/null` -> exit 0；`--pages` -> exit 0，4059 行。
- `focused` 旧默认实测：List `False`；Table/Tree/NavList/Tabs/MenuBar/ScrollView `True`。

## B. 只存在于脑子里的东西（W3d/W5 直接复用）
**迁移 pattern（照 W3a/W3b，全部验证）**
1. `class X(Widget)`（`LabelStrip` 为 `ClampedCursor, Widget`）；`super().__init__(theme, styles)`；
   `focused` 在子类 `__init__` 里显式补旧默认，之后由 FocusManager/App 改写。
2. `__slots__` 删除 `theme/focused/hover` 和全部 `_*_style`；构造器删 `*_style`/`focused`，加 `styles: Styles | None = None`。
3. render 每次 `self.group("<组>")`，不缓存；状态优先级不变。`revision()` 末尾放 `self.theme, self.styles`。
4. `Table._grid` 把 `text/borders/rows` 组提到每次网格构建的顶部各取一次，避免每 cell 走 `group()`；
   `table-open` 仍 0.1 ms/frame。

**样式映射（data/navigation 实际落地）**

| 控件 | 文字 | 行带 / 其它 |
|---|---|---|
| List | 标签+marker+mark `text.base`（默认 NONE）；counter `text.muted`；disabled `text.faint` | `rows.band(active, hovered, focused, disabled)` |
| Table | header `text.muted`；首列+padding `text.base`（默认 NONE）；其余 `NONE`；disabled `text.faint` | 边框 `borders.grid`；`rows.band(...)`；header/rules `rows.base` |
| Tree | guide+fold `text.faint`；label `text.base`（默认 NONE）；disabled `text.faint` | `rows.band(...)` |
| Tabs | active `content.accent`；inactive/disabled `text.faint`；hover `surfaces.hover`；divider `text.muted` | indicator `controls.focus` + `UNDERLINE`；unfocused 改 `text.muted` |
| MenuBar | active `content.accent`；inactive/disabled `text.faint`；hover `surfaces.hover`；divider `text.muted` | 颜色即指示器，无下划线 |
| NavList | group `text.muted`；active `content.accent`；inactive/disabled `text.faint`；hover `surfaces.hover` | bar 座 `text.muted`；active bar `content.accent`，unfocused merge `text.muted`；band 顺序 disabled > hovered > active > base（不走 `band()` 的 inactive） |
| ScrollView | — | track `chrome.scrollbar`；thumb `chrome.scrollbar_thumb`（render 时读 `group("chrome")`） |

**LabelStrip 槽处理**
- 没有自己的 `__init__`；Tabs/MenuBar 的 `super().__init__(theme, styles)` 沿 MRO 落到 `Widget.__init__`
  （`ClampedCursor` 无 `__init__`）。
- `__slots__` 只留 `_disabled_items/_hover_index/_index/_last_width/_spans/disabled/glyphs`；`theme/styles/focused/hover`
  全部由 Widget 提供，子类槽只留 `tabs` 或 `_pending/items`。子类 `revision()` 从“六个解析 style + `_theme`”改为 `theme/styles`。

**调用点清单（`rg` 扫描 + 实测）**
- 改了：`demo/shell.py::mount_catalog`（`NavList(focused=False)` -> 构造后 `.focused = False`）；
  `demo/topics/components_data.py::_tabs`（`Tabs(focused=False)` -> 先构造 `unfocused` 再赋值）；
  `tests/widgets/test_navigation.py`（Tabs/NavList 的 `active_style/disabled_style/focused=` -> `Styles(...)` + 构造后赋值）；
  `tests/widgets/test_data.py`（Table 的 `first_column_style/border_style/active_style` -> `Styles(text/borders/rows=...)`）；
  `tests/kernel/test_theme.py`（`List(focused=True)` -> 构造后赋值）。
- 无需改：`widgets/markdown/tables.py` 只传 `aligns/theme`；`demo/topics/{reference,patterns,overview,styling,components_layout,interactions}.py`
  只传 `theme/glyphs/...`；`app/scrollbar.py` 是 pane chrome，不是本族。
- 坑：`tests/kernel/test_theme.py` 不在工单允许清单，但它是 `List(focused=True)` 的唯一库外调用点；
  删除参数后必改，按“更新所有调用点”最小处理（仅构造方式，断言不变）。

**偏差与取舍**
- NavList 的 `bar_style/bar_active_style` 没有照工单字面映射到 `content.accent/controls.focus`，而是保持旧默认
  `text.muted/content.accent`（2.0 W2b handoff 的同一映射）。字面映射会把活动 rail 的 SGR 从“accent 前景”
  改成“下划线”，违反“默认渲染逐字节不变”；golden 只比文本所以两种都过，但选了守字节的一种。
- Tabs 的 indicator 按工单用 `controls.focus`；默认值是 `Style(underline=True)`，与旧的 `content.accent`
  合并结果逐字节相同（accent fg + underline）。
- `ContextMenu` 本来就没有显式 style 参数（只 `**kwargs` 转发），因此没有可删的转发；`styles` 经 `**kwargs` 直达 Select。
- 未做 Table wrap（W5a）、未做 ScrollView bar 输入（W5b）；`ScrollView.scrollbar` 属性名保留。
- 未加新测试（工单要求）；`List.theme = Theme.light()` 手工验证过 live theme 重绘，未落成测试。
## C. 指针
- `src/motui/widgets/strip.py`（槽与 MRO）、`tabs.py::_layout`、`menubar.py::_style_of/_layout`、
  `navlist.py::_band/render`、`scroll.py::revision/render`。
- `src/motui/widgets/table.py::_grid`（组提升点与 band 解析）、`list.py::_row/revision`、`tree.py::_node_row`。
- 活主题回归样板：`tests/widgets/test_choice.py::test_a_theme_assignment_repaints_the_next_render`。
- 稳定区（下一波不必重读）：`core/**`、`app/**`、`widgets/markdown/**`、全部 golden、`tools/**`、`docs/**`。
