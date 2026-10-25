# C2b · ScrollState → Scroll / ScrollAxis

> 分支 `2.0-clean/c2b-scroll`；前置：C2a 已合并（`3db86ff`）；写入范围：`src/motui/kernel/layout.py`、`src/motui/kernel/frame.py`（Pane 代理）、`src/motui/widgets/scroll.py`、`src/motui/app/{scrollbar,gesture}.py`、`tests/**`、`tools/api-2.0.txt`
> 权威：`../2026-10-25-0900-motui-2-0-architecture/ref/source/02-core-contracts.md` §6、`05-api-surface.md`

## 目标

删除可变 `ScrollState`，所有滚动表面统一用不可变的 `Scroll`/`ScrollAxis`：

1. `ScrollAxis.clamp(previous_extent=None)` 保留 sticky 的 previous-extent 语义；
2. `Viewport` 持有 `Scroll`（x 恒等、y sticky），`scroll` 属性返回 `Scroll`；
3. `ScrollPanel` 持有 `Scroll`（x/y），所有 offset/thumb/滚动方法用值替换；
4. `Pane.scroll`/`Scrollable.scroll` 返回 `Scroll`；`Scrollbar`/`Gesture` 用值；
5. 删除 `ScrollState` 与旧 `scroll_state()` 名；
6. 1604 用例、57 byte/semantic、hash 不变。

**本波结束：`grep ScrollState`/`scroll_state` 在 src 为 0；sticky/thumb/clamp 行为与 1.x 逐值一致；全量绿。**

## 前置上下文

- 必读：`../2026-10-25-0900-motui-2-0-architecture/handoff/W5-final.md` → C1/C2a handoff → 本工单。
- 基线：`uv sync --locked`；`pytest`（1604 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `kernel/layout.py:ScrollAxis`（不可变，offset/content/viewport/sticky，clamp 无 previous extent）与 `Scroll`（x/y）。
  - `ScrollState`（可变）：offset/content_height/viewport_height/stick_to_bottom/_extent；`max_offset/clamp/scroll_to/scroll_by/reveal/thumb`。
  - `Viewport` 持有 `_state: ScrollState`；`layout` 设置 content/viewport、clamp、读 offset；`scroll_up/down/to/to_bottom/by/reveal/at_bottom/scroll_state`。
  - `ScrollPanel` 持有 `_state: ScrollState`；`offset/total_rows/viewport_height/scroll_to/scroll_by/reveal/scroll_x/scroll_y/scroll_state`。
  - `Pane.scroll_state/scroll_to/scroll_by` 委托 viewport；`app/scrollbar.py:_thumb_of` 构造 `ScrollState` 取 thumb；`app/gesture.py` 用 `viewport.scroll_state/scroll_to`。
  - `Scrollable` Protocol（layout.py）定义 `scroll_state()/scroll_to/scroll_by`。
- 设计：
  - `ScrollAxis.clamp(previous_extent: int | None = None)`：
    ```python
    limit = self.max_offset
    at_prev_bottom = previous_extent is None or self.offset >= previous_extent
    if self.sticky and at_prev_bottom: return replace(self, offset=limit)
    return replace(self, offset=max(0, min(self.offset, limit)))
    ```
    保留旧 `clamp()` 无参调用（等价于 previous=None）。
  - `Viewport`：
    - `self._scroll = Scroll()`（x 0，y sticky=True）；`self._last_y_extent: int|None=None`。
    - `layout`：`y = replace(self._scroll.y, content=body_total, viewport=vh)`；`y = y.clamp(self._last_y_extent)`；`self._scroll = self._scroll.with_y(y)`；`self._last_y_extent = y.max_offset`。
    - `scroll_to(offset)`：`target = clamp`; `y = replace(self._scroll.y, offset=target, sticky=target>=y.max_offset)`; store; return moved.
    - `scroll_by(delta)`：用 `scroll_to(offset+delta)`，向上 `sticky=False`，向下到 max `sticky=True`（与旧行为一致）。
    - `scroll_up/down`：`scroll_by(∓n)` + sticky 规则。
    - `reveal(row)`：`y = self._scroll.y.reveal(row).with sticky=False`；store；return moved.
    - `scroll_to_bottom`：`scroll_to(max_offset)`；`at_bottom`：offset>=max。
    - `scroll` property → `self._scroll`；`offset` → y.offset。
  - `ScrollPanel`：
    - `self._scroll = Scroll(x=ScrollAxis(offset=...), y=ScrollAxis(offset=..., sticky=False))`。
    - `render`：`x = replace(self._scroll.x, content=content_w, viewport=inner_w).clamp()`；`y = replace(self._scroll.y, content=content_h, viewport=height).clamp()`；store。
    - `offset/total_rows/viewport_height/x_offset/total_columns/viewport_width` 从 `_scroll` 读。
    - `scroll_to/scroll_by/scroll_x/scroll_y/reveal` 用 `replace`/`with_*`。
    - `scroll` property → `self._scroll`。
  - `Pane.scroll` property → `viewport.scroll`；`scroll_to/scroll_by` 委托。
  - `Scrollable` Protocol：
    ```python
    class Scrollable(Protocol):
        @property
        def scroll(self) -> Scroll: ...
        def scroll_to(self, offset:int)->bool: ...
        def scroll_by(self, delta:int)->bool: ...
    ```
  - `app/scrollbar.py`：
    - `_thumb_of(layout, height, min_thumb)` 用 `ScrollAxis(offset=layout.offset, content=layout.total_rows, viewport=len(layout.body_rows)).thumb(height, min_thumb)`。
    - 水平 target 用 `target.scroll.x`（或 `target.x_offset/total_columns/viewport_width` 构造 ScrollAxis）。
    - 删除 `ScrollState` import。
  - `app/gesture.py`：`pane.scroll`/`scroll_to`；自动滚动用 `scroll_by`。
- 已知坑：
  - `Viewport.layout` 的 sticky 依赖 previous extent；`_last_y_extent` 初始 None → clamp 贴底（与旧 `_extent=None` 一致）。
  - `ScrollPanel` 的 y sticky=False；x sticky=False；不要误用 `Scroll()` 默认 y sticky。
  - `scroll_to` 到 max 要重新 sticky=True；向上滚要 sticky=False（旧 ScrollState 规则）。
  - `reveal` 明确不改变 sticky（旧 ScrollState.reveal 只移动 offset；调用方 `ScrollPanel.reveal` 设置 stick_to_bottom=False）。
  - `ScrollPanel` 的 `_last_offset/_last_height/_last_inner` 仍用于 child_at/bar；可从 `_scroll` 读或保留。
  - `Scrollbar` 的 `_thumb_of` 目前用 `ScrollState`；改成 `ScrollAxis` 后公式不变（C2a 已验证 thumb 委托）。
  - `tests/kernel/test_scroll_values.py` 有 ScrollState 对照；删除对照，保留 ScrollAxis 断言。
  - 57 golden/hash 不变。
- 不改渲染/交互算法；不改 demo 结构。

## 工单（按序，每步一个 commit）

### T1 `ScrollAxis.clamp(previous_extent)`

- `kernel/layout.py`：加参数与 docstring；无参调用等价 previous=None。
- 测试 `tests/kernel/test_scroll_values.py`：sticky 在内容增长时贴底、用户离开底部后不贴底、普通 clamp、x 轴不 sticky。
- 验证：`uv run pytest -q tests/kernel/test_scroll_values.py`。

### T2 Viewport → Scroll

- `kernel/layout.py:Viewport`：
  - `_state` → `_scroll: Scroll` + `_last_y_extent`；
  - `layout` 按设计更新；
  - `scroll_up/down/to/to_bottom/by/reveal/at_bottom/offset/max_offset/scroll` 迁移；
  - 删除 `scroll_state` 方法；`scroll` property。
- `kernel/frame.py:Pane`：`scroll_state` → `scroll` property；`scroll_to/scroll_by` 委托。
- `kernel/layout.py:Scrollable`：改为 `scroll` property + `scroll_to/scroll_by`；删除 `scroll_state`。
- 测试 `tests/kernel/test_layout.py`：offset/sticky/reveal/at_bottom 与旧值一致；`viewport.scroll` 是 `Scroll`，x 为 0。
- 验证：`uv run pytest -q tests/kernel/test_layout.py tests/kernel/test_scroll_values.py`。

### T3 ScrollPanel → Scroll

- `widgets/scroll.py`：
  - `_state` → `_scroll: Scroll`；
  - 所有 offset/content/viewport 读写改为 `_scroll.x/y`；
  - `scroll_to/scroll_by/scroll_x/scroll_y/reveal` 用 `replace`；
  - `scroll` property；删除 `scroll_state`；
  - `render` 设置 x/y 的 content/viewport 并 clamp；
  - `child_at`/bar/repr 同步。
- 测试 `tests/widgets/test_scroll.py`：x/y 独立 clamp、sticky（y 默认 False）、reveal、bar thumb、wheel 行为不变。
- 验证：`uv run pytest -q tests/widgets/test_scroll.py`。

### T4 Scrollbar / Gesture

- `app/scrollbar.py`：删除 `ScrollState`；`_thumb_of` 用 `ScrollAxis`；水平条用 target 的 `scroll.x`；行为/几何不变。
- `app/gesture.py`：`scroll_state` → `scroll`；自动滚动用 `scroll_by`。
- 测试 `tests/app/test_scrollbar.py`、`test_gesture.py`、`test_find.py`（若有 scroll_state 引用）。
- 验证：`uv run pytest -q tests/app`。

### T5 收口

- `grep -rn "ScrollState\|scroll_state" src/motui` → 0；`kernel/__init__`/`__all__` 删除 `ScrollState`。
- `tools/api.py --update`；全量验收；framebench 对比。
- 报告行数与剩余旧名。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `ScrollState`/`scroll_state` 在 src 为 0；`Viewport.scroll`/`ScrollPanel.scroll` 返回 `Scroll`。
5. sticky/thumb/reveal 与旧行为逐值一致（测试对照）。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth.py` full 全绿；framebench 不劣化 >10%。

## 禁触清单

`terminal/**`、`kernel/{cell,frame 的其它方法,hit,overlay,selection,style,glyphs,theme,text,events,keymap,geom,document}.py`、`widgets/**` 除 `scroll.py`、`app/{focus,pointer,modal,find,overlays,command_palette,runtime,workspace,application}.py`、`demo/**`、`tests/golden/**`、`tools/{golden,framebench,semantic,growth}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/C2b-scroll.md`：A 节给 ScrollAxis/Scroll 面、Viewport/ScrollPanel/Scrollbar 映射、门禁；B 节给 sticky previous-extent、x/y 独立、旧 ScrollState 行为对照、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
