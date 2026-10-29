# 2.1.2 全组件语义一致性重构

> 启动：2026-10-29 17:04（UTC+8）
> 分支策略：每波独立 worktree + 分支，合并回 main；不 push、不打 tag。
> 发版：2.1.2（语义重构，不是功能版本）。

## 目标

把 46 个 `motui.widgets` 公开组件、46 个 facade 名背后的构造、状态、动词、结果、
样式、键位、容器/绘制七套语义收敛成一套全局契约。旧名直接删除，不做兼容层；
迁移表写进 `docs/MIGRATION.md`。

成功的定义：

1. 同一概念全库只有一个名字（`index` / `selected` / `marked` / `value` /
   `checked` / `open` / `text`）。
2. 同一手势全库只有一个动词（`activate` / `toggle` / `select` / `move` /
   `advance` / `take`），且 `on_action` 只路由这组名字。
3. `take()` 在同类组件上返回同类值；`selected` 是状态，`take` 是决定。
4. 构造规则可机械检查：主内容唯一位置参数，其余 keyword-only，尾部
   `glyphs, theme, styles, keymap`。
5. 样式只有“主题角色 + 控件状态 overlay”，没有 per-component recipe。
6. 1663 个用例不降覆盖；删除的是重复的能力/keymap/height-budget 断言。
7. W1–W4 的渲染字符零变化；W5/W6 只改样式字节或有意的 demo 结构。

## 非目标

- 不合并 `Canvas` / `PixelCanvas`；只统一生命周期。
- 不做通用 raster 图层栈；ART/FILL 两层够用。
- 不做 CSS/flexbox；布局仍是 widget。
- 不做 per-component theme recipe（`theme.button` 这类）。
- 不做 measure/render 两阶段，不做 `Expanded`；绘制舞台尺寸由宿主定。
- 不把 demo 改成桌面应用 chrome；保持 splash + tile grid + 全屏场景语言。
- 不新增 `marked_values`；宿主自己把 `marked` 索引映射成值。

## 已拍板的决定

1. 严格构造：`Table(rows, headers=...)`、`Dialog(body, title=..., buttons=...)`、
   `Collapsible(body, title=...)`、`Canvas(*, width=...)`。
2. Navigation 全部可激活：`Tabs`/`NavList`/`Tree` 增加 `activate()`/`take()`；
   `Slider.take()` 删除。
3. `open` 统一为状态属性；删除 `expanded`/`is_open` 和 `open()`/`close()`
   方法，用 `toggle()` 或赋值。
4. Button 默认 neutral 底板、不加括号；Input/Editor 加字段底板；
   Panel 保持 border-only。
5. 测试目标：删除约 1/4 重复用例；docstring 体量减半；纯改名不新增测试。

## 组件模型

```
Component（只有 render）
└─ Widget（树、generation、theme/styles、keymap、hooks）
   ├─ ResultWidget（_pending / take / 清除规则）
   │  ├─ ActionWidget（Button / Checkbox / Link）
   │  ├─ CursorWidget（index / selected / select / move）
   │  │  ├─ Choice（Select / MultiSelect / RadioGroup / CheckboxGroup /
   │  │  │           Autocomplete / ComboBox / ContextMenu）
   │  │  └─ Navigation（Tabs / MenuBar / NavList / List / Table / Tree）
   │  ├─ Form / Dialog
   │  └─ Text / Markdown（inline action 结果）
   ├─ Drawing（尺寸 / resize / surface / 纯 render）
   │  ├─ Canvas
   │  └─ PixelCanvas
   └─ Container（children / child_at）
      ├─ Row / Column / Stack
      ├─ Padding / Panel / Align / ScrollPanel
      └─ Collapsible
```

共享件只做四件事：`ResultWidget` 收 `_pending`/`take`；`CursorWidget` 收
`index`/`selected`/`select`/`move`/禁用跳步/pending 清除；`ActionWidget` 收
`disabled`/`hint`/`activate`/`on_action`；`Keymap` 收类默认表 + 实例副本。

## 波次表

| 波次 | 分支 | 内容 | 写入范围（文件级） | 依赖 |
|---|---|---|---|---|
| W0 | `main` | 本 spec 组 | `specs/...` | — |
| W1 | `w2.1.2-w1-overlay` | `Line.overlay` / `Surface.overlay` | `kernel/cell.py`, `tests/kernel/test_cell.py` | W0 |
| W2 | 同 W1 分支 | `Stack` / `Align` + 命中策略 | `widgets/layout.py`, `widgets/__init__.py`, `tests/widgets/test_containers.py` | W1 |
| W3 | `w2.1.2-w3-drawing` | `Drawing` 基类、Canvas/PixelCanvas 生命周期、palette 派生 | `widgets/drawing.py`(新), `canvas.py`, `pixel_canvas.py`, `pixel/palette.py`, `tests/widgets/test_canvas.py`, `test_pixel_canvas.py`, `tests/pixel/test_palette.py`, `tests/test_invariants.py`, `demo/sections/motion/scene.py`, `demo/sections/splash/scene.py`, `demo/sections/terminal.py` | W0 |
| W4a | `w2.1.2-w4a-foundation` | `ResultWidget`/`ActionWidget`/`CursorWidget`/`Keymap` 描述符、focus space | `widgets/base.py`, `widgets/strip.py`, `widgets/action.py`, `app/focus.py`, `tests/widgets/test_base.py`, `test_action.py`, `test_contracts.py`, `tests/app/test_focus.py` | W1–W3 合并后 |
| W4b | `w2.1.2-w4b-choice-nav` | Choice/Navigation 迁移 | `choice.py`, `autocomplete.py`, `combobox.py`, `menubar.py`, `list.py`, `table.py`, `tree.py`, `tabs.py`, `navlist.py`, `strip.py`, `tests/widgets/test_choice.py`, `test_autocomplete.py`, `test_combobox.py`, `test_menubar.py`, `test_navigation.py`, `test_data.py`, `test_contract_choice_nav.py`(新), `tests/test_invariants.py`, `demo/sections/components.py`, `demo/sections/gallery.py` | W4a |
| W4c | `w2.1.2-w4c-text-form` | Text/Field/Form/Dialog/Content 迁移 | `text.py`, `markdown/component.py`, `textfield.py`, `form.py`, `dialog.py`, `collapsible.py`, `indicators.py`, `tests/widgets/test_text_widget.py`, `test_editing.py`, `test_form.py`, `test_dialog.py`, `test_containers.py`, `test_indicators.py`, `test_contract_text_form.py`(新), `tests/test_invariants.py`, `demo/sections/components.py`, `demo/sections/dashboard.py`, `demo/sections/gallery.py` | W4b 合并后 |
| W5 | `w2.1.2-w5-styles` | surfaces/controls、ButtonKind、字段底板、焦点、flat | `kernel/theme.py`, `widgets/action.py`, `textfield.py`, `dialog.py`, `tabs.py`, `menubar.py`, `indicators.py`, `pixel_canvas.py`, `decor.py`, styles 相关测试、semantic goldens | W4b/W4c |
| W6 | `w2.1.2-w6-demo` | splash 用 Stack/Align + 真按钮；components modal 用 Stack | `demo/sections/splash/`, `demo/sections/components.py`, `tests/demo/`, semantic goldens | W5 |
| W7a | `w2.1.2-w7a-docstrings-widgets` | docstring 减半：widgets/pixel/testing（6312→≤3150） | `src/motui/widgets/**`, `pixel/**`, `testing/**` | W6 |
| W7b | `w2.1.2-w7b-docstrings-kernel-app` | docstring 减半：app/kernel/terminal/demo（6692→≤3340） | `src/motui/app/**`, `kernel/**`, `terminal/**`, `demo/**`, root | W6（与 W7a 并行） |
| W7c | `w2.1.2-w7c-docs` | CONTRACT/WIDGETS/ARCHITECTURE/README + ADR 027–030 | `docs/**`, `README.md` | W6（与 W7a/W7b 并行） |
| W7d | `w2.1.2-w7d-test-trim` | 测试去重 1838→~1380 | `tests/**` | W6（与 W7a/W7b/W7c 并行） |
| W8 | `w2.1.2-w8-release` | 版本、CHANGELOG、MIGRATION、release notes、API 快照、终验 | `pyproject.toml`, `src/motui/__init__.py`, `CHANGELOG.md`, `docs/MIGRATION.md`, `docs/releases/2.1.2.md`, `tools/api-2.1.txt`, `uv.lock`(如引用) | W7 |

并行规则：W4b 与 W4c 共享 `demo/sections/components.py`（Table take 与
RadioGroup/Dialog 构造），因此**串行**执行：W4b 合并后再派 W4c。两波都不写
`tests/widgets/test_contracts.py`（W4a 独占）。W5 必须等 W4b/W4c 合并后再动，
避免样式与构造在同一文件反复冲突。

## 全局不变量

1. **构造**：主内容唯一位置参数；配置/结构字符/主题/键位全部 keyword-only；
   尾部顺序 `glyphs, theme, styles, keymap`。例外：`Diff(before, after)`、
   `Field(name, component)`、`ButtonSpec(label, value)`、`Option(label, value)`、
   `StatusLine(*, left, right)`、`Divider(*, label)`、`Sparkline(values, *)`、
   `Form(fields)`、`Row/Column/Stack/Padding/Align/ScrollPanel(child/children)`。
2. **状态**：`index` 为 int（空集合为 0）；`selected` 为项对象或 None；
   `marked` 为 `MarkSet`（源数据索引）；`value` 为标量；`checked` 为 bool；
   `open` 为 bool；`text` 为 str。`selected` 只读；`index` 由移动门改写。
3. **动词**：`activate()/toggle()/select(index)/move(delta)/advance()/take()`
   全部返回 bool 或结果值；`on_action` 只路由
   `prev/next/first/last/page_prev/page_next/activate/toggle/open/close`。
4. **结果**：只有 `activate`/`toggle` 写 pending；`select`/`move`/`open`/`close`
   清 pending；`take()` 读一次即清空；合法 `None` 用内部 sentinel 区分。
5. **样式**：主题角色组 + `ControlStyles` 状态 overlay；没有 per-component
   recipe；`Theme.flat()` 覆盖所有新 surface。
6. **键位**：`CURSOR_KEYMAP` 为 up/left=prev、down/right=next、home=first、
   end=last、page_up/down=page_prev/next；`ACTIVATE`（enter/space）由 focus
   层统一回退；组件只绑自己特有的键。
7. **容器/绘制**：单子 `child`、多子 `children`、语义复合 `body/fields/buttons`；
   只有占格容器实现 `child_at`；`Drawing.render` 只裁剪不改尺寸。

## 回归红线

- W1–W4 不允许改变任何组件的渲染字符；`tools/semantic.py --check` 必须在
  W1–W4 保持全绿（W3 的 Drawing 生命周期改动也不得改变现有 scene 输出）。
- W5 允许 SGR 字节变化；重录 golden 时必须在 handoff 记录每个场景的行文本
  未变（只允许 `\t` 后的 runs 变化）。W6 允许 splash/components 的行变化。
- `motui.kernel` 仍然无 I/O、不 import 上层；`motui.widgets` 不 import
  `motui.app`/`motui.terminal`。
- 不新增 alias、shim、forwarding module、deprecated 参数；旧名直接删。
- 每波结束 `pytest`、`ruff`、`pyright`、`lint-imports` 全绿。

## 门禁

每波默认：

```
uv run pytest -q -p no:cacheprovider
uv run ruff check .
uv run pyright
uv run lint-imports
uv run python tools/semantic.py --check
```

触及公开签名/导出的波次额外：

```
uv run python tools/api.py --update     # 由 lead 在 main 上执行
uv run python tools/api.py --check
```

触及渲染/绘制/组合的波次（W1–W3、W5、W6、W8）额外：

```
uv run python tools/framebench.py
```

`tools/api-2.1.txt` 由 lead 独占：worker 只报告 `api.py --check` 的差异，
不提交快照；lead 合并后统一 `--update` 并提交。

## 共享文件所有者

| 文件 | 所有者 |
|---|---|
| `specs/...` | lead |
| `tools/api-2.1.txt` | lead |
| `src/motui/widgets/__init__.py` | W2（Stack/Align 导出）；W4a 如需导出基类再加 |
| `tests/widgets/test_contracts.py` | W4a |
| `tests/widgets/test_contract_choice_nav.py` | W4b（新文件） |
| `tests/widgets/test_contract_text_form.py` | W4c（新文件） |
| `tests/golden/semantic/*` | W5/W6 各自重录，handoff 记录 |
| `CHANGELOG.md` / `docs/MIGRATION.md` / `pyproject.toml` / `src/motui/__init__.py` | W8 |

## 接口索引

- 目标契约：`ref/interfaces.md`
- 仓库地图：`ref/repo-map.md`
- 迁移矩阵：`ref/interfaces.md` §9
- 每个 worker 的交接包：`handoff/W<N>-<agent>.md`

## 状态

- [x] W0 spec 组
- [x] W1 kernel overlay（`2bda31a` 合并）
- [x] W2 Stack/Align（`2bda31a` 合并）
- [x] W3 Drawing（`11a4d28` 合并，`314c973` 对账）
- [x] W4a（`617377b` 合并，`ae2e88d` CursorWidget 扩展）
- [x] W4b（`2eb381f` 合并，`57efe5f` take 契约修正）
- [x] W4c（`01266d2` 合并）
- [x] W5（`fcc0108` 合并）
- [x] W6（`c692c0b` 合并）
- [x] W7a docstrings widgets/pixel/testing（6312→2183）
- [x] W7b docstrings app/kernel/terminal/demo（6692→1604）
- [x] W7c docs/ADR/README
- [x] W7d test trim（1838→1383）
- [x] W8
