# W1-a · kernel 像素核心：Raster + quantize
> 分支 `dm-w1a-pixel-core`；前置 无（并行波，与 W1-b 文件不相交）；写入范围 `src/motui/kernel/`（新模块 + `kernel/__init__.py` 导出）、`tests/`（新文件 ≤4 条）

## 目标

像素层核心落地为 kernel 纯值/纯函数：`Raster`（色索引 + 热度子格网格）与 `quantize`（逐格 fg/bg 色对、half/braille/mixed marker 阶梯）。最高约束：**量化产物永远是行模型（`Line` 列表），零 I/O、零终端知识**，对齐 kernel 既有纪律（frozen 值、无 os/sys 导入）。本模块是 PixelCanvas（W2-a）与 demo（W3-b）的唯一实现，**不允许任何调用方自带第二套**。

## 参考实现（读完即弃）

`examples/pixel.py` 是已验证的原型（本仓库对话中迭代定型）：算法、性能特征、坑都以它为准——但**它存的还是强度网格 + 4 色带，你要交付的是目标形态**（下述契约）。只读它，不改它（W1-b 会删掉它）。实测基线：76×24 全流程 2.0–4.2 ms/帧 headless；你的实现（双网格 + 分层量化）≤ 10 ms/帧即达标。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `examples/pixel.py`（参考实现）→ 本工单。
- kernel 既有风格：读 `src/motui/kernel/cell.py`（`Line`/`Segment`/`Surface` 的构造与身份语义）与 `src/motui/kernel/__init__.py`（导出方式）。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（1641 passed）。
- 已知坑（来自参考实现的迭代史，直接继承结论）：
  - 逐格 `put` 进 Canvas 的簿记开销让 76×24 帧到 13ms——**必须直接构 `Line`/`Segment`**，相邻同 `(char, style)` 融合 run，同 style 用对象身份短路比较；
  - `decay` 用 `bytes.translate` 表驱动（全网格 C 速度），不要写 Python 逐字节循环；
  - 盲文点阵编码 `U+2800 + bits`，位序 `(列,行)` 为 `((0x01,0x02,0x04,0x40),(0x08,0x10,0x20,0x80))`（点 1 在左上）；空格 fuse 用普通空格而非 U+2800，diff 才干净；
  - half marker：上 `▀` 下 `▄` 双亮为 `█`，未点亮的半行透 bg 色。

## 工单（按序执行，每项一个 commit）

### T1 `Raster`：色索引 + 热度双网格
- 几何：`cols×rows` 格，子格 `width = cols*2`、`height = rows*4`（盲文几何；half 档按行对折使用）。
- 双 bytearray：`slot`（0=空，1..255 槽位）+ `heat`（0..255）。`set(x, y, slot)` 点亮并重置该子格 heat 为满；`decay(n)` 只减 heat，heat 低于阈值（常量 `_HEAT_LIT = 128`）视为空。
- 图元：`line`（Bresenham）、`rect`（fill 开关）、`disc`（逐行跨度填充）、`ring`（参数化，thickness）。全部接受槽位号、静默裁剪、坐标为子格整数。
- `clear()` 双网格归零。模块常量：`BRAILLE_BITS`、`HALF_TOP/HALF_BOTTOM/HALF_FULL`。
- 验证：直测——已知操作序列断言 slot/heat 网格精确值（新测试文件，≤2 条覆盖图元与衰减）。

### T2 调色板与逐格色对量化
- 调色板是**调用方传入的值**（kernel 不内置主题）：`PixelPalette`（frozen）——槽位表（id → 主色 rgb + 冷色 rgb）+ bg 色。`quantize` 依据 (slot, heat) 选 Style：heat 饱和用主色，低于 `COOL_AT` 用冷色（冷却穿色）。
- 每格：取点亮子像素的**多数槽位**为 fg 色；half 档未点亮子行透 bg；braille 档熄点透 bg。
- 量化签名（契约，W2-a 直接消费）：
  `quantize(layers, palette) -> list[Line]`，`layers` 为 `Sequence[PixelLayer]`，
  `PixelLayer = (raster, marker)`（frozen tuple 即可），marker ∈ `"half"|"braille"`；
  合并语义：**上层有墨覆盖下层，同格先到先得按层序**——"mixed" 就由调用方传两个 layer 表达（填充层 half + 线条层 braille），kernel 不内置 mixed 字符串。
- 每格两色天花板写进模块 docstring（行业事实：字形 = 单色模板 + SGR fg/bg）。
- 验证：直测——手工小网格（如 2×2 格）断言产出 `Line` 的精确 `Segment` 序列与样式对象。

### T3 导出与红线核对
- `kernel/__init__.py` 导出新名字；跑 `uv run pytest -q tests/test_api.py` 与 `uv run python tools/api.py`（或其检查入口）确认 api-2.0 面板机制不拒绝纯增导出（若该面板要求登记新名字，按工具既有流程登记——这是"纯增"不是"修改"）。
- 性能验收：临时脚本量 76×24 双层量化的 ms/帧（headless），真实数字写进模块 docstring，≤10ms 达标。

### T4 测试与收尾
- 新测试文件（`tests/kernel/test_pixel.py` 或按 tests/kernel 既有布局）共 ≤4 条：图元+衰减、量化逐字断言、分层合并顺序、run 融合与身份短路。
- 全量回归 + ruff。

## 验收

1. `uv run pytest -q` 全绿（基线 1641 passed，贴真实输出）
2. `uv run ruff check .` 零告警
3. `tests/test_api.py` 绿（公共 API 面板纯增不破坏）
4. 性能数字真实测量并写入 docstring（≤10ms/76×24 帧）
5. `git diff --stat` 显示 src 变更只在 kernel 与导出面

## 禁触清单

`examples/**`（W1-b 删）、`src/motui/demo/**`、`src/motui/widgets/**`、`src/motui/app/**`、`src/motui/terminal/**`、`tests/golden/**`、既有测试文件（只新建）。

## 交接包

分支最后 commit 写 `handoff/W1-a-core.md`（`specs/2026-10-28-1349-demo-showcase/handoff/`）。A 节：全部最终精确签名（Raster/PixelPalette/quantize/PixelLayer/常量）、性能实测、导出面变化。B 节：色对启发式细节、marker 分层的调用方用法示例（W2-a 照抄即用）、与参考实现的偏差及原因。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 / 偏差与取舍 / 交接校验（无前置）/ 探索审计 / 未决问题
