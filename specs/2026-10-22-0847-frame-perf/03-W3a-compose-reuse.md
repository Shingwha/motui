# W3a · compose 容器复用（M5）—— 占位，待 W2 合并后补全 `## 前置上下文`
> 分支 `fp-w3a-compose-reuse`；前置 W2 已合并；写入范围 `src/motui/core/frame.py`、`tests/core/test_frame.py`、`docs/DESIGN.md`

## 目标

`Frame.compose` 每次组合的 `plan`/`table` 两层列表分配（frame.py:1340-1341）在尺寸
不变时复用容器（逐行 clear 而非重建），D11 备忘录已防住的"重拼接"之外把"分配"也
收掉；如实现顺路，"整行单写"（无 chrome 覆写的行）可跳过 plan 构建、直接消费 layout
行——以渲染字节零变化为前提，不顺路则不做。`stream-split` 下降为证据；
`render-hash` 逐字不变。

## 范围与验收（占位，派工前不变）

- `compose` 输出契约与备忘录键语义不变；pass-through 路径零变化。
- 新增测试 ≤ 4 条（P9）。
- `docs/DESIGN.md` frame 相关段落按新现实校正（W2 已先改 viewport 段，不冲突）。

## 依赖

W1+W2 已合并（M5 在 M1/M2 之后才是剩余大头）；`handoff/W1-a.md`、`handoff/W2-a.md`。
