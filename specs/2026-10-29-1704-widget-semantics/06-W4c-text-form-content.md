# W4c · Text / Field / Form / Dialog / Content 迁移

> 分支 `w2.1.2-w4c-text-form`；起点 main @ `2eb381f` + `57efe5f` + API 快照
> （W4b 已合并）。写入范围：`src/motui/widgets/{text,textfield,form,dialog,
> collapsible,indicators}.py`、`src/motui/widgets/markdown/component.py`、
> `tests/widgets/{test_text_widget,test_markdown,test_editing,test_form,
> test_dialog,test_containers,test_indicators}.py`、
> `tests/widgets/test_contract_text_form.py`（新）、`tests/test_invariants.py`、
> `tests/demo/test_scenes.py`、`src/motui/demo/sections/{components,dashboard,
> gallery}.py`。
> 最高约束：**W4c 结束时 semantic golden 的 9 个场景行文本与 SGR 都不变**。

## 目标

把 Text/Markdown、TextField、Form、Dialog、Collapsible、ProgressBar/Slider
迁到统一契约：构造顺序、`ResultWidget`/`CursorWidget`/`ActionWidget` 的
pending 规则、`activate`/`toggle`/`select`/`move`、`take` 返回、`ProgressBar`
的 `value/maximum`、`Slider.take` 删除。Input/Editor 的 TextBuffer 键表是
明确例外，不迁到 CursorWidget。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §0–§6 →
  `handoff/W4a-deepseek-v4.1-flash.md` → `handoff/W4b-deepseek-v4.1-flash.md`
  → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
uv run pytest -q tests/widgets/test_text_widget.py tests/widgets/test_markdown.py tests/widgets/test_editing.py tests/widgets/test_form.py tests/widgets/test_dialog.py tests/widgets/test_containers.py tests/widgets/test_indicators.py
uv run python tools/semantic.py --check
```

- 基线事实：1791 tests；semantic 9/9；`api.py --check` 243 names match；
  `tools/api-2.1.txt` 由 lead 独占。
- 稳定区（勿重读）：`widgets/base.py`、`action.py`、choice/list/table/tree/
  tabs/menubar/navlist/strip、`app/`、`kernel/`。
- W4b 已定：`Select.take()` 返回 value；`Table(rows, headers=...)`；
  `TreeNode.open`；`Tabs/MenuBar/NavList.items`；`ComboBox.open` property。
- 已知约束：
  - `Dialog` 用 `_NO_RESULT` sentinel 区分“取消（合法 None）”和“无决定”；
    迁移到 `ResultWidget` 时用基类 `_MISSING`，`_take_decision` 读
    `_result is _MISSING`。
  - `Form` 的 `_value` 提取顺序是 `value/text/checked/selected/marked`，不读
    `take()`；提交结果才是 `take()`。
  - `ProgressBar.fraction` 只读派生；demo 的 `self.x.fraction = ...` 必须
    改成 `value`。
  - `Slider.take` 删除；`activate()` 不再写 pending，只回答是否可用。
  - Input/Editor 的 `keymap` 是 TextBuffer 的 property；`Widget.__init__`
    已有 Mapping 守卫。构造尾部按 interfaces 表的顺序：
    `glyphs, theme, styles, keymap, read_only, wrap`（Editor 无 glyphs）。
  - `Text`/`Markdown` 的 take 是 inline action payload（str 或 None）。
  - `Collapsible` 用 `ActionWidget`：`activate()→toggle()`，toggle 翻转
    `open` 并 `_emit(open)`；`hint` 由基类提供。
  - `Form`/`Dialog` 是 `focus_scope`；`on_key` 的 tab/enter 处理保留。

## 工单（按序执行，每项一个 commit）

### T1 Text / Markdown → ResultWidget

- `text.py`：`Text(ResultWidget)`；删除 `_pending`/`take`；`on_click` 的
  inline action hit 改为 `self._emit(payload)`。构造不变。
- `markdown/component.py`：`Markdown(ResultWidget)`；同样替换 `_pending`；
  `on_click` 的 inline action hit 用 `_emit`。构造不变。
- 验证：`uv run pytest -q tests/widgets/test_text_widget.py tests/widgets/test_markdown.py`。

### T2 Input / Editor 构造顺序

- `textfield.py`：`Input(text="", *, prompt=None, placeholder="", mask="",
  glyphs=GLYPHS, theme=None, styles=None, keymap=None, read_only=False,
  wrap=WrapMode.OVERFLOW)`；`Editor(text="", *, placeholder="", mask="",
  theme=None, styles=None, keymap=None, max_rows=None, read_only=False,
  wrap=WrapMode.WORD)`。
- 只改关键字顺序和 docstring；`TextBuffer` 键表、`keymap` property、
  `text` 状态、`on_key` 行为不变。无 take。
- 验证：`uv run pytest -q tests/widgets/test_editing.py`。

### T3 Collapsible → ActionWidget

- `Collapsible(body, *, title="", open=True, glyphs=GLYPHS, disabled=False,
  theme=None, styles=None)`；`Collapsible(ActionWidget)`。
- `activate()` → `toggle()`；`toggle()`：disabled → False；翻转 `open`；
  `_emit(self.open)`。`on_click` 只在 row 0 上 `activate()`；`take` 继承。
- 删除本地 `_pending`/`take`/`on_action`/`hint` slot（ActionWidget 提供）。
- 验证：`uv run pytest -q tests/widgets/test_containers.py -k collapsible`。

### T4 Form / Dialog → CursorWidget

- `Form(CursorWidget)`：
  - 钩子：`_entry_count=len(fields)`、`_entry_at=fields[index]`、
    `_cursor_enabled=True`、`_cursor_wraps=False`。
  - `selected` 返回 `Field`；`index` 用基类；`select`/`move` 覆盖为
    `super()` 后 `_sync_focus()`；`focus(target)` 保留：str 查 name 后
    `select(position)`，int 直接 `select`。
  - `activate()`：原 `on_action("activate")` 的提交体；成功 `_emit(values)`，
    失败 `_clear_result()` 并返回 False。`on_action` 用基类。
  - 删除 `_pending`/`take`；`on_key` 的 tab/up/down/enter 改用 `self.move`/
    `self.activate`。
- `Dialog(CursorWidget)`：
  - 构造 `Dialog(body, *, title="", buttons=(), danger=False, width=None,
    align="center", border=None, shade=True, frame=True, glyphs=GLYPHS,
    theme=None, styles=None)`。
  - 钩子：`_entry_count=len(buttons)`、`_entry_at=buttons[index]`、
    `_cursor_enabled=True`、`_cursor_wraps=False`。
  - `activate()`：`_take_button(self.index)` 后 `_emit(spec.value)`；
    `on_key` escape `_emit(None)`，enter `activate()`，tab/right `move(1)`，
    s-tab/left `move(-1)`；`take` 继承；`_take_decision` 用 `_MISSING`；
    `_arm_result` 用 `_clear_result`；`focused_button` 返回 `selected`。
  - 删除本地 `_NO_RESULT`/`_pending`/`take`。
- 验证：`uv run pytest -q tests/widgets/test_form.py tests/widgets/test_dialog.py`。

### T5 ProgressBar / Slider

- `ProgressBar(value=0.0, *, maximum=1.0, label="", width_chars=None,
  glyphs=GLYPHS, theme=None, styles=None)`：
  - `maximum` 必须 > 0，否则 `ValueError`；`value` clamp 到 `[0, maximum]`；
    `fraction` 只读 `value / maximum`；删除 `_fraction` setter。
  - render 用 `self.fraction`；测试 `bar.value`/`bar.fraction`。
- `Slider`：删除 `_pending`/`take`；`activate()`：disabled → False，否则
  True（不写结果）；`on_action("activate")` → `activate()`；`on_key` enter
  调 `activate()`；`move`/`on_click` 不再清 pending（没有 pending）。
- 验证：`uv run pytest -q tests/widgets/test_indicators.py`。

### T6 Demo / invariants / 契约测试

- `demo/sections/components.py`：`Dialog(title, body, buttons)` →
  `Dialog(body, title=..., buttons=...)`；`radio.index` 仍可用。
- `demo/sections/dashboard.py`、`gallery.py`：`ProgressBar.fraction = x` →
  `value = x`（maximum 默认 1.0）。
- `tests/test_invariants.py`：`Dialog`/`ProgressBar` 构造更新；
  `ProgressBar(0.4)` 可保留（value）。
- `tests/demo/test_scenes.py`：若有 `fraction`/`Dialog`/`Collapsible` 调用，
  同步。
- `tests/widgets/test_contract_text_form.py`（新）：构造签名、状态
  （`text`/`value`/`open`/`index`/`selected`）、动词、take、pending 规则、
  ProgressBar `fraction` 只读、Slider 无 take、Dialog cancel None。
- 验证：`uv run pytest -q tests/widgets/test_contract_text_form.py tests/test_invariants.py tests/demo`。

## 验收

1. 全量 `uv run pytest -q -p no:cacheprovider` 全绿（贴用例数/失败项）。
2. `uv run ruff check .`、改动文件 no-exclude ruff、`pyright`、`lint-imports`
   全绿。
3. `uv run python tools/semantic.py --check` 全绿（硬门槛）。
4. `uv run python tools/framebench.py` 的 `render-hash` 不变。
5. `api.py --check` 会因构造签名变化失败；贴差异，不改快照。

## 禁触清单

`widgets/base.py`、`action.py`、`choice.py`、`autocomplete.py`、`combobox.py`、
`menubar.py`、`list.py`、`table.py`、`tree.py`、`tabs.py`、`navlist.py`、
`strip.py`、`layout.py`、`canvas.py`、`pixel_canvas.py`、`drawing.py`、
`app/`、`kernel/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W4c-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W4c-<agent>.md`：Form/Dialog 的钩子与 sentinel、ProgressBar
value/fraction 规则、Collapsible 的 toggle、给 W5 的样式钩子提示、api 差异。

## 最终报告

同 W1 模板。
