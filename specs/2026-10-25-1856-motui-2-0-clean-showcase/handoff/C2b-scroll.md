# C2b · ScrollState → Scroll/ScrollAxis · 交接

> 分支 `2.0-clean/c2b-scroll`；起点 `3db86ff`；5 个工单 commit + 本 handoff。
> 权威：`../2026-10-25-0900-motui-2-0-architecture/ref/source/02-core-contracts.md` §6。

## A. 交付面

- **`ScrollAxis.clamp(previous_extent: int | None = None)`**：`limit=max_offset`；
  `at_previous_bottom = previous_extent is None or offset >= previous_extent`；
  sticky 且贴底 → `offset=limit`，否则 `[0, limit]` clamp。无参 = previous None
  （等价旧 `ScrollState._extent=None`：首次 clamp 直接贴底），返回新值。
- **`Viewport`**：`_state` → `_scroll: Scroll()`（x 恒 0，y sticky=True）+
  `_last_y_extent`。两条 layout 路径（普通 / FILL）都按
  `replace(y, content=..., viewport=...).clamp(_last_y_extent)` 更新并写回新
  `max_offset`；`scroll_up/down/to/by/to_bottom/offset/_max_offset/at_bottom`
  全走 y 值；`scroll` property 返回 `Scroll`；`scroll_state` 删除。
  `at_bottom` 按工单定义为 `offset >= max_offset`。
- **`Pane`**：`scroll_state` → `scroll -> Scroll`；`scroll_to/scroll_by` 委托
  viewport 不变。
- **`Scrollable` Protocol**：`scroll` property + `scroll_to/scroll_by`；
  `scroll_state` 删除。`application._wheel/_scroll_key` 的 isinstance 路径未改。
- **`ScrollPanel`**：`_state`/`_x` 合并为 `_scroll: Scroll`，y 显式
  `sticky=False`（不得吃 `Scroll()` 的 sticky 默认）。`offset/x_offset/
  total_rows/total_columns/viewport_height/viewport_width/scroll` 均读值；
  `scroll_to/scroll_x` 用 `with_y/with_x` + `replace`；`reveal` 用
  `ScrollAxis.reveal` 且强制 y sticky=False；`render` 两轴独立
  `replace(...).clamp()`；`on_drag`/`child_at`/bar/`__repr__` 同步。
- **`app/scrollbar.py`**：`_thumb_of` 用 `ScrollAxis(offset=layout.offset,
  content=layout.total_rows, viewport=len(layout.body_rows))`；水平条读
  `target.scroll.x`；拖拽跨度 `scroll = axis.max_offset`。
- **`app/gesture.py`**：自动滚动改走 `pane.scroll_by(rows)`；偏移读取仍
  `viewport.offset`。
- **删除**：`ScrollState` 类与 `__all__` 条目；src 内 `ScrollState`/
  `scroll_state` 0 处（`grep -rn` exit 1）。`tools/api-2.0.txt` 仍 185 names
  （`ScrollState` 从未进公开快照）。

### 门禁（真实输出）
```
uv sync --locked                    -> motui==2.0.0 (editable)
pytest -q -p no:cacheprovider       -> 1610 passed in 38.96s
golden / semantic --check           -> 57 / 57 topics match
framebench                          -> e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da
python -m motui < /dev/null         -> exit 0, 70 lines
python -m motui --pages             -> exit 0, 4059 lines
quickstart/snake/dashboard/wide_table --headless -> 全部 exit 0
ruff / pyright                      -> All checks passed / 0 errors, 0 warnings
lint-imports / api --check          -> 4 kept, 0 broken / 185 names match
growth.py (full)                    -> pytest/golden/api pass, OK
```

## B. 语义、对照与坑

- **sticky previous-extent**：新 clamp 把旧 `_extent` 变成调用方传入的
  `previous_extent`；Viewport 在每次 layout 后写回 `y.max_offset`。首帧
  `None` 贴底、贴底后内容增长继续贴底、用户离开后增长不动、缩容回 clamp，
  均有单测（`test_sticky_*`、`test_detached_viewport_*`）。
- **逐值差分**：用 `git archive 3db86ff` 导出旧 `motui`，与 HEAD 跑同一
  trace（Viewport 15 条、growth 7 条、ScrollPanel 10 条、双轴 10 条，共 42
  条快照/返回值，含增长/缩容/resize/reveal/bar/thumb 字节），除模块路径外
  **完全一致**。
- **旧 ScrollState 规则映射**：`scroll_to` 落到 `max` 才重新 sticky；向上
  `scroll_by/scroll_up` 强制 sticky=False；向下到 max 自动 reattach；
  `reveal` 只移动 offset、sticky 由调用方（ScrollPanel）关掉。
- **x/y 独立**：ScrollPanel 的 y 与 x 各自 `clamp`，x 永不 sticky；共享一个
  `Scroll` 值但互不影响，`test_both_axes_clamp_independently` 覆盖。
- **`at_bottom`**：按工单用 `offset >= max_offset`，不再读 sticky 标志。对
  可达状态两者等价；唯一差异是“内容全可见时显式 scroll_up”（旧 False、新
  True），属工单定义。
- **坑**：`Scroll()` 默认 y sticky=True，ScrollPanel 必须显式传 y 轴；
  `clamp()` 无参等价 previous=None（sticky 首帧贴底）；`_last_y_extent` 只在
  layout 更新，短文档 resize 也走同一条 clamp；`ScrollPanel._rendered` 仍
  负责“首渲染前接受 offset”；删掉 `_state` 后不要再引入任何可变偏移。
- **framebench**：本机初始基线明显快于随后所有测量（含 base export），故用
  交错 3 轮 base/HEAD 对照：中位数 base 2.2/13.7/1.2/2.2/920ms，HEAD
  2.3/13.6/1.2/2.2/604ms（single/split/scroll/scroll-long/replay）；除 replay
  噪声（base 560–923、HEAD 577–867）外无 >10% 劣化，hash 不变。

## C. 路径、提交与行数

关键路径：`src/motui/kernel/{layout,frame}.py`、`src/motui/widgets/scroll.py`、
`src/motui/app/{scrollbar,gesture}.py`、`tests/kernel/{test_layout,test_scroll_values}.py`、
`tests/widgets/test_scroll.py`、`tools/api-2.0.txt`（无内容变化）。

commit：`a5f0962` ScrollAxis.clamp previous extent · `7bb8553` Viewport/Scroll
· `f010c61` ScrollPanel/Scroll · `e5fff8c` Scrollbar/Gesture · `490163b`
删除 ScrollState · 本 handoff commit。

行数（wc -l，base→head）：layout 1007→909、frame 1709→1709、scroll 574→575、
scrollbar 683→679、gesture 634→631。测试 1604→1610（+6：clamp 3、viewport 2、
panel 1；ScrollState 对照改写为 pinned 断言 + 1 个 legacy thumb 参考公式）。
