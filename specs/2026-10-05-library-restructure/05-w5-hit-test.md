> ✅ 2026-10-05 @ 分支 lib-w5 — 已合并 main

# Spec W5 · hit_test 鼠标点击(波次 W5)

> 分支 `lib-w5-hit-test`;前置:W1 已合并;深读:总纲、`specs/2026-10-05-mouse-wheel/00-overview.md` 与 `01-wheel-scroll.md`(MouseEvent 坐标预留的扩展缝)、`src/mocode_tui/keys/decoder.py`(SGR 1006 解析,按键当前被丢弃)、`src/mocode_tui/core/viewport.py`(layout 行归属)、`src/mocode_tui/core/app.py`(read_key 的 scroll_keys 拦截)。

## 目标

让组件可被鼠标点击:decoder 放开按键按下事件,Viewport 记录行→block 归属,TUI 暴露 `hit_test(x, y)`,Select 支持点击定位。**滚轮行为与现有键盘路径零变化。**

## 工单(按序执行,每项一个 commit)

### T1 decoder 放开鼠标按键

- `keys/events.py`:`MouseEvent` 语义扩展——`button` 取值 `wheel_up/wheel_down`(现状)+ `left/middle/right`(按下);新增字段如需(如 `kind: "press"`)谨慎最小化,优先复用现有字段。坐标 x/y 为 SGR 报告的 1-based 终端行列(现状已是)。
- `keys/decoder.py`:SGR 1006 解析中,当前「垂直滚轮路由、按键/横向滚轮丢弃」处,改为按键**按下**(`M` 结尾)生成对应 button 的 MouseEvent;**释放**(`m` 结尾)与横向滚轮、拖拽移动仍丢弃(注释写明为预留缝)。
- `core/app.py`:`TUI.read_key()` 的 scroll_keys 拦截逻辑不变;`left/middle/right` 按键 MouseEvent **不被拦截**,原样返回给宿主。
- `tests/test_keys.py`/`tests/test_keys_sources.py` 追加:按键按下解码、释放丢弃、滚轮回归不变。

### T2 Viewport 行归属记录

- `core/viewport.py`:`layout()` 内部已知每行来自哪个 block;将归属表存到实例(`self._row_blocks: list[tuple[str, int]]` 或并入 ScreenLayout——裁决:挂 Viewport 实例,不改 ScreenLayout 公共 dataclass 形状),每帧 layout 重建。full repaint 与 diff 路径共用同一 layout 结果,无额外渲染成本。
- 归属记录覆盖 top/body/bottom 三个区域,行号为屏幕 0-based 行。
- `tests/test_viewport.py` 追加:pinned/unpinned 混合布局的行归属断言、滚动后归属跟随、空文档。

### T3 TUI.hit_test + Select.click

- `core/app.py`:
  ```python
  @dataclass(frozen=True)
  class Hit: block: Block; row: int; col: int   # row/col 为块内 0-based
  def TUI.hit_test(self, x: int, y: int) -> Hit | None  # 入参为 MouseEvent 的 1-based 终端坐标
  ```
  未命中任何块(空白填充行)→ None。
- `widgets/choice.py`:`Select.click(row: int) -> bool`(row 为块内行,title 行要偏移换算;命中选项行则移动游标返回 True)。Confirm 继承生效。
- 便捷接线(可选,若做则写清楚):`TUI` 不自动分发点击——宿主拿到 MouseEvent 后自行 `hit_test` + 调用组件方法。示例写进 app.py 的 hit_test docstring。
- `tests/test_app.py` 追加:HeadlessScreen 下构造布局,hit_test 命中/未命中/边界;`tests/test_widgets_choice.py` 追加 click 行为。

## 验收

1. `uv run pytest -q` 全绿(贴真实输出)。
2. `uv run python examples/pi_demo.py < /dev/null | diff - specs/2026-10-05-library-restructure/ref/w1-demo-dump.txt` 为空。
3. 滚轮相关既有测试原样通过(在报告中点名列出)。

## 禁触清单

`src/mocode_tui/__init__.py`、`core/` 其他文件(style/text/lines/ansi/block/screen/painter/testing)、`keys/` 其他文件、`widgets/` 其他文件、`tests/test_api_root.py`、`examples/`、`docs/`、`README.md`、`pyproject.toml`。不改 `enable_mouse_tracking` 的字节序列(?1000h 已含按键上报)。

## 最终报告格式

工单状态表 / commit 清单 / 门禁真实输出 / MouseEvent.button 取值表 / hit_test 坐标换算说明 / 偏差与取舍 / 未决问题。
