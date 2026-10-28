# W3-b · Terminal 报告节 + Themes 节（占位，W2-b 合并后补前置上下文再派工）
> 分支 `dm-w3b-report-themes`（派工时定）；前置 W2-b；写入范围 `src/motui/demo/sections/**`、golden、新测试 ≤4 条

## 目标
**Terminal**：尺寸/色模式/DECSET 2026/鼠标实况（移动区回显最近事件）/16·256·truecolor 色条/marker 阶梯自检（octant 探测联动 W3-a，未合则显示未探测）/帧计数与 ms/帧。**Themes**：同一样例布局 + 快捷键/面板即时切主题。

## 范围
只动对应 section 文件；探测逻辑经 W3-a 的公共能力（若已合并），否则本波只做展示层。

## 验收
全量门禁绿；golden 更新；两节确定性重放（鼠标区在 headless 下显示脚本注入的事件或空态）。

## 前置上下文
（W2-b 合并后由 lead 填写）
