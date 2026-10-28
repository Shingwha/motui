# W3-a · PixelCanvas widget + octant 探测（占位，W2-a 合并后补前置上下文再派工）
> 分支 `dm-w3a-pixel-canvas`（派工时定）；前置 W2-a；写入范围 `src/motui/widgets/`（新文件）、导出面、golden、新测试 ≤4 条

## 目标
`PixelCanvas(Widget)`：持有 Raster + 图元（line/rect/disc/ring/poly）+ decay/set/unset + underlay，`render() -> Surface` 走 quantize；`marker="half"|"braille"|"mixed"`，octant 档与探测（发探针字符测宽或配置项，方案在派工单定）。

## 范围
widget 层新增；kernel 不改（除非 W2-a 契约暴露缺陷，需在报告中说明）；demo 不动（W4 才消费）。

## 验收
全量门禁绿；widget 直测（headless 渲染断言）；公共 API 面板绿。

## 前置上下文
（W2-a 合并后由 lead 填写）
