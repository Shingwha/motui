# W4c 交接包

> 分支 `w2.1.2-w4c-text-form` / 起点 main @ `558f3ef`（W4a/W4b 已合并）/ 2026-10-29

## A. 自动事实（命令与代码生成）

`git log --oneline main..HEAD`：`0331c54` contract matrix → `1a6940f` progress/slider
→ `cba5178` form/dialog → `2370fa9` collapsible → `e761dd6` text/markdown。

`git diff --stat main...HEAD`：17 files changed, 598 insertions(+), 288 deletions(-)；
新增 `tests/widgets/test_contract_text_form.py`（22 用例）。

门禁（真实输出）：起点 `223 passed` / semantic 9 scenes match；全量
`1812 passed, 1 failed`（仅 `tests/testing/test_api_tool.py::test_check_accepts_the_recorded_surface`，
快照由 lead 在 W8 更新，预期）；`ruff check .` 与 16 个改动文件 `--config "exclude=[]"`
全绿；`pyright` 0 errors；`lint-imports` 5 kept；semantic `9 scenes match`；
framebench `render-hash e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
不变（motion 场景计时随机器波动，hash 是硬指标）。

复现门禁：`uv run pytest -q -p no:cacheprovider`、`uv run ruff check .`、
`uv run pyright`、`uv run lint-imports`、`uv run python tools/semantic.py --check`、
`uv run python tools/framebench.py`、`uv run python tools/api.py --check`。

`api.py --check` 差异（4 行，未改快照）：`motui:Dialog`、`motui.widgets:Dialog`
（body 前移、title/buttons keyword-only）、`motui.widgets:Collapsible`
（body 前移、title keyword-only）、`motui.widgets:ProgressBar`
（fraction→value/maximum）。Text/Markdown/Form/Slider 的公开 shape 未变。

**偏差（必读）**：

1. **T2 零 diff**：`Input`/`Editor` 基线已是目标关键字顺序，故无 commit；`test_editing.py` 86 passed 复核。
2. 写入范围外唯一机械改动：`tests/app/test_modal.py:247` 的 Dialog 构造；不改则全量门禁红。禁触清单零 diff。
3. `demo/sections/components.py` 的**代码示例字符串**仍写旧 `Dialog(...)`：改它会改变 components 场景 golden，与“9 场景不变”冲突，留给 W8/文档波。
4. Markdown 构造尾部与 interfaces 的“尾部 glyphs/theme/styles”表述不完全一致（基线 `theme, styles, highlighter, glyphs, ...`）；T1 明确“构造不变”。
5. `ProgressBar` 的 `int(round(...))` → `round(...)`（RUF046，等值），渲染字节由 semantic 9/9 证明不变。

## B. 只存在于脑子里的东西

1. **Form 钩子**：`_entry_count=len(fields)`、`_entry_at=fields[i]`、`_cursor_enabled=True`、`_cursor_wraps=False`；`selected` 是 `Field`。构造器 `_sync_cursor(); _cursor.index = clamp(index)` 直接安装初始 index（不走 select/不清 pending）；`select`/`move` 覆盖为 `super()` 后 `_sync_focus()`；`focus(name)` 查名后走 `select`。

2. **Form.activate**：校验→写回 `Field.error`→`touch()`；失败 `_clear_result()` 且 False；成功 `_emit(values)` 后调 `on_submit`。`on_action` 用基类；`on_key` 的 tab/down、s-tab/up、enter 直接调 `move`/`activate`。

3. **Dialog 钩子**：`_entry_count=len(buttons)`、`_entry_at=buttons[i]`；`selected` 是内部 `Button`，`focused_button` 返回它。构造器 `_sync_cursor(); _cursor.index = _default_index()` 保留 D3；`select`/`move` 覆盖后 `_sync_focus()`。

4. **Dialog 结果**：`_take_button` = 按钮 `on_action("activate")` + `button.take()` + `_emit(spec.value)`；`activate()` 无按钮返回 False；escape `_emit(None)`、enter `activate()`、tab/right/left `move(±1)`（端点 False）。`_take_decision`/`_arm_result` 改读写基类 `_MISSING`/`_clear_result()`；`take` 继承。取消（合法 None）与“无决定”靠“是否调用过 take / `_take_decision().made`”。

5. **Collapsible**：ActionWidget；`activate()→toggle()`，`toggle()` disabled 拒绝、翻转 `open`、`_emit(open)`；`on_click` 仅 row 0 走 `activate()`；本地 `_pending`/`take`/`on_action`/`disabled` slot 已删。

6. **ProgressBar**：`maximum > 0` 否则 ValueError（构造与 setter）；`value` 构造/赋值都 clamp 到 `[0, maximum]`；`fraction` 只读派生；`maximum` setter 会 re-clamp value。render 读 `self.fraction`。

7. **Slider**：`_pending`/`take` 删除；`activate()` 只回答可用性（disabled→False），不写结果；`move`/`on_click` 不再清 pending；`on_key` enter 与 `on_action("activate")` 都委托 `activate()`。`Widget.take()` 仍存在恒返回 None（“无结果”看行为，不看 hasattr）。

8. **Text/Markdown**：`ResultWidget`；`on_click` 命中 inline action 用 `_emit(payload)`；未命中不写。

9. **给 W5**：Dialog danger 按钮仍用 `Styles(controls=replace(...base=danger))` + `ButtonSpec(label, value, styles, danger)`；待换 `kind=ButtonKind.DANGER` + `surfaces.danger`/`action_band`。Collapsible/Form/Dialog 仍读 `content.accent`/`controls.focus`/`surfaces.hover`，未接 `ControlStyles.overlay`（§6）。

## C. 指针

- 改写：`widgets/{text,markdown/component,collapsible,form,dialog,indicators}.py`；`Text/Markdown._emit`；`Form` 钩子与 `activate`；`Dialog` `_take_button`/`_take_decision`/`_arm_result`；`ProgressBar` value/maximum；`Collapsible.activate/toggle`。
- 测试：`tests/widgets/test_contract_text_form.py`（新）；更新的 `test_{text_widget,containers,form,dialog,indicators}.py`、`test_invariants.py`、`tests/app/test_modal.py`（唯一范围外机械改）。
- W6 注意：不要再写 `bar.fraction =` / `slider.take()` 读值 / `Collapsible(title, body)` / `Dialog(title, body, buttons)`；`Text.take()`/`Markdown.take()` 仍是 inline payload。
