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

## examples/pixel.py —— 仅参考实现（W1-b 物理删除，非契约）

已在本仓库对话中验证的算法语义（W1-a 交付 kernel 版时的行为基准）：色索引+热度双网格、
逐格多数槽位选 fg、冷却穿色、half 实心填充 / braille 曲线、run 融合直接构 Line
（绕开 Canvas 逐格簿记，2.0–4.2ms/76×24 帧）、`bytes.translate` 表驱动衰减、
盲文位序 `((0x01,0x02,0x04,0x40),(0x08,0x10,0x20,0x80))`、确定性重放
（`random.Random(20261028)` + `runtime.clock()`）。目标 API 契约见 `01-W1-a-kernel-pixel-core.md` 工单；
合并后由 lead 把 kernel 现实签名回写到这里。

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
