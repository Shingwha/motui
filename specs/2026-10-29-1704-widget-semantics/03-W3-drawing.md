# W3 · Drawing lifecycle

> 分支 `w2.1.2-w3-drawing`；起点 main @ `ca3e53c`。
> 写入范围：`src/motui/widgets/drawing.py`（新）、`canvas.py`、`pixel_canvas.py`、
> `src/motui/pixel/palette.py`、`tests/widgets/test_canvas.py`、
> `tests/widgets/test_pixel_canvas.py`、`tests/pixel/test_palette.py`、
> `tests/test_invariants.py`、`src/motui/demo/sections/motion/scene.py`、
> `src/motui/demo/sections/splash/scene.py`、`src/motui/demo/sections/terminal.py`。
> 前置：W0 已提交。最高约束：**本波的场景渲染字符不变**（semantic golden 全绿）。

## 目标

把 Canvas/PixelCanvas 的生命周期收敛到一个 `Drawing` 基类：尺寸由宿主显式
`resize`/`fit`，`surface()` 缓存，`render` 只裁剪不改尺寸。同时把
PixelCanvas 的 palette 默认改成从 theme 派生，把 `Canvas.marker` 改名为
`plot_marker`。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §8.3 → 本工单。
- 基线命令：

```bash
uv run pytest -q tests/widgets/test_canvas.py tests/widgets/test_pixel_canvas.py tests/pixel
uv run python tools/semantic.py --check
```

- 稳定区（勿重读）：`src/motui/pixel/raster.py`、`quantize.py`、`types.py`。
- 已知约束：
  - `Canvas` 用 cell 网格 + 行缓存；宽字符是 lead + continuation cell。
  - `PixelCanvas` 有两个 `Raster`（ART/FILL），`render` 当前会 resize；
    `palette` 是普通属性；`PixelPalette` 是 frozen dataclass，构造时会预建
    style quad。
  - splash 的 `render` 已经先 `self._canvas.resize(...)` 再 paint；motion 有
    `_fit_board`。本波要让这两个场景仍然输出同样的字符。
  - `Canvas(10, 1, marker=...)` 在 `demo/sections/terminal.py` 必须改成关键字
    构造和 `plot_marker`。

## 工单（按序执行，每项一个 commit）

### T1 `Drawing` 基类

- 新文件 `src/motui/widgets/drawing.py`，`class Drawing(Widget)`。
- 公开面：

```python
width: int; height: int        # setter 调 resize；负值 clamp 到 0
def resize(self, width, height) -> None
def surface(self) -> Surface   # 全尺寸；缓存到下一次 invalidate
def fit(self, c: Constraints) -> None
def render(self, c: Constraints) -> Surface
```

- `resize`：clamp、调用子类 `_resize_storage(width, height)`、清 surface 缓存、
  `touch()`。
- `surface()`：缓存未命中时调用子类 `_build_surface()`；返回全尺寸 Surface。
- `fit(c)`：`resize(c.width, c.max_height if c.max_height is not None else
  self.height)`。
- `render(c)`：取 `surface()`，按 `c.max_height` 截断行，返回
  `Surface.clipped(rows, c.width)`；**不调用 resize**。
- 子类钩子：`_resize_storage(width, height)`、`_build_surface()`、
  `_invalidate()`（清缓存 + touch，供绘制动词调用）。
- 只改新文件；`Drawing` 不从 `motui.widgets` 导出（W4a 再决定）。
- 验证：`uv run pyright src/motui/widgets/drawing.py`（若 pyright 未覆盖
  widgets，改用 `uv run python -c "import motui.widgets.drawing"`）。

### T2 Canvas 迁移

- `Canvas(Drawing)`；删除自己的 `resize`/`surface`/`render` 骨架，改成
  `_resize_storage`/`_build_surface`。
- 构造改为 `Canvas(*, width=0, height=0, plot_marker="cell", glyphs=GLYPHS,
  theme=None)`；删除 `styles`；`marker` 属性改名为 `plot_marker`。
- 所有写操作继续 `_invalidate()`（清行缓存 + surface 缓存 + touch）。
- `plot(..., marker=...)` 的参数名保留（它是单次 plot 的 marker，不是画布
  属性）；`self.marker` 的读取改成 `self.plot_marker`。
- `demo/sections/terminal.py` 的 `Canvas(10, 1, marker=name, theme=...)` 改为
  `Canvas(width=10, height=1, plot_marker=name, theme=...)`。
- 只改 `canvas.py` 和 `terminal.py`。

### T3 PixelPalette.from_theme + PixelCanvas 迁移

- `src/motui/pixel/palette.py` 增加 `PixelPalette.from_theme(theme)`：
  - slot 1..8 依次用 `content.accent`、`content.inline_code`、
    `status.success`、`status.warning`、`status.danger`、`content.heading[0]`、
    `text.muted`、`text.faint`。
  - 每个 token 的 `fg` 是 `Color`/hex/tuple 时取 RGB；否则用固定 fallback
    （accent `(77,232,210)`，其余见 `demo/palettes.py` 的 `pixel_palette`）。
  - cool = 每个通道 `round(c * 0.38)`。
  - `bg=None`。
- `PixelCanvas(Drawing)`；构造改为 `PixelCanvas(*, width=0, height=0,
  marker=Marker.BRAILLE, palette=None, theme=None)`；删除 `styles`。
- `palette=None` 时 `self.palette = PixelPalette.from_theme(self._theme)`；
  显式 palette 优先。`palette` 改成 property：赋值时 `_invalidate()`。
- `render` 只走基类；删除 render 里的 `_resize`。
- splash/motion：确保在 paint 前 `resize`/`fit`；如果原 render 依赖
  “render 自动 resize”，改成显式 `fit`/`resize`，但输出字符必须不变。
- 只改 `pixel_canvas.py`、`pixel/palette.py`、两个 demo 场景文件。

### T4 测试

- `tests/widgets/test_canvas.py`：构造关键字化、`plot_marker`、render 不改
  尺寸、fit 改尺寸、surface 缓存失效。
- `tests/widgets/test_pixel_canvas.py`：palette 默认派生、显式 palette 优先、
  render 不改尺寸、resize 重建栅格、palette 赋值失效缓存。
- `tests/pixel/test_palette.py`：`from_theme` 的 8 个 slot、cool 比例、fallback。
- `tests/test_invariants.py`：`_PIXEL_PALETTE` 构造不变（显式 palette）。
- 只改上述四个测试文件。

## 验收

1. 全量 `pytest` 全绿（贴用例数/失败项）。
2. `ruff`（含单文件 no-exclude）、`pyright`、`lint-imports` 全绿。
3. `tools/semantic.py --check` 全绿（这是硬门槛：场景字符不能变）。
4. `tools/framebench.py` 跑一遍，记录 `pixel-quantize`/`scene-*` 与
   `render-hash`；render-hash 必须不变。
5. `api.py --check` 会因 Canvas/PixelCanvas 构造变化而失败；不要改快照，
   报告差异给 lead。

## 禁触清单

`widgets/base.py`、`widgets/layout.py`、`kernel/cell.py`、`pixel/raster.py`、
`pixel/quantize.py`、`app/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W3-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W3-<agent>.md`：Drawing 的钩子签名、缓存失效规则、两个场景的
resize 位置、`api.py` 预期差异、framebench 数值。

## 最终报告

同 W1 模板。
