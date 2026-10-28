# W4 · Motion 双画板 + Splash 2.0（占位，W3-a 与 W1-b 均合并后补前置上下文再派工）
> 分支 `dm-w4-motion-splash`（派工时定）；前置 W3-a + W1-b（并以最新 main 为基线）；写入范围 `src/motui/demo/**`、golden、新测试 ≤4 条

## 目标
**Motion 节**：PixelCanvas rings（examples/pixel.py 收编，键盘判定+鼠标踢球适配新输入面）与 Canvas Snake 并列两模式——"两种画板"叙事；marker 阶梯对比条。**Splash 2.0**：手绘像素 wordmark（≈152×96 虚拟像素）+ 扫光/视差星空，四个风格包美术身份保留，"任意键→menu"与永不超时契约不变。

## 范围
`motion.py`、`splash.py` 重写；`demo/snake.py` 迁入或保留由派工单定；examples/pixel.py 收编后保留与否由 lead 届时拍板。

## 验收
全量门禁绿；golden 全部重录并 `--check` 绿；60fps 帧预算实测写入 docstring；确定性重放逐字一致。

## 前置上下文
（W3-a 合并后由 lead 填写）
