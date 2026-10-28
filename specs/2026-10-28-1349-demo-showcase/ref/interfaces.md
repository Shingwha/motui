# interfaces · 当前契约（lead 维护，合并后回写）

> 状态：W1 派工前草案（基于 main `bffcf64` 实读）。worker 只读此文件，不自行重新考古。

## motui.demo 公开面（红线，零变化）

```python
SCENES: tuple[str, ...]          # 场景名注册表；golden 按 SCENES 全覆盖
PAGE_PHASE: int = 20             # headless 快照的固定 phase
def render_scene(name, *, width, height, phase) -> str   # 仅供测试/快照
def scene_output(...) -> ...     # 同上（见 demo/__init__.py:79）
def main(argv=None) -> int       # python -m motui 入口
```

`motui.demo.showcase` 额外必须可导入（tests/test_demo_scenes.py 钉住，零修改）：
`SplashScene / SnakeScene / DashboardScene / GalleryScene / SPLASH_ROTATE_TICKS`。
hub 场景名保留 `"menu"`（splash 的 on_key/on_click → `"menu"` 契约被钉）。

## Scene 协议（demo 内部，W1-b 可扩展不可破坏）

```python
class Scene(Protocol):
    name: str
    def render(self, c: Constraints, phase: int) -> Surface: ...
    def tick(self, phase: int) -> str | None: ...      # 返回转场目标
    def on_key(self, event: KeyEvent) -> str | None: ...
    def on_click(self, pos: Pos) -> str | None: ...
```

`Showcase(Widget)`：`scene: str`、`phase: int`、`switch(name)`、`tick()`、`on_quit` 回调、
`_scenes` 注册表由 `_scenes(theme, seed) -> dict[str, Scene]` 构造。

## examples/pixel.py 当前 API（W1-a 的改造对象；W1-a 后为 W2-a 的抽取契约来源）

```python
class Raster:                    # 强度网格：width=cols*2, height=rows*4
    cols/rows/width/height/grid: bytearray   # 0..255 强度
    clear() / decay(amount) / set(x, y, intensity=255)
    line(x0,y0,x1,y1,intensity) / rect(x0,y0,x1,y1,fill=False,intensity)
    disc(cx,cy,r,intensity) / ring(cx,cy,r,thickness=1,intensity)

def quantize(raster, palette, underlay=None) -> list[Line]
#   palette: tuple[(low, high, Style), ...]  按格内最亮强度选带
#   underlay: (Raster, Style) | None 静态垫底层

class PixelDemo:                 # 三模式 rings/bounce/spin
    MODES; mode; combo/score/hits/attempts/bounces/respawns
    set_mode(mode); tick(now: float); hit(); kick(cell_x, cell_y) -> bool
    render(c: Constraints) -> Surface
# 常量：FPS=60, _ON=128, _PALETTE 4 色带, _SLOT 4 槽位色
# 确定性：random.Random(20261028) + runtime.clock()，--headless --frames 可逐字重放
```

## App 接线（demo 壳使用）

```python
App(terminal=TerminalOptions(mouse=MouseMode.MOVE), throttle=1/60, title=...)
app.handlers = (custom, *DEFAULT_HANDLERS)   # 扩展不替换（替换砍断 bind）
app.bind(key, cb); app.every(period, fn); app.invalidate(); app.quit()
```

## golden 工具

```
uv run python tools/semantic.py --check | --update [--snapshot DIR]
```

## 不变公共 API（禁触）

`tools/api-2.0.txt` 钉住的 motui 顶层导出（kernel 值/App/widgets/…）。本操作对其只增不改；
W2-a/W3-a 往 `motui.kernel`/`motui` 导出面加名字时必须同步更新 `tools/api-2.0.txt` 所依据的
`tools/api.py` 生成逻辑（若该工具枚举导出面）——以 `tests/test_api.py` 全绿为准。
