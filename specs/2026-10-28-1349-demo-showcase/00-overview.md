# Spec demo-showcase · demo 整体重构：像素层进 kernel + examples 退场 + 七节新壳

> ✅ 已合并 2026-10-28 —— 七波全部落地 main（W1-a `dm-w1a-pixel-core`、W1-b `dm-w1b-demo-shell`、W2-a `dm-w2a-pixel-canvas`、W2-b `dm-w2b-sections`、W3-a `dm-w3a-report-themes`、W3-b `dm-w3b-motion-splash`），终验 1659 passed / ruff 零告警 / golden 10 场景 / api 198 名。rev 2，2026-10-28 14:05 重写：用户拍板"examples 全部删除、像素核心直接进 kernel，不留平行实现"）。启动：2026-10-28 13:49（UTC+8）；基线 main `148ce4a`；基线 `uv run pytest -q` = **1641 passed in 13.26s**；W1-b 合并后预期 **1638**（删 test_examples 3 条）。

## 目标

把 `python -m motui` 从"四个全屏场景硬切"重构为多节展示应用；像素层（Raster/量化器/PixelCanvas）**直接落地为框架能力**；`examples/` 整体退场，demo 成为唯一展示面。需求讨论拍板记录（不再重议）：

1. **像素以"画布类部件的量化能力"进框架**：kernel 层 `Raster` + `quantize`（blitter 阶梯）是承重结构；widget 层为 `PixelCanvas` 兄弟部件（不并入现有 `Canvas`）。量化产物永远是行模型。
2. **examples/ 全部删除**（用户拍板）：pixel.py 的算法语义已在本仓库对话中验证（原型/性能 2–4ms/帧/视觉），降级为 W1-a 的**参考实现**（读完即弃，W1-b 物理删除）；code/wide_table 的故事由 demo Layout 节讲；quickstart 内容 README 已有内联版。**任何 demo/框架代码不得自带第二套像素实现。**
3. **盲文降级为曲线专用档**：填充走 half（octant 为探测档），一帧内分区混合 marker。
4. **颜色模型 = 颜色索引 + 热度 + 逐格 fg/bg 色对**（chafa 式）；每格两色是字形路线物理天花板，sixel/kitty 真像素属远景档（本期不做，架构留位）。
5. **demo 七节**：Home 瓷砖（即 menu）、Components 游乐场、Layout 实操、Motion 双画板、Dashboard、Terminal 报告、Themes；每节指向一个库能力，不做游戏合集。hub 场景名保留 `"menu"`。

## 非目标

- sixel/kitty 位图档、xterm-1016 像素鼠标解码（留位不做）。
- `Canvas` 与 `PixelCanvas` 合并；`Canvas.plot()` 语义变化。
- `tools/api-2.0.txt` 钉住的公共 API 面板任何变化（kernel/widgets 新增为纯增项）。
- demo 之外的文档体系重写（README 的 demo/examples 段落随 W1-b 清扫对齐）。

## 全局不变量（红线，逐波适用）

1. `tests/test_demo_scenes.py` **零修改全绿**：`motui.demo.showcase` 继续可导入 `SplashScene/SnakeScene/DashboardScene/GalleryScene/SPLASH_ROTATE_TICKS`，`motui.demo` 继续导出 `SCENES/main/render_scene/scene_output/PAGE_PHASE`。
2. `uv run pytest -q` 波末全量绿（W1-a 期 1641，W1-b 起按删减后基数）；`uv run ruff check .` 零告警；`tools/semantic.py --check` 绿（重录发生在同波内并记录原因）。
3. 每波新增测试 ≤ 4 条。
4. 像素实现单一真相源：kernel 之外（demo/widgets）不得出现第二套 Raster/量化逻辑。
5. 确定性纪律：动画场景 seed 固定、时钟经 `advance()`，`--headless`/golden 逐字重放。
6. 注释/docstring 英文；commit 英文一行祈使句；不 push / 不发版；worker 不 merge。

## 波次表

| 波 | worker | 内容 | 写入范围 | 依赖 |
|---|---|---|---|---|
| **W1-a** | A | kernel 像素核心：`Raster`（色索引+热度）+ `quantize`（逐格色对、half/braille/mixed 阶梯），参考实现 `examples/pixel.py` | `src/motui/kernel/**`（新模块）、导出面、`tests/kernel/` 或 `tests/` 新文件（≤4 条） | — |
| **W1-b** | B | demo 新壳：sections/ 拆分、Home(menu) 瓷砖、wipe 过渡、StatusLine、60Hz、面板命令；**examples/ 退场** | `src/motui/demo/**`、删除 `examples/**` 与 `tests/test_examples.py`、README/pyproject/CI 引用清扫、`tests/golden/semantic/*`（重录）、`tests/test_demo_shell.py`（新，≤4 条） | — |
| W2-a | — | `PixelCanvas` widget + octant 探测 | `src/motui/widgets/`（新文件）、导出面、新测试 ≤4 条 | W1-a |
| W2-b | — | sections：Components 游乐场 + Layout 实操 | `src/motui/demo/sections/**`、golden | W1-b |
| W3-a | — | Terminal 报告节 + Themes 节 | `src/motui/demo/sections/**`、golden | W2-b |
| W3-b | — | Motion 双画板（PixelCanvas rings + Canvas snake）+ Splash 2.0 像素 wordmark | `src/motui/demo/**`、golden | W2-a + W1-b |
| 终验 | lead | 全量门禁 + `python -m motui --headless/--pages` + TTY 人工验收 | — | 全部 |

依赖图：W1-a ∥ W1-b →（W2-a ∥ W2-b）→（W3-a ∥ W3-b）→ 终验。并行波写入范围文件级不相交。

## 波次级门禁

每波合并前 lead 亲自跑：`uv run pytest -q` 全绿（贴用例数）、`uv run ruff check .` 零告警、`tools/semantic.py --check` 绿、diff 越界检查（handoff 外零越界）。合并后 lead 回写 `ref/interfaces.md` 并提交。

## 共享文件所有者

- `src/motui/demo/showcase.py`（兼容再导出壳）：W1-b 建立后为后续波的禁触文件（只加不改）。
- `tests/golden/semantic/*`：每波 worker 重录自己动过的场景并说明原因，lead 合并时核对。
- `ref/interfaces.md`：仅 lead 写。
- `examples/**`：W1-b 一次性删除（无共享）。

## 接口索引

当前现实见 `ref/interfaces.md`；W1-a 的目标 kernel API 在其工单内（合并后由 lead 回写为现实）。
