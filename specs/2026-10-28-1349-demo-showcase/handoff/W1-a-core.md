# handoff · W1-a kernel pixel core

分支 `dm-w1a-pixel-core`（基于 main `bffcf64`），5 个 commit，波末全量
`uv run pytest -q` = **1645 passed**（基线 1641 + 本波 4 条），`uv run ruff check .`
零告警。W2-a PixelCanvas 与 W3-b demo 只消费本文件 A 节的签名。

## A · 自动事实（契约，照抄即用）

### 模块与导出面

`src/motui/kernel/pixel.py`，stdlib only（math/dataclasses/types/typing +
kernel 内部 `.cell`/`.style`）。`motui.kernel` 新增导出 9 个：
`BRAILLE_BITS, COOL_AT, HALF_BOTTOM, HALF_FULL, HALF_TOP, PixelLayer,
PixelPalette, Raster, quantize`。登记册已同步：`tools/api-2.0.txt`（+9 行，纯增）、
`tests/kernel/test_kernel_imports.py`（EXPECTED 集合 + 模块隔离清单 +`motui.kernel.pixel`）。

### 常量

```python
BRAILLE_BITS: tuple[tuple[int, int, int, int], tuple[int, int, int, int]] = (
    (0x01, 0x02, 0x04, 0x40),
    (0x08, 0x10, 0x20, 0x80),
)                # 点位 (子列, 子行) -> 位；点 1 在左上；字形 = chr(0x2800 + bits)
HALF_TOP = "\u2580"      # ▀  仅上两子行亮
HALF_BOTTOM = "\u2584"   # ▄  仅下两子行亮
HALF_FULL = "\u2588"     # █  上下都亮
COOL_AT = 192            # 主体主色 / 冷色分界（heat >= 192 主色）
# 模块私有：_HEAT_LIT = 128（heat < 128 的子格视为熄灭，slot 字节作废）
```

### Raster（色索引 + 热度双网格）

```python
class Raster:
    cols: int; rows: int            # 格
    width: int; height: int         # 子格：width == cols*2, height == rows*4
    slot: bytearray                 # 0=空，1..255 槽位号
    heat: bytearray                 # 0..255 新鲜度；set 重置为 255，decay 衰减
    def __init__(self, cols: int, rows: int) -> None
    def clear(self) -> None                       # 双网格归零
    def decay(self, amount: int) -> None          # 只减 heat（bytes.translate，C 速）
    def set(self, x: float, y: float, slot: int = 1) -> None
    def line(self, x0: float, y0: float, x1: float, y1: float, slot: int = 1) -> None
    def rect(self, x0: float, y0: float, x1: float, y1: float, *,
             fill: bool = False, slot: int = 1) -> None
    def disc(self, cx: float, cy: float, r: float, slot: int = 1) -> None
    def ring(self, cx: float, cy: float, r: float, thickness: int = 1, slot: int = 1) -> None
```

坐标是子格位置，浮点截断（`int()`）；出界静默裁剪；`slot <= 0` 不写。
所有图元点亮子格时**同时写 slot 与 heat=255**。

### PixelPalette / PixelLayer / quantize

```python
PixelLayer = tuple[Raster, Literal["half", "braille"]]

@dataclass(frozen=True, slots=True)
class PixelPalette:
    slots: Mapping[int, tuple[tuple[int, int, int], tuple[int, int, int]]]
    bg: tuple[int, int, int]
    # 构造时冻结并预建每槽 4 个 Style（main/cool × 无bg/带bg）+ 纯 bg Style；
    # 未登记槽位回退白色 fg。slot id 必须在 1..255，否则 ValueError。

def quantize(layers: Sequence[PixelLayer], palette: PixelPalette) -> list[Line]
```

量化语义（每格两色天花板写在模块 docstring）：

- 层序即优先序：**格归属序列中第一个有墨的层**（上层有墨覆盖下层，同格先到
  先得按层序）；kernel 不内置 "mixed"，调用方传两个 layer 表达。
- `braille`：`chr(0x2800 + bits)`，fg 取该格点亮子格的**多数槽位**色，fg-only
  （熄点透明）；`half`：上两子行/下两子行折叠，`▀/▄/█`，style 恒带
  `bg=palette.bg`（未亮半行透 bg）。多数槽位 = 点亮子格计数最多者，平手依次比
  峰值 heat、更小槽位号；该槽位峰值 heat `>= COOL_AT` 用主色，否则冷色。
- 无墨格：纯空格（无 style）；**若任一层用 `half`，空格带 `bg=palette.bg`**
  （这就是"填充层"——传一个 half 层即得整片底色）。
- 相邻同 (char, style **对象身份**) 融合为一个 `Segment`；调色板预建并复用
  Style 对象，跨帧身份稳定，身份短路是融合的全部机制。
- 全层几何不一致 → `ValueError`；未知 marker → `ValueError`；空 layers → `[]`。

### W2-a 调用方用法示例（可照抄）

```python
from motui.kernel.pixel import PixelPalette, PixelLayer, Raster, quantize

PALETTE = PixelPalette(                 # 模块级建一次（值冻结）
    slots={
        1: ((255, 255, 255), (150, 150, 170)),  # id: (主色, 冷色)
        2: ((255, 130, 190), (150, 70, 110)),
    },
    bg=(12, 12, 16),
)

class PixelCanvas(Widget):
    def render(self, c: Constraints) -> Surface:
        ...  # 尺寸变化时重建 Raster(cols, rows)
        fill = self._fill                   # Raster：half 填充层（整片 bg + 大色块）
        art = self._art                     # Raster：braille 线条层（上层优先）
        rows = quantize(((art, "braille"), (fill, "half")), PALETTE)
        return Surface.of([hud_row, *rows, hint_row], c.width)
    def tick(self, now: float) -> None:     # 写 raster；trail 用 decay
        self._fill.clear(); ...draw...; self._art.decay(26); ...draw...
```

### 性能实测（docstring 同款数字）

76×24，CPython 3.12.14 / Windows，300 帧均值，`quantize` 纯量化：

- demo 形态稀疏单层（297/1824 格有墨）：**3.6 ms/帧**
- 最坏压测双层（1824/1824 格全亮、多槽位混色、half 全屏底 + braille 密线）：
  **7.9 ms/帧**（首次实现 17.1 ms，优化点见 B 节）

结论：≤10ms 达标；60fps 预算（16.7ms）内。decay 本身是单次
`bytes.translate`（C 速），不占 Python 预算。

## B · 脑内知识

- **单槽位快路径是性能的命门**：绝大多数格只含一个槽位。扫描时跟踪
  `(solo, solo_n, peak)`，只在出现第二个槽位时才建 dict 走 `_majority`
  投票。首版每格无条件建 dict + `max()+lambda` + 函数调用 → 17ms；
  快路径 + 展开偏移表（`((bit, offset), ...)` 相对格左上角）+ 内联选色 →
  7.9ms。W2-a 若改动 quantize，先保住这条快路径。
- **融合靠身份不靠 `==`**：调色板在 `__post_init__` 一次建齐 4×槽位数的
  Style 对象，quantize 每格只做 `styles.get(slot)`；同格态跨帧跨格都是同一
  对象，`style is run_style` 短路。不要在 quantize 里现造 Style。
- **与参考实现 examples/pixel.py 的偏差及原因**：
  - 参考实现是强度网格 + 4 色带；本实现按工单改为 slot+heat 双网格 +
    调色板值对象（槽位识别对象身份，颜色由调用方给，kernel 不内置主题）。
  - 参考实现 `underlay=(raster, style)` 双层特殊参数；本实现推广为
    `Sequence[PixelLayer]`，归并语义"第一有墨层得格"。参考实现的
    underlay 用法等价于 `[(main, "braille"), (under, "braille")]`。
  - 参考实现 `set(x, y, intensity)` 带强度带选色；本实现 `set(x, y, slot)`
    强度语义移到 heat（`set` 恒 255 起点，`decay` 造渐变）。
  - 继承未动的坑：`bytes.translate` 表驱动衰减；盲文位序
    `((0x01,0x02,0x04,0x40),(0x08,0x10,0x20,0x80))`；half 双亮为 `█`、
    未亮半行透 bg；直接构 `Line`/`Segment` 绕开 Canvas 簿记。
  - `raster.heat` 在 decay 后是**新 bytearray**（translate 返回值）——外部
    若缓存了旧引用会读到旧网格，W2-a 每帧从 `raster.heat` 现取即可。
- **量化是纯函数**：不 mutate 传入 raster；同一 (layers, palette) 恒等输出，
  可安全用于确定性重放（配合 `random.Random(seed)` + `runtime.clock()`）。
- 测试文件 `tests/kernel/test_pixel.py` 恰 4 条：图元+衰减精确值、量化逐字
  断言（含衰减穿色、空格透 bg、白fallback）、层序合并、融合与身份。

## C · 指针

- 实现：`src/motui/kernel/pixel.py`（唯一实现，禁止第二套）；导出：
  `src/motui/kernel/__init__.py`
- 测试：`tests/kernel/test_pixel.py`；登记册：`tests/kernel/test_kernel_imports.py`、
  `tools/api-2.0.txt`
- 行为基准（读完即弃，W1-b 删）：`examples/pixel.py`（主检出未跟踪文件，
  worktree 里没有）
- 下游工单：`specs/2026-10-28-1349-demo-showcase/02-W2-a-pixel-canvas.md`
  （PixelCanvas 只消费 A 节签名）；性能复测可仿 A 节数字的测法
  （300 帧均值、双层最坏 + 稀疏单层两个口径）
