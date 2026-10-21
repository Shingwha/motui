# W5b · ScrollView bar 输入 + App drag 路由

> 分支 `refactor/1.2-w5b-scroll`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w5b-scroll`
> 前置：W4b 已合并（`a346ed7`）；写入范围见下；波末必须全量绿。

## 目标

让 `ScrollView(bar=True)` 的 bar 真正可交互：thumb 可拖动、track 可点击翻页、wheel 可达；App 增加通用 drag 路由，把 press/motion/release 派发给命中的、实现了 `drag` 的控件。`bar=False` 行为不变。

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§4 W5 ScrollView bar + W4b 实际交付）
  3. `handoff/W4b-w4b-demo.md`
  4. 本工单
- 基线命令：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
```

起点 **882 passed / 57 topics match**；render hash `a82f7968...`；保持。
- 稳定区（勿重读/勿改）：`widgets/table.py`（W5a 并行）、`widgets/markdown/**`、`demo/topics/components_text.py`、`docs/**`。
- 已知约束/坑：
  - `ScrollView` 现在只有 `scrollbar: bool`；本波改名为 `bar: bool`（破坏性变更），更新所有调用点。
  - `ScrollState.thumb(track_height)` 是唯一 thumb 公式（W1）；拖动映射必须用它，不要再写第二套。
  - `ScrollView.child_at` 已把 bar 列排除；bar 列命中时 chain 尾是 `ScrollView` 本身，正好作为 drag 目标。
  - App 目前只把 mouse 交给 gesture/pointer/focus；没有 drag 路由。需要新增 `Widget.drag(row,col,kind)` 默认 False + `ScrollView.drag` 覆盖 + App 的 press/motion/release 转发。
  - drag press 必须在 gesture/pointer 之前消费，否则 bar 上按下会锚定文本选择。
  - pane `Scrollbar` 是另一套 chrome；本波不要求泛化到 `Scrollable`，只保证 ScrollView 自己的 bar 可交互。demo 的 `interactions--scrollbar` 仍保留 session 的 pane Scrollbar，但 topic 的 ScrollView bar 必须可拖/可滚。
  - golden 不允许变化；如果 bar 视觉变了，停下来报告。

## 工单（按序执行，每项一个 commit）

### T1 · Widget.drag + ScrollView bar 输入

- `core/widget.py`：`Widget` 增加默认 `drag(self, row: int, col: int, kind: str) -> bool: return False`（kind 为 `"press"`/`"motion"`/`"release"`）。
- `widgets/scroll.py`：
  - `ScrollView.__init__` 的 `scrollbar: bool` 改名 `bar: bool`；`revision` 同步。
  - `ScrollView.drag(row, col, kind) -> bool`：
    - 只有 `bar=True` 且 `col == self._last_inner` 才是 bar 列；
    - 用 `self._state.thumb(self._last_height)` 取 `(start,length)`；内容不足/无 thumb 时返回 False；
    - `press`：thumb 行 -> `_grab = (row, self._state.offset)`，返回 True；track 行 -> 向指针方向翻一页（`scroll_by(±viewport_height)`），返回 True；
    - `motion`：`_grab` 存在时，`delta = row - grab_row`，`target = grab_offset + round(delta * scroll / track)`，`scroll_to(target)`，返回 True；
    - `release`：清 `_grab`，返回是否曾经抓住。
  - `ScrollView.click(row, col)`：bar 列时执行 `drag(...,"press")` + `drag(...,"release")`，返回 True；内容列返回 False（交给 descend）。
  - 保留现有 `handle` 的 wheel/键盘分支；增加 `bar` 属性读取。
  - 允许改：`core/widget.py`、`widgets/scroll.py`。
- 验证：pytest + golden 不变。

### T2 · App drag 路由

- `app/application.py`：
  - 新增 `_drag_target: Component | None` 与 `_drag_row/_drag_col`。
  - Dispatch 的 mouse 段，在 gesture/pointer 之前：
    ```python
    if self._drag_target is not None and event.kind in ("motion", "release"):
        if self._drag_event(event):
            return True
    if event.kind == "press" and self._drag_press(event):
        return True
    ```
  - `_drag_press(event)`：`hit = tui.hit`；反向遍历 `hit.chain`，找第一个 `type(component).drag is not Widget.drag` 的组件；调用 `component.drag(row,col,"press")`；True 则记住目标/坐标，返回 True。
  - `_drag_event(event)`：重新 hit-test；在 chain 里找同一目标，使用该层的 row/col；找不到则用上次坐标；调用 `drag(..., event.kind)`；release 或丢失目标时清空；返回结果（release 即使目标消失也返回 True 以结束拖拽）。
  - 更新 App docstring 的 dispatch 顺序（drag 在 mouse 段最前）。
  - 允许改：`app/application.py`、`tests/app/test_app.py`。
- 验证：pytest + golden 不变。

### T3 · 调用点 + demo

- 更新所有 `ScrollView(..., scrollbar=...)`：
  - `demo/topics/interactions.py`：`bar=True`；
  - `demo/topics/components_layout.py`、`demo/topics/components_data.py`、`tests/test_invariants.py`、`tests/widgets/test_scroll.py`、`tests/app/test_app.py` 等 `rg` 命中点。
- `demo/topics/interactions.py` 的 ScrollView 继续 `b.focus(view)`；bar 由 App drag 路由和 wheel 路由工作。
- 不新增 demo 文案（golden 不变）；API line 的 `Scrollbar(...)` 文案留 W6。
- 允许改：`demo/topics/*.py`（仅构造参数）、`tests/**`（构造参数/新增最小 drag 用例）。
- 验证：pytest + golden 不变 + demo 两个入口。

### T4 · 最小测试

- 只加必要用例（优先扩展现有文件）：
  1. `tests/widgets/test_scroll.py`：`bar=True` 时 thumb press/motion/release 移动 offset；track press 翻页；`child_at` bar 列返回 None。
  2. `tests/app/test_app.py`：App 在 bar 上 press/motion/release 能移动 ScrollView offset，且不产生 selection。
- 不新增独立测试文件。

### T5 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 五条门禁全绿；报告贴真实用例数/失败项。
2. `ScrollView(bar=True)` 的 thumb 可拖动、track 可翻页、wheel 可滚；`bar=False` 不变。
3. App 的 drag 路由在 gesture/pointer 之前消费 bar 按下，不产生 selection。
4. golden 57 未变；render hash 不变。
5. `rg "scrollbar=" src tests` 只应剩 pane `Scrollbar` 的构造（不是 ScrollView 参数）。

## 禁触清单

- `widgets/table.py`、`widgets/markdown/**`（W5a 并行）。
- `core/**`（除 `core/widget.py` 的 drag 默认）、`app/**`（除 `application.py` 的 drag 路由）。
- `docs/**`、README/CHANGELOG/pyproject、root `__all__`、golden。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后写 `handoff/W5b-w5b-scroll.md`（60-80 行），重点写 drag 协议、bar 几何、App 路由顺序、调用点、demo 行为、测试。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题
