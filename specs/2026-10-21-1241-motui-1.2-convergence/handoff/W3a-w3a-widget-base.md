# W3a 交接包
> 分支 `refactor/1.2-w3a-widget-base` / 起点 `16fefcf` / 2026-10-21

## A. 自动事实（从命令与代码生成，别凭记忆）

- commits：`2e5878c`（T1）、`0354488`（T2）、`5edcca6`（T3）、本文件所在 commit（T4）。
- `git diff --stat 16fefcf..HEAD`：8 files, +293/-187（不含本文件）。文件：
  `core/theme.py`（+Styles）、`core/widget.py`（新，+86）、`core/__init__.py`（+Styles/+Widget）、
  `widgets/action.py`、`widgets/dialog.py`、`demo/topics/{components_actions,styling}.py`、`tests/widgets/test_action.py`。
- `Styles`：`core/theme.py`，`@dataclass(frozen=True, slots=True, kw_only=True)`，10 个字段与 Theme 组同名，默认 `None=继承`。
  `theme.__all__` 与 `core.__all__` 已加 `Styles`；`Widget` 只加 `core.__all__`，root `__all__` 未动（仍 37）。
- `Widget`：`core/widget.py`，`__slots__ = ("theme","styles","focused","hover")`，**不继承 `Themed`**（`Widget.__bases__ == (object,)`）。
  `_theme` = `theme or DEFAULT_THEME`；`group(name)` = 非 None 的 `styles.<name>` 否则 `_theme.<name>`；
  `handle/click/hover_at/activate` -> False，`take_result/revision` -> None，`render` -> `NotImplementedError`；无 `child_at`。
- 签名实测（`inspect.signature`）：
  - `Button(label, *, disabled=False, theme=None, styles=None)`
  - `Link(text, *, disabled=False, theme=None, styles=None)`
  - `Checkbox(label, *, checked=False, glyphs=GLYPHS, disabled=False, theme=None, styles=None)`
  - 三者都无 `focused=` 与 4 个 `*_style` 参数；基类均为 `Widget`。
- `__slots__` 实测：`Button=("_pending","disabled","hint","label")`、`Link=("_pending","disabled","hint","text")`、
  `Checkbox=("_pending","checked","disabled","glyphs","hint","label")`；`theme/focused/hover` 已从子类删除。
- 验收 grep：`rg "hover_style|focus_style|disabled_style|style=" src/motui/widgets/action.py` -> **空**。
- 全波真实结果（本 worktree，CPython 3.13）：
  - `uv run pytest -q -p no:cacheprovider` -> **880 passed**（879 基线 + T3 的 1 个活主题用例）。
  - `uv run python tools/golden.py --check` -> **57 topics match**，未重录任何帧。
  - `uv run python tools/framebench.py` -> render hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（与 W2 基线一致）。
  - `uv run python -m motui < /dev/null` -> exit 0；`--pages` -> exit 0，4059 行。

## B. 只存在于脑子里的东西（W3b/W3c 直接复用）

**迁移 pattern（每一步都验证过）**

1. `class X(Widget)`，构造器 `super().__init__(theme, styles)`；不要保留 `Themed` 的 `pick`。
2. `__slots__` 删除 `"theme"`/`"focused"`/`"hover"`（基类已有）以及所有 `_*_style` 缓存槽；保留行为状态槽。
3. 删除构造器 `style/hover_style/focus_style/disabled_style/focused`，加 `styles: Styles | None = None`；参数顺序确认在 10 个以内。
4. `render()` 里**每次**调用 `self.group("<组>")`，不缓存解析结果；状态优先级保持不变（disabled > focus/hover > base）。
5. `revision()` 返回 `(原有状态..., self.theme, self.styles)`；否则 Block 的 `(width, revision)` 缓存会吞掉换主题。
6. 禁用态读 `group("text").faint`；不要恢复旧的 `disabled_style` 名字。

**样式映射（action 家族，W3b 可照抄）**

| 控件 | base | hover | focus | disabled |
|---|---|---|---|---|
| Button | `controls.base` | `surfaces.hover` | `controls.focus` | `text.faint` |
| Checkbox mark | `content.accent` | `surfaces.hover` | `controls.focus` | `text.faint` |
| Checkbox label | `text.base` | 同上 | 同上 | `text.faint` |
| Link | `content.link` | `surfaces.hover` | `controls.focus` | `text.faint` |

**显式样式 -> Styles 的等价转换**：旧 `style=` 只重画 base；用 `Styles(controls=replace(<effective>.controls, base=style))`
（Link/Checkbox 若用户指定 `style=`，旧语义是“同时画 mark+label/link”，需要分别覆盖 `content.accent` + `text.base`，或
Link 的 `content.link`）。旧的 `hover_style/focus_style/disabled_style` 分别对应 `surfaces.hover`、`controls.focus`、`text.faint`，
且整组替换时必须从**当前生效主题** `replace` 出来，否则同组其它字段会漂移。

**调用点清单（全部已扫描 `rg "Button\(|Checkbox\(|Link\(" src tests`）**

- 改了：`demo/topics/components_actions.py`（`focused=True` -> 先构造再赋值 `.focused = True`，渲染不变）；
  `demo/topics/styling.py`（5 处 `style=` -> `Styles(controls=replace(b.theme.controls, base=...))`）；
  `widgets/dialog.py::_new_button`（ButtonSpec 的 style/hover/focus -> 组覆盖；`danger` 仍默认 `status.danger`）；`tests/widgets/test_action.py`。
- 不用改（只用 `theme=`/`disabled=`/默认构造）：`demo/topics/components_forms.py`、`components_overlays.py`、`overview.py`、
  `patterns.py`、`interactions.py`、`tests/test_invariants.py`、`tests/widgets/test_form.py`、`tests/interaction/{test_modal,test_overlays}.py`、
  `tests/kernel/test_theme.py`。
- 坑：`demo/topics/components_actions.py` 的 `api_line` 字符串是**渲染内容**（进 golden），本次刻意未改，仍写着旧签名；
  W6 更新 demo 文案时一并重录 `components--button`/`components--link`。

**偏差与取舍**

- 工单 T2 的允许文件清单漏了 `widgets/dialog.py` 与 `demo/topics/styling.py`，但它们是 `rg` 扫出的必改调用点；
  只改构造点、不改行为/渲染，故按 T2 “更新所有调用点”处理并在报告记录。
- `Themed` 一行未动；`find.py`/`command_palette.py` 的 `Input`/`Autocomplete` 未动（W3b/W3c）。
- W2 handoff 约束核验：`Themed` 仍 `__slots__=("_theme",)` 且构造期解析；widgets 未 import app；golden 零改动；
  `tests/kernel` 目录名未动；root `__all__` 未动；`.zcodeignore` 未提交。

## C. 指针

- `src/motui/core/widget.py`（全部）、`src/motui/core/theme.py` 的 `Styles` 段、`src/motui/core/__init__.py` 的 import/`__all__`。
- `src/motui/widgets/action.py` 的 `_band` 与三个 `render()`；`src/motui/widgets/dialog.py::_new_button`。
- `tests/widgets/test_action.py` 的 `test_a_theme_assignment_repaints_the_next_render`（活主题回归样板）。
- 稳定区（下一波不必重读）：`core/scroll.py`、`core/cursor.py`、`core/block.py`、全部 golden、`tools/golden.py`、`docs/**`。
