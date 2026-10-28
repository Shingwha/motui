# W3-b · Motion 双画板 + Splash 2.0（占位，W2-a 与 W1-b 均合并后补前置上下文再派工）
> 分支 `dm-w3b-motion-splash`（派工时定）；前置 W2-a + W1-b（以最新 main 为基线同步）；写入范围 `src/motui/demo/**`、golden 重录、新测试 ≤4 条

## 目标
**Motion 节**：PixelCanvas rings（判定游戏：键盘空格判定 + 鼠标踢球，语义以原 examples/pixel.py 为准——该文件此时已删，行为契约在本工单派工时由 lead 从对话纪要誊写）与 Canvas Snake 并列两模式，讲"两种画板"叙事；附 marker 阶梯对比条（half/braille/octant 各画同一测试圆）。**Splash 2.0**：手绘像素 wordmark（约 152×96 虚拟像素）+ 扫光/三层视差星空，四个风格包（neon/plasma/retro/starfield）美术身份保留，"任意键→menu"与永不超时契约不变。

## 范围
`sections/motion.py`、`sections/splash.py`；`demo/snake.py` 迁入或保留由派工单拍板。

## 验收
全量门禁绿；golden 全部重录并 `--check` 绿；60fps 帧预算实测（≤8ms/帧）写入 docstring；确定性重放逐字一致。

## 前置上下文
- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2-a-canvas.md`（PixelCanvas 全部签名与用法，A 节照抄即用）→ `handoff/W1-b-shell.md`（B 节：wipe/60Hz/占位节机制）→ 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（**1653 passed**）；`uv run python -m motui --pages` 看 motion/splash 现状。
- 稳定区（勿重读）：`demo/shell.py`、`demo/showcase.py`、`sections/menu.py`、`sections/components.py`、`sections/layout.py`、`sections/dashboard.py`、`sections/gallery.py`、`sections/terminal.py`、`sections/themes.py`（若 W3-a 并行进行中，两节文件禁触——你只动 `sections/motion.py`、`sections/splash.py`、`sections/__init__.py` 接线、`demo/snake.py` 是否迁移由下述拍板决定）、golden。
- 拍板：**`demo/snake.py` 不迁文件**。motion 节组合现有 `SnakeScene`（复用对象，"snake" 契约名不动）+ 新 rings 场景；`tests/test_demo_scenes.py` 的 snake 钉子因此天然安全。

### rings 行为契约（从已验证参考实现逐条誊写，视觉参数可按 PixelCanvas 双层微调，判定数值不得改）

- 出生：首个 +0.4s，此后每 1.2s；位置 = 槽位种子 RNG（`random.Random(20261028)`，resize 重置）在边距内均匀取点（边距 = min(34, 可用宽高的一半)，保证最大环 r=26 完整在画布内）；槽位色按并发序轮换。
- 缩圈：approach 1.0s，环半径 26 → 8 线性收缩；目标盘 r=8 常驻（出生时 ease_out_back 0.15s 弹入）。
- 判定（space）：对最近未判圈取误差 `|now − (born+1.0)|`——≤0.06 Perfect +300，≤0.12 Good +100，≤0.20 强行命中（combo 清零）；超窗未按 → Miss（combo 清零、attempts+1、原地冷色淡出）。Perfect/Good 计 hits。
- 入窗提示：误差 ≤0.12 时缩圈环白色闪烁（"现在按"）。
- 爆散：命中环 0.35s ease_out_back 向外 +20 过冲，色调按判定（Perfect 白 / Good 粉 / 强行冷色）。
- HUD：combo/score/hits-attempts；时间源 `runtime.clock()`，经壳层 tick 驱动；`--headless`/golden 必须逐字重放（seed 固定）。
- 性能预算：motion 节整帧 ≤8ms（PixelCanvas 实测最坏 10.5ms 是全亮双层；rings 是稀疏场景，余量足）。

### Splash 2.0 视觉规格

- 像素 wordmark：在 PixelCanvas（约 152×96 子格，按终端自适应）手绘 "MOTUI" 字形——不再用 5×7 点阵字体放大，直接以子格笔画设计（笔画粗 3–4 子格，保留原四风格包的配色身份：neon 青紫渐变+白扫光 / plasma 色相行走 / retro 琥珀绿 CRT+扫描线 / starfield 星野+glitch）。
- 动效：扫光用 decay 拖尾实现"流过"；starfield 三层视差（不同速度+缓动闪烁）；全部 phase 推导、确定性。
- 契约不变：永不超时（tick 永不返回转场）、任意键/点击 → `"menu"`；`--headless` 逐字重放；golden 重录逐条说明。
