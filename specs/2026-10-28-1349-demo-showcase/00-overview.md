# Spec demo-showcase · demo 整体重构：像素层落地 + 七节新壳

> ✅ 进行中。启动：2026-10-28 13:49（本地时间 UTC+8）；基线 main `bffcf64`；基线 `uv run pytest -q` = **1641 passed in 13.26s**。

## 目标

把 `python -m motui` 从"四个全屏场景硬切"重构为一个多节展示应用：像素层（Raster/量化器/PixelCanvas）落地为框架能力，demo 重排为一壳七节（Home 瓷砖、Components 游乐场、Layout 实操、Motion 双画板、Dashboard、Terminal 报告、Themes），并升级首页为像素 wordmark。需求讨论结论（拍板记录，不再重议）：

1. **像素以"画布类部件的量化能力"进框架**：kernel 层 `Raster` + `quantize`（blitter 阶梯）是承重结构；widget 层为 `PixelCanvas` 兄弟部件（不并入现有 `Canvas`）。量化产物永远是行模型，diff/DECSET 2026/选区/IME 全保留。
2. **盲文降级为曲线专用档**：填充走 half（后续 octant 探测档），一帧内分区混合 marker。
3. **颜色模型从"强度色带"升级为"颜色索引 + 逐格 fg/bg 色对"**（chafa 式）；字形路线的每格两色是物理天花板，真每像素一色属 sixel/kitty 远景档（本期不做，架构留位）。
4. **demo 七节结构**：每节只讲一句话、指向一个库能力；游戏只是能力载体，不做游戏合集。
5. hub 场景名保留 `"menu"`（Home 瓷砖即新 menu），splash 的"任意键 → menu"契约不动。

## 非目标

- sixel/kitty 位图档、xterm-1016 像素鼠标解码（架构留位，本期不做）。
- `Canvas` 与 `PixelCanvas` 合并；`Canvas.plot()` 语义变化。
- src 公共 API 的任何破坏性变化（`tools/api-2.0.txt` 钉住的面板零变化）。
- demo 之外文档重写（README 的 demo 段落随终验顺带对齐即可）。

## 全局不变量（红线，逐波适用）

1. `tests/test_demo_scenes.py` **零修改全绿**：`motui.demo.showcase` 必须继续可导入 `SplashScene/SnakeScene/DashboardScene/GalleryScene/SPLASH_ROTATE_TICKS`，`motui.demo` 必须继续导出 `SCENES/main/render_scene/scene_output/PAGE_PHASE`。
2. `uv run pytest -q` 波末全量绿；`uv run ruff check .` 零告警；`uv run python tools/semantic.py --check` 绿（重录必须发生在同波内并记录原因）。
3. 每波新增测试 ≤ 4 条。
4. src 公共 API（api-2.0 面板）零变化；kernel 新增为纯增项。
5. 注释与 docstring 英文；commit 英文一行祈使句；确定性纪律：所有动画场景可 `--headless`/golden 逐字重放（seed 固定、时钟经 `advance()`）。
6. 不 push / 不发版 / 不打 tag；worker 不 merge。

## 波次表

| 波 | worker | 内容 | 写入范围 | 依赖 |
|---|---|---|---|---|
| **W1-a** | A | pixel example 升级：色索引 Raster + 逐格色对 + half/braille 混合 marker | `examples/pixel.py`、`tests/test_examples.py`（+≤1 条） | — |
| **W1-b** | B | demo 新壳：sections/ 拆分、Home(menu) 瓷砖、wipe 过渡、StatusLine、60Hz、面板命令 | `src/motui/demo/**`、`tests/golden/semantic/*`（重录）、`tests/test_demo_shell.py`（新，≤4 条） | — |
| W2-a | — | kernel 抽取：`Raster`/`quantize` 纯值 + 确定性测试 | `src/motui/kernel/**`（新模块）、导出面 | W1-a |
| W2-b | — | sections：Components 游乐场 + Layout 实操 | `src/motui/demo/sections/**`、golden | W1-b |
| W3-a | — | `PixelCanvas` widget + octant 探测 | `src/motui/widgets/**`、导出面、golden | W2-a |
| W3-b | — | Terminal 报告节 + Themes 节 | `src/motui/demo/**`、golden | W2-b（octant 探测可后补联动） |
| W4 | — | Motion 节（rings+snake 双画板）+ Splash 2.0（像素 wordmark） | `src/motui/demo/**`、golden | W3-a + W1-b |
| 终验 | lead | 全量门禁 + `python -m motui --headless/--pages` + 三 examples 抽验 | — | 全部 |

依赖图：W1-a ∥ W1-b →（W2-a ∥ W2-b）→（W3-a ∥ W3-b）→ W4 → 终验。并行波写入范围文件级不相交。

## 波次级门禁

每波合并前 lead 亲自跑：`uv run pytest -q` 全绿（贴用例数）；`uv run ruff check .` 零告警；`uv run python tools/semantic.py --check` 绿；diff 越界检查（handoff 外零越界）。合并后 lead 提交 `ref/interfaces.md` 回写。

## 共享文件所有者

- `src/motui/demo/showcase.py`（兼容再导出壳）：W1-b 建立后为 W2-b/W3-b/W4 的禁触文件（只加不改）。
- `tests/golden/semantic/*`：每波 worker 自己重录自己动过的场景，lead 合并时核对 `--check`。
- `ref/interfaces.md`：仅 lead 写。

## 接口索引

见 `ref/interfaces.md`（当前现实）；每波合并后更新。
