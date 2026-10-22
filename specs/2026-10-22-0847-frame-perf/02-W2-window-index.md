# W2 · 增量窗口索引（M2）—— 占位，待 W1 合并后补全 `## 前置上下文`
> 分支 `fp-w2-window-index`；前置 W1 已合并；写入范围 `src/motui/core/viewport.py`、`src/motui/core/block.py`（如索引需要）、`tools/framebench.py`、`tests/core/test_viewport.py`、`docs/DESIGN.md`

## 目标

`Viewport.layout` 从"每帧无条件漫游全部块"（viewport.py:171-183）改为增量索引：
revision 等值比较探测脏块 → 只重渲变化块 → 前缀和增量维护 → 窗口二分定位 → 只物化
与 `[offset, offset+vh)` 重叠的行。每帧成本从 O(全部块 × 各自调用开销) 降到
O(全部块的最廉比较 + 变化块渲染 + log n 定位 + 可见窗口行)。渲染字节与全部既有测试
零变化（红线 1/2）；`core/scroll.py` 零改动（不变量 4）。

## 范围与验收（占位，派工前不变）

- 索引是 Viewport 私有状态（P5）：键 `(Document.mutation, width)`；revision `None`
  永远脏（P5）；前缀和朴素 suffix 重算（P6）；`block_order` tuple 按 mutation 复用。
- pinned（top/bottom）块与 body 块同索引治理；`natural_height` 走同一索引。
- `ScreenLayout` 输出契约逐字段不变（interfaces.md）。
- framebench 新增 `idle-long` 行（P7，只加不改）+ docstring 基线段；`render-hash`
  逐字不变；`scroll-long` 在 W1 之上再降；`idle-long` 接近单 pane 直通下限。
- 新增测试 ≤ 4 条（P9）：脏块重数、结构变更（add/remove 中部）后地址算术、宽度变化
  全量重建、非 Revisioned 块每帧重渲不冻结。

## 依赖

W1 的 `row_count`/`rows_view` 门与 `Document.mutation` 计数；`handoff/W1-a.md`。
