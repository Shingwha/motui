# W1-a · pixel example 升级：色索引 Raster + 逐格色对 + 混合 marker
> 分支 `dm-w1a-pixel-example`；前置 无（并行波，与 W1-b 文件不相交）；写入范围 `examples/pixel.py`、`tests/test_examples.py`（追加 ≤1 条）

## 目标

把 `examples/pixel.py` 从"强度色带"升级为像素层的目标形态——**这份文件的最终 API 就是 W2-a kernel 抽取的契约来源，签名质量优先**。最高约束：三模式（rings/bounce/spin）的行为身份与确定性重放不变，单文件自包含、仅 stdlib、不碰 `src/`。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md`（examples/pixel.py 节）→ 本工单。无前置 handoff。
- 文件现状（约 600 行，lead 写的，可直接信任结构）：`Raster`（强度 bytearray + line/rect/disc/ring）、`quantize(raster, palette, underlay)`（4 强度色带逐格选样式）、`PixelDemo`（三模式）、`live()/headless()/main()`。
- 基线命令（开工先跑，贴真实输出）：
  `uv run pytest -q tests/test_examples.py`（3 passed）
  `uv run python examples/pixel.py --headless --frames 90 --every 26 --mode rings --hit 84`
- 已知性能基线：76×24 全流程 2.0–4.2 ms/帧（headless），docstring 已记录；升级后不得劣化超过 2×。
- 稳定区（勿重读）：`src/motui/` 全部——本工单不读不改 src，接口以 `ref/interfaces.md` 为准。

## 工单（按序执行，每项一个 commit）

### T1 Raster 存颜色索引 + 热度
- `Raster` 改为双网格：`slot`（颜色索引 0=空，1..N=槽位色）+ `heat`（0..255，衰减量）。图元签名统一为 `...(slot: int)`，内部以 `_SLOT_BASE` 查基色/热度。
- `decay(n)` 只减 heat；heat 低于阈值（现 `_ON=128`）即视为空。**冷却穿色**：heat 落入不同区间时映射到"更冷"的颜色（在量化层做，Raster 只存数）。
- 验证：`--headless --frames 60 --mode bounce` 拖尾仍平滑衰减（贴一帧）。

### T2 逐格 fg/bg 色对量化
- `quantize` 升级：每格取点亮子像素的多数槽位色做 fg；**半格 marker（填充）时未点亮子行用 bg 色**（默认近黑，可配）；braille marker 保持点亮=fg。
- palette 数据结构改为槽位表 `((id, (r,g,b), cool_variant), ...)`，替换现有 `(low, high, style)` 强度带。
- 验证：贴 rings 一帧的 Segment 序列（程序断言：目标盘格 fg=白槽、缩圈环格 fg=各自槽位色）。

### T3 half/braille 混合 marker
- 一帧内分区量化：**填充类图元（disc/rect fill）走 half（▀▄█ 实心）**，**曲线类（ring/line）走 braille**。实现形态自定（双 Raster 分层量化后合并，或单 Raster + 图元层标记），要求：`quantize` 签名能表达分层，W2-a 可原样抽取。
- 验证：bounce 模式球为实心块（无点阵缝），rings 缩圈环仍为细线；各贴一帧。

### T4 三模式适配 + 文档
- rings：槽位色轮换/入窗白闪/爆散着色全部迁移到槽位表；bounce：球白槽 + 冷却拖尾；spin：方块与双轨迹点各自槽位色。
- docstring 更新：新量化语义、混合 marker、重测的 ms/帧（真实数字）。
- 验证：三个模式 `--headless --frames 90 --every 26`（rings 加 `--hit 84`）各贴首末帧，肉眼核对动画连续。

### T5 测试
- `tests/test_examples.py` 追加 ≤1 条：subprocess 跑 `examples/pixel.py --headless --frames 3 --every 2 --mode rings`，returncode 0 且输出含 `pixel:` 行（照既有 3 条的风格）。

## 验收

1. `uv run pytest -q` 全绿（基线 1641 passed，贴真实输出）
2. `uv run ruff check .` 零告警
3. 三个模式 headless 帧转储动画正确（贴帧）；确定性：同参数两次运行逐字一致（`diff` 两次输出贴结果）
4. 每帧耗时写入 docstring（真实测量，注明 headless）

## 禁触清单

`src/**`、`tests/`（除 test_examples.py 追加一条）、其他 examples、golden。examples/pixel.py 之外的 examples 零 diff。

## 交接包

分支最后 commit 写 `handoff/W1-a-<agent>.md`。**A 节必须给出最终精确签名**：Raster 全部公开方法、quantize、槽位表结构、分层 marker 的表达方式——这是 W2-a 的抽取契约。B 节写清：色对选择的启发式（多数槽怎么定、bg 怎么选）、混合 marker 的实现形态与理由、冷却穿色的映射规则。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论（含两次运行 diff 证据）/ 偏差与取舍 / 交接校验（本波无）/ 探索审计 / 未决问题
