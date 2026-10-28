# W3-b · Motion 双画板 + Splash 2.0（占位，W2-a 与 W1-b 均合并后补前置上下文再派工）
> 分支 `dm-w3b-motion-splash`（派工时定）；前置 W2-a + W1-b（以最新 main 为基线同步）；写入范围 `src/motui/demo/**`、golden 重录、新测试 ≤4 条

## 目标
**Motion 节**：PixelCanvas rings（判定游戏：键盘空格判定 + 鼠标踢球，语义以原 examples/pixel.py 为准——该文件此时已删，行为契约在本工单派工时由 lead 从对话纪要誊写）与 Canvas Snake 并列两模式，讲"两种画板"叙事；附 marker 阶梯对比条（half/braille/octant 各画同一测试圆）。**Splash 2.0**：手绘像素 wordmark（约 152×96 虚拟像素）+ 扫光/三层视差星空，四个风格包（neon/plasma/retro/starfield）美术身份保留，"任意键→menu"与永不超时契约不变。

## 范围
`sections/motion.py`、`sections/splash.py`；`demo/snake.py` 迁入或保留由派工单拍板。

## 验收
全量门禁绿；golden 全部重录并 `--check` 绿；60fps 帧预算实测（≤8ms/帧）写入 docstring；确定性重放逐字一致。

## 前置上下文
（W2-a 合并后由 lead 填写：PixelCanvas 用法、rings 行为契约誊写、风格包视觉规格）
