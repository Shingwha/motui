# Spec choice-architecture · W4 demo 重建 + 文档对位 + 门面重钉（波次 W4）

> ✅ 已合并 2026-10-17 @ `arch4-demo`（tip `6fead4e`）→ main `a91629c`；1472p/1s，
> golden 12 页，apidoc 186，hash 未动。根门面最终 33 名（本单 T4 文案 31 为笔误）。
> 分支 `arch4-demo`；前置：W3（已合并：`Modal`、`interaction/palette.py`、`Prompt`、
> `interaction/{overlays,scrollbar,find}.py` 在位，顶层 `chrome.py` 已删）；
> 深读：`00-overview.md`（红线、删除清单）、`docs/COMPONENTS.md`（全篇，本波重写它）、
> `docs/DESIGN.md` 的层结构图与 naming charter。
> **最高约束：本轮是收尾——除本单列明的演示页新增/改版与文档重写外，不引入任何新的
> 库行为；golden 全量重录必须逐页解释。**

## 目标

新组件的演示入口补齐（对话框、多选、掩码、组合框），demo 的模态路由切到 `Modal`，
`docs/COMPONENTS.md` / `docs/API.md` / `docs/DESIGN.md` / README 的组件表对位到终态，
根门面重钉 31 名，golden 11 → 12 页重录。

## 工单（按序执行，每项一个 commit；每步之间跑 `uv run pytest -q`）

### T1 `widgets/combobox.py`：`ComboBox`（新组件，最后一个补齐件）

```python
class ComboBox(Themed):
    """An editable Input over a filtered dropdown -- the form's pick-or-type.

    ``options`` are the candidate :class:`Option` rows; the field is the
    component's own :class:`~motui.widgets.textfield.Input` (``.input``),
    and while the dropdown is open the ``Autocomplete`` of the field's text
    (``.list``) is painted under the field's row.  ``open()``/``close()``/
    ``is_open`` drive it; ``handle`` routes: ``down``/``up`` step the list
    (consumed, cursor wraps like every menu), ``enter`` takes the
    highlighted option's value into ``chosen``, closes and writes the
    option's label back into the field, ``escape`` closes with ``chosen``
    ``None``; every other event is the field's, and a field change
    re-filters the list.  ``chosen`` is read once by the host and reset
    (the library convention).  ``render(width)`` is the field's rows; the
    dropdown paints through a host-mounted :class:`~motui.interaction.modal.Modal`
    (see the class docstring's recipe) -- a widget lays out rows, the
    modal owns the screen.
    """
    __slots__ = (...)
    input: Input
    list: Autocomplete
    chosen: object | None
    is_open: bool
    def __init__(self, options=(), *, text="", max_rows=8, theme=None, max_drop_rows=6) -> None: ...
    def open(self) -> None
    def close(self) -> None
    def handle(self, event: Key | Paste) -> bool
    def render(self, width: int) -> list[Line]
```

- 只 import kernel + 同层（`textfield`、`choice`）；**不 import interaction**。
- docstring 写清「宿主把 `Modal(tui, combo.list, anchor=字段行下方一格)` 挂上，`combo.handle`
  先于 `modal.handle` 接键，打开/关闭同步 `modal.open()/close()`」的三行配方——
  这正是 `Modal` 的锚定定位策略的第二个消费者。
- 测试：`tests/test_widgets_combobox.py`（新）：过滤联动、enter 取值回填、escape 关、
  开合前后 `handle` 的消费边界，4–6 条行为断言；**不铺 happy path**。

### T2 demo 页重建

- **新页 `modal`**（`src/motui/demo/pages/modal.py`，注册在 `choice` 之后）：

  ```
  Page("modal", "Dialog and Modal -- a confirm, a prompt and the scrim", modal.page)
  ```

  页上：一个「Delete project」危险按钮 → 打开 `Modal(tui, confirm_dialog("delete the
  project?", danger=True, confirm_text="Delete", cancel_text="Cancel"))`；一个「Rename…」
  → `prompt_dialog("rename", placeholder="new name")`；一个「plain confirm」；
  每次结果的 `chosen` 由页的 `note` 播报（沿用 `PageBody.note`）。
  路由落在页的 `modal` 字段（`PageBody.modal`），session 现有的 `_modal()` 查询无需改。
  页内说明文案讲清：危险对话框默认焦点在取消、`Escape` 恒取消、点击框外取消。
- **`chrome` 页**：`Palette(palette_rows(session.pages), …)` 改成
  `Palette(session.tui, palette_rows(...), …)`；该页 `modal=palette` 的用法随之变成
  「打开即上遮罩」；页内说明与 `script.py` 里该页的回放锚点同步（若锚点因遮罩位移而变化，
  同 commit 修）。
- **`choice` 页**：删掉两个内联 `Confirm` 的展位（对话框去 modal 页），加入
  `CheckGroup`（多选）与 `Select(commit=True)`（表单式选择）两个展位；
  页头文案与 `data.py` 的组件名清单同步（`data.py` 顶部有一份按名字列的清单字符串，
  别忘了它）。
- **`data` 页**：`Table` 与 `List` 各加一个标记展位（**W4 同时给 `Table`/`List` 加
  `marked: MarkSet` 公开属性 + `space` 切换 + 行首 `mark_prefix`**——这是本组最晚的
  一小步库改动，做法照 `CheckGroup` 的既有渲染：标记行前缀三列、`chosen` 语义不变；
  `Table.revision()`/行缓存要包含标记集合；两个组件各 2–3 条行为断言加到
  `tests/test_widgets_table.py` / `tests/test_widgets_list.py`）。
- **`input` 页**：加 `Input(mask="•")` 与 `ComboBox` 展位（ComboBox 的 Modal 挂法照 T1
  的配方，页的 `modal` 字段按开关切换）。
- **`feedback` 页**：`ShortcutBar`/`StatusLine` 的 import 路径没变（widgets 根名），
  检查即可，不重排页面。
- 每页结尾的 `api_note` 文案同步为新签名（`Select(commit=…)`、`CheckGroup`、`Dialog`、
  `Modal`、`mask`、`ComboBox`）。
- `src/motui/demo/registry.py` 的页数注释（"eleven categories"）改 12；
  `tests/test_demo_protocol.py` 如钉了页数/页名清单，同步更新并补一条 modal 页的行为断言
  （打开→遮罩→`Escape` 后 `chosen is None`→按钮路径 `chosen` 为按钮值）。

### T3 文档对位（本波的重头，全部同 commit）

- **`docs/COMPONENTS.md`**：组件目录两张表按终态重排（`Dialog`/`CheckGroup`/`ComboBox`/
  `Prompt`/`Modal` 各自成行；`Select` 行补 `wrap/commit/multi/marked/window` 五个旋钮；
  `Radio`/`CheckGroup` 标注为 `Select` 预置）；「The dispatch order」一节把 `Modal` 安进
  路由链（chrome → overlays → **modal** → find → gestures → ring → host）并写明
  body-first 的按键路由；「刻意不做」列表加：Tree 多选、Dialog 内嵌表单级联校验、
  Keymap 助记符；`Toasts/Tooltip/Stats/Scrollbar/Palette/Find` 的路径引用全部改新位置。
- **`docs/DESIGN.md`**：层结构图更新（`chrome.py` 消失、`interaction/` 全控制器化、
  `kernel/cursor.py`+`kernel/mark.py` 上树）；naming charter 表补本组新名词条
  （`Modal`/`Dialog`/`CheckGroup`/`ComboBox`/`Prompt`/`CursorWindow`/`MarkSet`）；
  「deliberately out of scope」同步。
- **`docs/API.md`**：`tools/apidoc.py --write` 重生成（FACADES 已在 W3 改好）。
- **`README.md`** quickstart 与组件速览：确认无 `Confirm` 旧用法、无 `chrome` 路径；
  quickstart 可不动代码（`Button`/`Checkbox` 仍在根），只改提法。
- **`CONTRIBUTING.md`**：不须改（规则未变）。
- **`CHANGELOG.md`**：加 `## Unreleased` 段落：Added（Dialog/Modal/Prompt/ComboBox/
  CheckGroup/Input.mask/Table+List 标记）· Changed（Palette 走 Modal、`Radio`/`Autocomplete`
  成为 Select 变体）· Removed（旧 Confirm、`chrome.py`、碎模块）· 每条一句、
  不写版本号（发版另等指令）。

### T4 根门面重钉 + golden 重录

- `src/motui/__init__.py`：import 与 `__all__` 重排——
  **正好 31 名**：`DEFAULT_THEME Button Checkbox Dialog Editor FocusRing Input Key Line
  Link List Markdown Modal MouseEvent Option Palette Paste Pointer Scrollbar Segment
  Select SelectionGesture StatusLine Style TUI Table Tabs Text Theme Toasts Tree
  headless_tui snapshot`（`Modal` 与 `Palette` 来自 `motui.interaction`，
  `Dialog` 来自 `motui.widgets`；按常量/类/函数分组排序）。
- `tests/test_api_root.py`：`ROOT_ALL` 与 `LAYER_ALLS`/`DOWN_LISTED` 重钉；
  `SHED` 的 42 计数与 `DIALOG` 类新词的归属在 commit message 说明。
- `tools/golden.py --update`：12 页全量重录；commit message **逐页**说明变化
  （新增 modal 页、choice/data/input/chrome 页内容位移）。
- `tools/framebench.py`：render-hash 变化逐条解释；若 demo 路数变了，
  按既有约定登记新值。
- demo 三入口复跑：`uv run python -m motui < /dev/null`、`--pages` 均 exit 0，
  `--pages` 输出含 modal 页。

## 验收（完成前自测，报告给真实结论）

1. `uv run pytest -q` 全绿（贴 passed/skipped；新增用例逐条列名）
2. `uv run python tools/golden.py --check` → 12 页全等
3. `uv run python tools/apidoc.py --check` → matches
4. `uv run python tools/framebench.py` 出数并解释 hash
5. demo 两入口 exit 0；`--pages` 含 `modal`
6. 全仓 `grep -rn "Confirm(" src/motui/demo` 只命中新 `confirm_dialog`；
   `grep -rn "motui.chrome\|widgets.palette\|widgets.radio\|widgets.input\b" src tests docs README.md`
   零命中（历史 spec/CHANGELOG 旧条目除外，改不了的不动）

## 禁触清单

`src/motui/kernel/**`、`src/motui/app.py`、`src/motui/keys/**`、
`src/motui/interaction/{focus,pointer,gesture,find,modal,overlays,scrollbar}.py`（只读；
`interaction/palette.py` 也只读）、`src/motui/widgets/**` 除
`widgets/combobox.py`(新) · `widgets/table.py`/`list.py` 的标记增量 ·
`widgets/__init__.py` 加 ComboBox 导出、`tools/**` 除 golden `--update` 与 apidoc `--write`
的产物、`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令与输出）/
偏差与取舍 / 未决问题。阻塞即停，不越界自救。
