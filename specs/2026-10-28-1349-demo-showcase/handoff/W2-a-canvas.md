# handoff · W2-a PixelCanvas widget

分支 `dm-w2a-pixel-canvas`（基于 main `1468820`），3 个 commit，波末全量
`uv run pytest -q` = **1650 passed**（基线 1646 + 本波 4 条），`uv run ruff check .`
零告警，golden 10 场景 match，`tools/api.py --check` = 198 名（+1 纯增）。
环境实测 `uv run python --version` = **3.13.16**（`.python-version` 钉生效）。
W3-b demo Motion 节只消费本文件 A 节的签名。

## A · 自动事实（契约，照抄即用）

### 模块与导出

`src/motui/widgets/pixel_canvas.py`，只 import kernel（cell/layout/pixel）+ `base.Widget`。
`motui.widgets` 新增导出 `PixelCanvas`；登记册已同步：`tools/api-2.0.txt`（198 名，
+1 纯增）、`tests/test_invariants.py`（CASES 矩阵 + `_PIXEL_PALETTE`——**这个矩阵就是
widget 导出的登记册**，`public == set(CASES)` 完备性测试会红）。根包 `motui` 不动
（Canvas 也不在根包，PixelCanvas 同样只住 widgets 层）。

### 构造与公开面（精确签名）

```python
class PixelCanvas(Widget):        # __slots__: _art/_cols/_fill/_rows/marker/palette
    PixelCanvas(width: int = 0, height: int = 0, *,
                marker: str = "braille",          # "half" | "braille"，ValueError 其余
                palette: PixelPalette,            # 必填关键字，无默认（颜色归调用方）
                theme=None, styles=None) -> None

    marker: str            # 公开属性（写经 Widget.__setattr__ → touch）
    palette: PixelPalette  # 同上；两者换值即时生效于下一帧 render

    # 几何：单位是“格”（cell）；每格 = 2x4 子格
    width -> int  /  width = v          # property + setter（setter 重建 buffer）
    height -> int /  height = v
    resize(width: int, height: int) -> None

    # 两个栅格只读出口（栅格本体是 kernel 公开可变状态）
    art  -> Raster    # 线条/精灵层，以 marker 分辨率量化（上层，优先得格）
    fill -> Raster    # 背景块层，恒以 "half" 量化（下层；空格因此带 palette.bg）

    # art 层便捷动词（全部 touch；浮点截断、出界静默裁剪，同 Raster）
    set(x, y, slot=1) -> None
    unset(x, y) -> None                        # 唯一擦除动词（见 B 节）
    line(x0, y0, x1, y1, slot=1) -> None
    rect(x0, y0, x1, y1, *, fill=False, slot=1) -> None
    disc(cx, cy, r, slot=1) -> None
    ring(cx, cy, r, thickness=1, slot=1) -> None
    decay(amount: int) -> None                 # 只衰减 art（fill 永不衰减）
    clear() -> None                            # 双层都清（整个画布归零）

    # fill 层便捷动词（其余动词直接用 canvas.fill 的 Raster 方法）
    fill_set(x, y, slot=1) / fill_rect(..., *, fill=False, slot=1)
    fill_disc(cx, cy, r, slot=1) / fill_clear()

    render(c: Constraints) -> Surface          # 唯一量化出口
```

### render 语义

`render(c)` 先把 buffer 几何同步到约束：`cols = c.width`，
`rows = c.max_height if c.max_height is not None else 当前行数`；几何变化即**重建空
Raster**（丢墨，按合同像素场景每 tick 重画），随后
`Surface.of(quantize(((art, marker), (fill, "half")), palette), c.width)`。
`c.width == 0` 或行数为 0 → `Surface(width=c.width, rows=())`。
不缓存：栅格公开可直写，脏状态不可跟踪，每帧全量重量化。

### octant 探测方案现状（拍板记录）

工单留给派工拍板的两案，落定为**显式配置项**，且本波未实现任何探测代码：

- widget 层不能发探针：widgets 包纪律是只 import kernel（无 terminal/keys/screen），
  测宽探针需要裸终端控制，架构上不属于 widget。
- kernel `PixelLayer` 的 marker 词表只有 `half/braille`（W1-a 契约）——即使探测出
  octant 支持，widget 侧也没有可用的 octant 量化路径；widget 侧自拼 octant 字形
  就是“第二套量化”，被红线禁止。
- 结论：等 kernel 词表长出 `"octant"` 后，PixelCanvas 的 `_MARKERS` 扩一词即可接上；
  “这台终端要不要 octant”由宿主显式传入（配置或 terminal 层的探测结果），widget
  永不探测。模块 docstring 已按此口径写明。**本波无 kernel 缺陷需补丁**；唯一可选
  的后续改进见 B 节（`Raster.unset`）。

### W3-b 调用方骨架（照抄即用）

```python
from motui.kernel.pixel import PixelPalette
from motui.widgets import PixelCanvas

PALETTE = PixelPalette(slots={1: ((255,255,255),(150,150,170))}, bg=(12,12,16))

class MotionScene:
    def __init__(self): self.canvas = PixelCanvas(palette=PALETTE)
    def render(self, c, phase):
        return self.canvas.render(Constraints(width=c.width, max_height=c.max_height))
    def tick(self, phase):
        self.canvas.decay(26); self.canvas.set(x, y, slot=1)   # trail + draw
        self.canvas.fill_disc(...)                              # 背景块
```

### 性能实测（76 格 x 24 格，本机 CPython 3.13.16 / Windows）

“帧经 widget 全流程” = `canvas.render(Constraints(76, 24))` 整次调用：

- 最坏双层（每格双层混色、half 全屏底 + braille 横线铺满）：300 帧均值
  **9.95–10.5 ms**，p50 **6.7–11.3 ms**（跨轮次机器噪声大）；钉死的测试取
  7 样本中位数 ≤ 12.0 ms，通过但余量薄（见 B 节）。
- 稀疏单线（demo 形态近似）：300 帧均值 **7.2 ms**。
- 开销解剖：quantize 本体 ~4.6–4.8 ms；`Surface.of` 触发的 `Line.width` 惰性物化
  ~5.8 ms——但 painter 每帧也读 `row.width`（`terminal/paint.py:174`），这笔账是
  帧成本 intrinsic，只是由 render 提前付；widget 自身逻辑（同步检查 + 图层组装）
  <0.1 ms。诚实口径：12 ms 红线含这笔，达标。

## B · 偏差与坑

- **marker 语义拍板**：工单只说“marker 由构造参数定层组织”。落定为：`marker`
  是 **art 层**的分辨率（`half/braille`），fill 层恒 `half`——这正是工单点名的
  “填充层 half / 线条层 braille”组织，且让“任一层 half → 空格带 bg”恒成立
  （PixelCanvas 渲染永远整片 palette.bg，不会透出终端底色）。demo 若想透底：
  目前无开关（layer 组织写死），需要时加构造参数即可，属纯增。
- **`unset` 走公开 bytearray**：kernel Raster 没有擦除动词（`set` 的 `slot<=0`
  是 no-op），widget 端直写 `raster.slot`/`raster.heat`（布局 row-major，
  `index = y * width + x`，已实测验证；heat 每次现取——`decay` 会换新 bytearray）。
  若 kernel 将来收编一个 `Raster.unset(x, y)`，widget 的 unset 改一行转发即可
  （最小补丁建议，非缺陷，本波不动 kernel）。
- **子格坐标坑（写测试时踩过）**：cell 行号 = `y // 4`，不是 `y // (4*rows)`；
  half 折叠按每格的子行 0-1（上）/2-3（下）。`fill_set(0, 2)` 落在**第 0 格行**
  的下半（▄），要到第 1 格行下半得 `y = 4 + 2`。braille 位序见 W1-a handoff
  （`(子列, 子行) -> 位`，点 1 在左上），`set(2, 0)` 是第 1 格左列顶点（⠁ 不是 ⠈）。
- **render 重建 vs invariants 矩阵**：`tests/test_invariants.py` 会以
  `Constraints(width=0..80)` 反复 render 同一实例并要求幂等/无漂移——本 widget
  语义是“变尺寸即重建空 buffer”，矩阵能过仅因矩阵工厂**不预画内容**；真实消费方
  变尺寸会丢墨（docstring 已声明，像素场景每 tick 重画所以无所谓）。W3-b 别在
  render 尺寸抖动的宿主里指望跨帧保墨。
- **性能钉测试的余量**：最坏形态 p50 跨轮次 6.7–11.3 ms，12.0 ms 阈值在噪声大的
  轮次只剩 ~6% 余量。若 CI 偶发红，先看是否机器负载问题；真超了再谈缓存或
  quantize 优化（动 quantize 前先保住单槽位快路径，见 W1-a B 节）。
- **登记流程实录**：widget 纯增导出要碰三处——`widgets/__init__.py`（import+__all__）、
  `tests/test_invariants.py`（CASES + import + 调色板常量）、`tools/api.py --update`
  （api-2.0.txt +1）。`tests/test_api.py` 是结构测试不用动。
- docstring/注释英文、commit 英文祈使句、每任务一个 commit 均已遵守；
  测试恰 4 条（`tests/widgets/test_pixel_canvas.py`）：量化分层逐字断言、
  unset+衰减生命周期、几何重建、性能钉。

## C · 指针

- 实现：`src/motui/widgets/pixel_canvas.py`；导出：`src/motui/widgets/__init__.py`
- 测试：`tests/widgets/test_pixel_canvas.py`；登记册：`tests/test_invariants.py`、
  `tools/api-2.0.txt`
- 上游契约：`handoff/W1-a-core.md` A 节（未变）；下游工单：W3-b demo Motion 节
