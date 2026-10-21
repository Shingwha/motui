# W5 · Table 换行 + ScrollView bar 输入

> 占位；W4 合并后由 lead 补全「前置上下文」再派工。
> 两个可并行工单：W5a `refactor/1.2-table-wrap`，W5b `refactor/1.2-scroll-input`。

## 目标

- **W5a**：`Table` 支持 `wrap=True`（默认），单元格按列预算换行，行高 = 最大单元格行数；`wrap=False` 保留省略；Markdown 表格默认换行；inline Segment/link/action 保留；`click`/`hover_at` 映射回数据行。
- **W5b**：`ScrollView(bar=True)` 的 bar 可拖动、可滚轮；pane `Scrollbar` 与 `ScrollView` 共用 `ScrollState.thumb` 和拖动映射；App 的 wheel 路由按 `Hit.chain` 找最近 `Scrollable`；demo `interactions--scrollbar` 只保留一个可交互 bar。

## 依赖

W4 已合并。

## 验收

- 全量 pytest、golden、framebench、两个 demo 入口全绿。
- W5a：长单元格换行而非省略；header 可换行；第二视觉行点击命中同一数据行；Markdown 表格保留 inline style。
- W5b：headless 脚本在 bar 上 press/motion/release 能移动 `ScrollState.offset`；wheel 在 bar/内容上能滚动最近的 ScrollView；不会误触发文本选择。
- 新增测试只覆盖上述两点；不写实现细节测试。
