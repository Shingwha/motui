# W2-a · PixelCanvas widget + octant 探测（占位，W1-a 合并后补前置上下文再派工）
> 分支 `dm-w2a-pixel-canvas`（派工时定）；前置 W1-a；写入范围 `src/motui/widgets/`（新文件）、`src/motui/widgets/__init__.py` 导出、`tests/`（新文件 ≤4 条）

## 目标
`PixelCanvas(Widget)`：持有 `Raster` + 图元便捷方法 + decay/set/unset + 多层（填充层 half / 线条层 braille）组织，`render(Constraints) -> Surface` 调 `kernel.quantize`。marker 由构造参数定层组织；octant 档与终端探测（发探针字符测宽，或先做显式配置项——方案在派工单拍板）。消费方：demo Motion 节（W3-b）与未来任何像素场景；**widget 之外不得出现第二套量化调用姿势**。

## 范围
kernel 不改（若 W1-a 契约暴露缺陷，报告说明并给最小补丁建议，lead 拍板）；demo 不动；公共 API 面板纯增。

## 验收
全量门禁绿；widget 直测（headless 渲染逐字断言）；`tests/test_api.py` 绿；性能：76×24 帧经 widget 全流程 ≤12ms。

## 前置上下文
（W1-a 合并后由 lead 填写：kernel 最终签名、W1-a handoff 指针、层组织用法示例）
