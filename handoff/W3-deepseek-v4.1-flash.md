# W3 交接包

> 分支 `w2.1.2-w3-drawing` / 起点 `main @ 561ed56`（工单文字写 `ca3e53c`，实际树同源）/ 2026-10-29
> 写入范围外唯一改动：`tests/widgets/test_invalidation.py` 一行（见 B.1）。

## A. 自动事实（命令与代码生成）

`git diff --stat main...HEAD`：10 files changed, 508 insertions(+), 202 deletions(-) --
`widgets/drawing.py`(new)、`widgets/canvas.py`、`widgets/pixel_canvas.py`、
`pixel/palette.py`、`demo/sections/terminal.py`、
`tests/widgets/{test_canvas,test_pixel_canvas,test_invalidation}.py`、
`tests/test_invariants.py`、`tests/pixel/test_palette.py`(new)。

公开接口（实际签名）：

- `Drawing(*, width=0, height=0, theme=None)`：`resize/fit/surface/render`、属性
  `width/height`（setter 走 resize）；钩子 `_resize_storage(width,height)`、
  `_build_surface() -> Surface`、`_invalidate()`。`resize` 对同尺寸是 no-op；
  `render` 只裁剪、绝不 resize；`fit(c)` 取 `(c.width, c.max_height or height)`。
- `Canvas(*, width=0, height=0, plot_marker="cell", glyphs=GLYPHS, theme=None)`；
  `styles` 与 `marker` 删除；`plot(..., marker=...)` 的单次覆盖保留。
- `PixelCanvas(*, width=0, height=0, marker=Marker.BRAILLE, palette=None,
  theme=None)`；`styles` 删除；`palette`/`marker` 是 property，赋值清 surface 缓存。
- `PixelPalette.from_theme(theme) -> PixelPalette`：8 slot（accent、inline_code、
  success、warning、danger、headings[0]、muted、faint），cool=38%，bg=None。

门禁真实结果：

- 起点：`pytest -q tests/widgets/test_canvas.py tests/widgets/test_pixel_canvas.py tests/pixel`
  → `22 passed`；`semantic.py --check` → `semantic: 9 scenes match`。
- 当前全量：`1671 passed, 2 failed`。两个失败都在 `tests/testing/test_api_tool.py`，
  唯一原因是 `tools/api-2.1.txt` 旧快照（预期差异见 B.3），非渲染/行为回归。
- `ruff check .` 全绿；改动文件的 `ruff check <paths> --config "exclude=[]"` 全绿；
  `pyright` 0 errors；`lint-imports` 5 contracts kept；semantic 仍 9/9。
- `framebench.py`（60 帧）：`pixel-quantize 9.54/11.03`、`scene-render 10.41/12.85`
  （splash）、`scene-paint 10.61/13.84`、`replay 809 ms`；
  **`render-hash e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da` 未变**。

## B. 只存在于脑子里的东西

1. **写入范围漏项（需 lead 授权）**：`tests/widgets/test_invalidation.py` 的
   `Canvas(4, 2)` 无法在 keyword-only 之后存活，而它不在工单写入范围。只改了这一个
   构造调用为 `Canvas(width=4, height=2)`，其余零改动。该文件在 no-exclude ruff 下
   仍有**既存** I001，未顺手修。
2. **T3 的两个场景零改动**：`splash` 原本就在 paint 前 `resize`，`motion._fit_board`
   也是；新 render 不再自动 resize 后字符未变（semantic 9/9 证明）。不要为“看起来
   该改”而重写它们。
3. **api 预期差异**（未改快照）：
   `~ motui.widgets:Canvas (shape changed)`、`~ motui.widgets:PixelCanvas (shape changed)`、
   `+ motui.widgets:PixelCanvas.fit (added)`、`+ motui.widgets:PixelCanvas.surface (added)`。
   `tools/api.py` 的 `MEMBER_TARGETS` 只 pin PixelCanvas，所以 Canvas 无成员行。
4. **PixelCanvas.render 语义变化**：旧 render 会按 constraint resize 并补齐宽度；
   新 render 只裁剪缓存。全仓调用方只有 splash/motion，均先自己 resize，故字节不变；
   若未来有宿主依赖“render 自动适配宽度”，必须改为显式 `fit`。
5. **同尺寸 resize no-op 是墨迹保留的关键**：Drawing.resize 对相同尺寸直接 return，
   PixelCanvas 才能“探测别宽度不丢墨”。旧 `_resize` 也有同样早退，别删。
6. **缓存失效**：`Widget.__setattr__` 对 property 赋值也会 touch；`palette`/`marker`
   setter 仍显式 `_invalidate()`（会再 touch 一次，无害）。任何新绘制动词必须调
   `_invalidate()`，否则 `surface()` 答旧值。
7. **`_resize_storage` 时基类已装好新 `_width/_height`**：Canvas 从 `len(_cells)`
   推断旧网格，PixelCanvas 直接重建 `Raster`。
8. **Canvas 的 B008 既存违规**：`Sparkline(style=Style())` 改成模块常量
   `_DEFAULT_STYLE`，值等价，仅为让 no-exclude ruff 全绿（canvas.py 在写入范围内）。
9. 不用碰：`pixel/raster.py`、`quantize.py`、`types.py`、`demo/palettes.py`
   （`pixel_palette` 仍是显式调色板路径）。
10. 下一波：`Drawing` **未**从 `motui.widgets` 导出，W4a 再决定；W4a 的契约测试
    可直接断言 `Canvas`/`PixelCanvas` keyword-only 与 `plot_marker`。

## C. 指针

- 基类：`src/motui/widgets/drawing.py:37`（hooks 145/154/158）。
- Canvas：`src/motui/widgets/canvas.py:67`（`_build_surface` 364，`plot` 314）。
- PixelCanvas：`src/motui/widgets/pixel_canvas.py:46`（palette 101，`_build_surface` 245）。
- 调色板派生：`src/motui/pixel/palette.py:94`。
- 场景调用点：`demo/sections/splash/scene.py:186`、`demo/sections/motion/scene.py:115`、
  `demo/sections/terminal.py:177`。
- commits：`f2728fa` T1 → `daf0cdb` T2 → `6c10fc2` T3 → `6ff39ae` T4 → 本 handoff。
- 稳定区（已验收）：上述五个源文件、四个测试文件；`tests/pixel/test_palette.py` 新增。
