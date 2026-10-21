# W3a · Widget / Styles 基础 + action 家族

> 分支 `refactor/1.2-w3a-widget-base`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w3a-widget-base`
> 前置：W2 已合并（`0c25bc2`）；写入范围见下；波末必须全量绿。

## 目标

新增 `Widget` 基类和 `Styles` 组覆盖，并用 `Button` / `Checkbox` / `Link` 三个 action 控件验证模式：删除 4 个 `*_style` 参数和 `focused=`，样式在 render 时解析，换主题不重建控件。**默认主题/现有 golden 的渲染必须逐字节不变。**

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§2 W3 冻结 + §2 W2 实际交付）
  3. `specs/2026-10-21-1241-motui-1.2-convergence/handoff/W2-w2-runtime.md`
  4. 本工单
- 基线命令（开工先跑，贴真实输出）：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
```

起点应为 **879 passed / 57 topics match**。
- 稳定区（勿重读/勿改）：`core/scroll.py`、`core/cursor.py`、`core/block.py`、全部 golden、`docs/**`、`pyproject.toml`。
- 已知约束/坑（来自 W2 handoff）：
  - `Themed` 仍有 `__slots__ = ("_theme",)`，**不要改它**；`Widget` 不继承 `Themed`，自己持有 `theme/styles/focused/hover`。
  - 迁移一个控件时，把基类从 `Themed` 改为 `Widget`，并从该控件的 `__slots__` 删除 `"theme"`/`"focused"`/`"hover"`。
  - 控件在 render 时通过 `self._theme` / `self.group(...)` 读样式，不要缓存解析结果。
  - `revision()` 必须包含 `theme` 和 `styles`，否则 Block 缓存会吞掉主题切换。
  - `find.py`/`command_palette.py` 直接构造 `Input`/`Autocomplete`；本波不动它们。

## 工单（按序执行，每项一个 commit）

### T1 · Styles + Widget 基础

- 在 `src/motui/core/theme.py` 增加：

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Styles:
    text: TextStyles | None = None
    surfaces: SurfaceStyles | None = None
    borders: BorderStyles | None = None
    controls: ControlStyles | None = None
    rows: RowStyles | None = None
    status: StatusStyles | None = None
    content: ContentStyles | None = None
    chrome: ChromeStyles | None = None
    overlays: OverlayStyles | None = None
    syntax: SyntaxStyles | None = None
```

- 在 `src/motui/core/widget.py` 新增 `Widget`：
  - `__slots__ = ("theme", "styles", "focused", "hover")`；
  - `__init__(theme=None, styles=None)` 置 `focused=False`、`hover=False`；
  - `_theme` property 返回 `self.theme or DEFAULT_THEME`；
  - `group(name)` 返回 `self.styles.<name>`（非 None 时）否则 `self._theme.<name>`；
  - 默认交互动词：`handle/click/hover_at/activate` 返回 `False`，`take_result` 返回 `None`，`revision` 返回 `None`；
  - `render(width)` 抛 `NotImplementedError`（子类实现）。
  - 不定义 `child_at`（容器才实现）。
- 从 `core/__init__.py` 导出 `Styles` 和 `Widget`（加入 `__all__`）。
- 不改 `Themed`。
- 只允许改：`src/motui/core/theme.py`、`src/motui/core/widget.py`(新)、`src/motui/core/__init__.py`。
- 验证：`uv run pytest -q -p no:cacheprovider`（其它控件仍用 Themed，应全绿）。

### T2 · action 家族迁移

- `src/motui/widgets/action.py` 的 `Button` / `Checkbox` / `Link`：
  - 基类 `Themed` -> `Widget`；
  - `__slots__` 删除 `"theme"`/`"focused"`/`"hover"`（若存在）；
  - 删除构造器参数 `style` / `hover_style` / `focus_style` / `disabled_style` / `focused`，改为 `styles: Styles | None = None`；
  - 删除 `self._base_style` / `_hover_style` / `_focus_style` / `_disabled_style` / `_mark_style` / `_label_style` 等构造期缓存；render 时读：
    - `Button`: `group("controls").base`、`group("surfaces").hover`、`group("controls").focus`、`group("text").faint`；
    - `Checkbox`: `group("content").accent`（mark）、`group("text").base`（label）、`group("surfaces").hover`、`group("controls").focus`、`group("text").faint`；
    - `Link`: `group("content").link`、`group("surfaces").hover`、`group("controls").focus`、`group("text").faint`。
  - 保留原有状态优先级和所有行为（click/activate/hover/focus/disabled/take_result）。
  - `revision()` 加入 `self.theme`、`self.styles`（以及原有状态）。
  - 默认渲染必须与迁移前逐字节相同。
- 更新所有调用点：
  - `rg -n "Button\(|Checkbox\(|Link\(" src tests`；
  - 删除 `focused=`；把显式 `style=`/`hover_style=`/`focus_style=`/`disabled_style=` 改成 `Styles(...)` 对应组；
  - 没有显式样式的调用只删参数，不加 `styles=`。
- 允许改：`src/motui/widgets/action.py`、`demo/topics/components_actions.py`、`demo/topics/overview.py`、`demo/topics/patterns.py`、`demo/topics/interactions.py`、`tests/widgets/test_action.py`、`tests/test_invariants.py`（仅构造点）、`tests/test_api.py`（仅必要时）。
- 验证：pytest + golden 逐字节不变。

### T3 · 活主题最小抽验

- 在 `tests/widgets/test_action.py` 增加 **一个** 用例：同一 `Button` 实例，改 `button.theme` 后 `render` 使用新主题的 `controls.base`（例如比较 `Line` 的 style 或输出字节）；不需要第二个用例。
- 如果现有测试已经覆盖同一实例的 theme 变更，则不加，报告说明。
- 只允许改 `tests/widgets/test_action.py`。

### T4 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 五条门禁全绿；报告贴真实用例数/失败项。
2. `rg "hover_style|focus_style|disabled_style|style=" src/motui/widgets/action.py` 为空（内部 `self.styles` 除外）。
3. `Button` / `Checkbox` / `Link` 的公共构造器不再有 `focused=` 和 4 个 `*_style` 参数。
4. 同一实例改 `theme` 后重绘使用新主题（T3 用例或现有覆盖）。
5. golden 逐字节不变；framebench render hash 不变。

## 禁触清单

- `Themed` 及其它未迁移控件（W3b/W3c）。
- `core/scroll.py`、`core/cursor.py`、`core/block.py`、`core/hit.py`。
- `app/**`、`widgets/scroll.py`、`widgets/table.py`、`widgets/markdown/**`。
- `docs/**`、`README.md`、`CHANGELOG.md`、`pyproject.toml`、root `__all__`。
- golden 文件、`.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后在分支最后一个 commit 写 `specs/2026-10-21-1241-motui-1.2-convergence/handoff/W3a-w3a-widget-base.md`，按 Handoff 协议，60-80 行。**重点写清迁移 pattern、slot 处理、样式映射、调用点清单**，供 W3b/W3c 直接复用。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验（W2 handoff 的哪些约束被验证/推翻）/
探索审计 / 未决问题
