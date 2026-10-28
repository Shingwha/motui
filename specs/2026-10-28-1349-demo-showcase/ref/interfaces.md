# interfaces · 当前契约（lead 维护，合并后回写）

> 状态：**W1 合并后现实**（main：kernel pixel core + demo 新壳 + examples 退场；1646 passed / 10 golden / api 197）。

## motui.demo 公开面（红线，零变化）

```python
SCENES: tuple[str, ...]          # ("splash","menu","components","layout","motion",
                                 #  "dashboard","terminal","themes","snake","gallery")
PAGE_PHASE: int = 20
def render_scene(name, *, width, height, phase) -> str
def scene_output(...) -> ...
def main(argv=None) -> int       # python -m motui；TICK_HZ=60、App(throttle=1/60)
```

`motui.demo.showcase` 仍是场景类契约导入路径（纯 re-export 壳，禁加逻辑）：
`SplashScene / SnakeScene / DashboardScene / GalleryScene / SPLASH_ROTATE_TICKS`。
hub 场景名 `"menu"`（Home 瓷砖）；`"snake"` 与 `"motion"` 是同一对象（W3-b 拆分时保 `"snake"` 可用）。

## demo 内部结构（W1-b 现实）

```
demo/__init__.py   入口 + _commands（palette：7 条 jump + toggle status line + quit）
demo/shell.py      Showcase 壳：switch/tick/on_key/on_click、wipe（列裁剪 9 tick）、StatusLine
demo/sections/     __init__(Scene 协议+SCENES+_scenes)、splash、menu(瓷砖)、
                   placeholder(占位节：components/layout/terminal/themes)、dashboard、gallery
demo/snake.py      SnakeScene（W3-b 迁入 motion）
```

已知连带面：`_DASHBOARD_FPS=30` 被 `test_dashboard_clock_is_derived_from_phase` 钉死
（phase=30→"00:01.0"），节内 per-tick 动画墙钟速度因此 ×2；W3 调整须连契约测试一起改。
`test_smoke.py` 的 SCENES 断言已改为**成员断言**（注册表扩容授权）。

## kernel 像素核心（W1-a 现实，`motui.kernel` 导出 +9）

```python
BRAILLE_BITS / HALF_TOP("▀") / HALF_BOTTOM("▄") / HALF_FULL("█") / COOL_AT(192)

class Raster:                    # 色索引+热度双网格；width=cols*2, height=rows*4
    cols/rows/width/height; slot: bytearray; heat: bytearray
    clear(); decay(amount)                 # translate 表驱动，只减 heat
    set(x,y,slot=1); line(x0,y0,x1,y1,slot=1)
    rect(x0,y0,x1,y1,*,fill=False,slot=1); disc(cx,cy,r,slot=1); ring(cx,cy,r,thickness=1,slot=1)
    # 子格坐标浮点截断、出界静默裁剪、slot<=0 不写；图元写 slot 同时重置 heat=255
    # _HEAT_LIT=128：heat<128 视为熄灭

PixelLayer = tuple[Raster, Literal["half", "braille"]]

@dataclass(frozen=True, slots=True)
class PixelPalette:
    slots: Mapping[int, tuple[rgb_main, rgb_cool]]; bg: rgb
    # 构造时预建每槽 4 个 Style（main/cool × 带不带 bg）+ 纯 bg Style；身份稳定可跨帧复用

def quantize(layers: Sequence[PixelLayer], palette: PixelPalette) -> list[Line]
```

量化语义：层序即优先序（格归第一个有墨的层）；braille=多数槽位 fg、熄点透明；
half=▀▄█、style 恒带 bg；多数槽平手依次比峰值 heat、更小槽位号；峰值 heat≥COOL_AT
主色否则冷色；任一层 half 时空格带 bg（整片底色）；(char, style 对象身份) 融合 run。
性能实测（docstring）：稀疏单层 3.6ms、最坏双层 7.9ms / 76×24 帧。
W2-a 的 PixelCanvas 只消费这些名字；**任何调用方不得自带第二套量化逻辑**。

## golden / api 工具

```
uv run python tools/semantic.py --check | --update     # tests/golden/semantic/*.txt，现 10 场景
uv run python tools/api.py --check | --update          # tools/api-2.0.txt，现 197 名
```

## 环境陷阱（W1 实录）

- **Python 版本漂移**：main `.venv` 是 3.13.16；fresh worktree 里 uv 曾建出 3.12 venv，
  `PixelLayer` 别名的表面形状跨版本不同导致 api 面板 check 红。已加 `.python-version`(3.13)
  钉版本——新 worktree 务必确认 `uv run python --version` = 3.13.x 再动登记册类工具。
- `examples/` 已删除；历史讨论中的 `PixelDemo`/`FPS=60`/`_PALETTE` 等名字不复存在。
- `ruff format --check` 全仓 47 个文件基线即不合格——仓库红线只有 `ruff check`。

## 不变公共 API（禁触）

`tools/api-2.0.txt` 钉住的 motui 导出面（现 197 名）。后续波对 kernel/widgets 的**纯增**
必须走 `tools/api.py --update` 登记流程（`tests/kernel/test_kernel_imports.py` 的 EXPECTED
集合同步），保持测试全绿。
