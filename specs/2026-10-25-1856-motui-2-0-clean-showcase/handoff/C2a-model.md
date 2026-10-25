# C2a · generation/touch、Theme.group、RowSpan · 交接

> 分支 `2.0-clean/c2a-model`；起点 `2e55970`；4 个工单 commit + 本 handoff。

## A. 交付面

- **Section 缓存键**：`(width, max_height, widget.generation)`；`Section._cacheable = hasattr(widget, "generation")`，
  `Section.generation -> int | None`。纯 `Component`（无 generation）每次 fresh；`Widget` 的 generation 由
  `touch()` 沿 `parent` 链递增（`__setattr__` 公开属性自动、`children` 赋值自动）。
- **`_BodyIndex`**：`_BodyEntry.revision` → `generation`；`_sweep` 用整数比较，`None` 每帧重算并走
  `_frame_rows`（一帧仍只 render 一次）。
- **删除**：`Revisioned` Protocol、`Widget.revision()`、全部组件 `revision()/_revision()`
  （action/autocomplete/canvas/choice/collapsible/combobox/decor/dialog/diff/form/indicators/layout/list/
  markdown/menubar/navlist/rows/scroll/table/tabs/text/textfield/tree + demo shell/stage）。
  `Frame.revision()` 保留（结构修订，与行缓存无关）。
- **`TextBuffer`**：新增 `on_change: Callable[[], None] | None`，在 `_changed()`（`_version += 1`）处回调；
  `_TextField.__init__` 设 `self._buf.on_change = self.touch`。内容写入走该钩子；光标/选择移动在
  `_route`、`_moved`、`select_all/clear_selection`、`on_click`、`Editor._step_logical` 里 touch。
- **就地 mutator touch 清单**：`Text/Markdown.on_hover`；`List/Select` 的 index/move/home/end/toggle/
  on_click/on_hover/jump；`MultiSelect/CheckboxGroup` marks；`Table` index/move/click/toggle/hover/
  sort_by/set_widths；`Tree` move/click/_fold/filter/jump/hover；`Tabs/MenuBar/NavList`（strip 基类）；
  `ScrollPanel.scroll_to/scroll_to_x/reveal`；`Canvas` 全部写入（`_touch` 内）；`Spinner.advance`；
  `Slider` 四个 setter/move/click/hover；`ProgressBar.fraction`；`Collapsible.on_hover`；`Dialog.index/
  _take_button`；`Form.focus/move/on_action`；`TextBuffer` 内容钩子。
- **Theme.group**：`Theme.group(name, styles=None)` 是唯一解析（override 整组优先，否则主题组）；
  `Widget.group` 调它；删除 `Themed/pick`。`Find`、`_MountedOverlay`、`RegexHighlighter` 不再继承，
  各自保存 `_theme`（None → `DEFAULT_THEME`）。
- **RowSpan**：`kernel/layout.py` 新增 `@dataclass(frozen=True, slots=True) RowSpan(first, last)`；
  `kernel/hit.py` 只留 `Hit`；`kernel.__init__` 从 layout 导出；`Runtime/Workspace.visible_range` 返回它。
- **门禁（真实输出）**：
  ```
  pytest -q -p no:cacheprovider -> 1604 passed in 20.12s
  golden / semantic --check     -> 57 / 57 topics match
  framebench                    -> e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da
  python -m motui < /dev/null   -> exit 0, 70 lines；--pages -> exit 0, 4059 lines
  quickstart/snake/dashboard/wide_table --headless -> 全部 exit 0
  ruff / pyright                -> All checks passed / 0 errors, 0 warnings
  lint-imports / api --check    -> 4 kept, 0 broken / 185 names match
  growth.py (full)              -> pytest/golden/api pass, OK
  ```
- **性能**：200 帧同尺寸布局 7 块文档，`Section._refresh` 1005 次、`_render` 7 次，命中率 99.3%；
  单块 `List.move` 只重渲 1 块；流式 Text 50 帧 50 次 render。framebench 对基线
  (`2e55970` export)：stream-single 1.0→1.0/1.1、stream-split 5.5→5.7-5.9、stream-paragraph 1.1→1.1、
  replay 503/650→439-471ms；无 >10% 劣化，回放更快。

## B. 过程、风险与 C2b

- **内部行记忆**：`Table._memo_generation`、`_TextField._memo_generation` 直接键 generation
  （原 `_revision` 快照删除）；任何 touch 都使记忆失效，捕获 `wrap`/`cell_wrap` 等策略字段。
- **公开 list 的就地编辑**：`Table.rows`、`List.items/options`、`Select.options`、`Sparkline.values`
  是宿主自己的 list，`append`/改写后必须 `touch()`（Table 文档已改写成该契约，测试覆盖
  `rows.append()+touch()`）。赋值整个 list 仍自动 touch。
- **共享子组件**：generation 冒泡依赖 `children` → `parent` 唯一父链；同一个 widget 被两个容器挂载时
  只有最后一个父容器收到 touch。现有测试/示例无共享；如未来需要，容器需自己 touch。
- **Sparkline**：当前 API 没有 `set_values/plot`（工单描述与代码略有出入），`values` 就地改需 touch。
- **C2b（ScrollState）清单**：`widgets/scroll.py`（`_state = ScrollState(offset=...)`、`scroll_to/reveal/
  on_drag`、`ScrollPanel.scroll_state`）、`kernel/layout.py`（`ScrollState`/`Scrollable`/`Viewport`）。
- **坑**：`TextBuffer.on_change` 只覆盖内容，光标移动不会触发；`_TextField` 的 hook/直接方法必须
  自己 touch（已做）。`Section._cacheable` 不能用 isinstance（kernel 不能 import widgets），用
  `hasattr(widget, "generation")`。`Dialog/Form` 的字段组件是 `FormField`/按钮，字段 `error` 不是
  Widget 属性，`Form.on_action` 显式 touch。
- **遗留文字**：`kernel/selection.py` 与 `tests/golden/README.md` 仍有 "revision" 叙述，二者在禁触清单；
  `frame.py` 的 `revision` 是结构修订，保留。`app/find.py` 已改为 generation。

## C. 路径、提交与行数

关键路径：`src/motui/kernel/{document,layout,hit,theme,__init__}.py`、`src/motui/widgets/**`、
`src/motui/app/{find,overlays,runtime,workspace}.py`、`src/motui/demo/{shell,stage}.py`、`tests/**`、
`tools/api-2.0.txt`。

commit：`7cde49d` kernel 缓存键 generation · `24660ef` widgets touch/删除 revision ·
`32ba20a` Theme.group/删除 Themed · `ea78f75` RowSpan · 本 handoff commit。

行数（wc -l，净变化）：document 538→500、layout 998→1006、theme 536→514、textfield ~1240→1274、
table ~1390→1380；全仓 928 行删除 / 221 行新增（widgets 为主），无新文件除 invalidation 测试。
