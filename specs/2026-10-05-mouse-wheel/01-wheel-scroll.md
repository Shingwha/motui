# Spec 01 · 鼠标滚轮滚动（波次 W16）
> ✅ 2026-10-05 @ `wfs16-mouse-wheel`：T1 `d6394c2`（内核）· T2 `0ab8934`（驱动）· T3 `6c19487`（文档）。
> 分支 `wfs16-mouse-wheel`；前置：无（从含本 spec 的 main HEAD 切出）；深读：`specs/2026-10-05-mouse-wheel/00-overview.md`（决策 D1–D5、不变量 8–11、回归红线、风险出口）

## 目标

让整个 TUI 支持鼠标滚轮上下滚动：任何宿主（含 `examples/pi_demo.py`）**零改动**即获得该能力。
最高约束：`examples/pi_demo.py` 与其他一切非写入范围文件零 diff；既有两条反向断言保持有效；
公开导出面仅新增 `MouseEvent`。

## 工单（按序执行，每项一个 commit，每个 commit 独立 `uv run pytest` 全绿）

### T1 内核：追踪序列 + 屏幕配对 + SGR 解码 + 测试

**`src/mocode_tui/ansi.py`**（转义单源，docstring 风格照旧，函数加 `__all__`）：

```python
def enable_mouse_tracking() -> str:
    """Ask the terminal to report button presses and wheel motion (SGR 1006)."""
    return f"{ESC}[?1000h{ESC}[?1006h"


def disable_mouse_tracking() -> str:
    """Stop mouse reporting (reverse order of :func:`enable_mouse_tracking`)."""
    return f"{ESC}[?1006l{ESC}[?1000l"
```

**`src/mocode_tui/screen.py`**：

- `TerminalScreen(stream=None, *, mouse: bool = True)`：构造存 `self._mouse`；
  `enter()` = `enter_alt_screen() + hide_cursor() + (enable_mouse_tracking() if self._mouse else "")`（仅 live）；
  `leave()` = `(disable_mouse_tracking() if self._mouse else "") + show_cursor() + leave_alt_screen()`（仅 live）。
  非 live 行为逐字节不变。保持可读性优先于一行式（新增分支后一行式已难读，用 early return 或清晰括号均可）。
- `HeadlessScreen`：`enter()` = `enter_alt_screen() + hide_cursor() + enable_mouse_tracking()`；
  `leave()` = `disable_mouse_tracking() + show_cursor() + leave_alt_screen()`。
- 更新类 docstring（enter/leave 现含鼠标配对，一句即可）。

**`src/mocode_tui/keys.py`**：

- 模块 docstrings：事件模型段补一句 `MouseEvent`（`Key` 子类，携鼠标坐标）。
- 新增并导出 `MouseEvent`：

```python
@dataclass(frozen=True)
class MouseEvent(Key):
    """A mouse report: a routable :class:`Key` name plus the report's data.

    Today the decoder routes only the vertical wheel (``"wheel_up"`` /
    ``"wheel_down"``); every other report a terminal can send (button
    presses/releases, horizontal wheel, motion) is still dropped here --
    that branch is the seam future mouse kinds land in.  ``button`` is the
    report's low two bits (wheel: 0 = up, 1 = down); ``x``/``y`` are the
    1-based column/row from the report, kept for a future component hit
    test (subtract 1 to index ``Painter.rows()``) and ignored by scrolling.
    """

    button: int = 0
    x: int = 0
    y: int = 0
```

- `KeyDecoder._emit_csi` 开头（`~` 分支之前）加 `<` 私有参数分支，其余分发逻辑不动：

```python
if params.startswith("<"):
    self._emit_mouse_report(params, final, events)
    return
```

- 新增 `_emit_mouse_report(self, params: str, final: str, events) -> None`，按总纲 L3 草图：
  `final` 只认 `M`/`m`；`params[1:].split(";")` 取三段 `int`，畸形/缺段一律 `return`（丢弃，
  与既有「未知即丢弃」一致）；`b & 0x40` 且低 2 位 ∈ {0,1} → `wheel_up`/`wheel_down`
  的 `MouseEvent(name, button=low, x=x, y=y)`；横轮（低 2 位 2/3）与非滚轮（按键等）丢弃。
  修饰位（4/8/16）天然被低 2 位判定掩掉，无需显式处理。
- `KeySource` 协议、`ScriptedKeys`、`RawTerminalKeys`、Windows record 路径 **零改动**。

**测试**（`tests/test_keys.py`，结构化断言，风格照旧）：

```python
@pytest.mark.parametrize(
    ("report", "name"),
    [
        (b"\x1b[<64;10;5M", "wheel_up"),
        (b"\x1b[<65;10;5m", "wheel_down"),
        (b"\x1b[<68;3;9M", "wheel_up"),   # shift bit (4) masked
        (b"\x1b[<81;3;9m", "wheel_down"), # ctrl bit (16) masked
    ],
)
def test_sgr_wheel_reports_decode_to_wheel_keys(report, name):
    assert feed(report) == [MouseEvent(name, button=0 if name == "wheel_up" else 1, x=10, y=5)]
```

上例参数中 x/y 注意与 report 一致（`68`/`81` 用例是 3;9，按需构造或拆成两组，由你保证断言与序列对应）。
另加：`MouseEvent` 字段回填断言（x/y/button）1 例；跨 feed 拼接
（`feed(b"\x1b[<64;1")` → `[]`，再 `feed(b"0;5M")` → wheel_up）1 例；横轮
`b"\x1b[<66;1;1M"`、畸形 `b"\x1b[<64;10M"`、`b"\x1b[<M"` 均 `[]`（并入既有
`test_csi_with_private_markers_and_modifiers_is_dispatched_or_dropped` 同款风格一处即可）。
既有 `assert feed(b"\x1b[<0;5;5M") == []`（点击报告丢弃）**保持不动**。

### T2 驱动：scroll_keys 表 + mouse 开关 + 测试

**`src/mocode_tui/app.py`**：

- 类级默认表 `_DEFAULT_SCROLL_KEYS = {"page_up": -1, "page_down": 1, "wheel_up": -3, "wheel_down": 3}`
  （带符号行数，负 = 向上；page 键保持逐行语义，滚轮每格 3 行）。
- `TUI.__init__` 增 `mouse: bool = True`：`self.screen = screen if screen is not None else TerminalScreen(mouse=mouse)`；
  `self.scroll_keys = dict(_DEFAULT_SCROLL_KEYS)`（实例级公开字典，docstring 注明：
  宿主可改行数或删绑定收回事件，例如 `del tui.scroll_keys["wheel_up"]`）。
  类 docstring 参数说明同步补 `mouse` 与 `scroll_keys`。
- `read_key()` 用表驱动替换现有两个 if（语义等价且更简）：

```python
while True:
    event = await source.read()
    if event is None:
        return None
    if isinstance(event, Key):
        rows = self.scroll_keys.get(event.name)
        if rows is not None:
            if rows < 0:
                self.scroll_up(-rows)
            else:
                self.scroll_down(rows)
            continue
    return event
```

  docstring 改为：「scroll_keys 命中的键（默认 page_up/page_down/wheel_up/wheel_down）被拦截并滚动视口，读继续」，
  逃生口 `tui.keys.read()` 语义不变。
- `TUI(mouse=…)` 只影响默认 `TerminalScreen`；自定义 `screen` 自带 mouse 设置（docstring 写明）。

**测试**（`tests/test_app.py`，既有 `test_read_key_intercepts_page_keys_and_returns_the_rest` 必须继续绿）：

- `read_key` 拦截滚轮：script `[MouseEvent("wheel_up", button=0, x=1, y=1), Key("a", "a"), None]`，
  加 30 行文档后 `read_key()` 返回 `Key("a","a")` 且视口已上移 3 行（rows 对比）。
- `scroll_keys` 定制：其一改 `tui.scroll_keys["wheel_down"] = 1` 验证只滚 1 行；
  其二 `del tui.scroll_keys["wheel_up"]` 验证 `MouseEvent` 原样返回且 x/y/button 完好。
- 导入 `MouseEvent`（从 `mocode_tui.keys`）。

**`src/mocode_tui/__init__.py`**：`from .keys import ... MouseEvent ...`，`__all__` 追加一项（其余不动）。

### T3 文档（英文）

- `README.md`：特性清单加一条「**mouse wheel** — PageUp/PageDown scroll back, and so does the
  wheel (SGR 1006); `tui.scroll_keys` rebinds what scrolls and by how many rows」；driver 小节
  `read_key` 行补「page keys and the wheel scroll and are absorbed」；「Not on purpose」段删掉
  mouse-wheel 一条（保留其余）。
- `docs/DESIGN.md`：screen model 段 enter/leave 描述补鼠标配对（一句）；Keys 段补
  `MouseEvent` 与 SGR 解码（含「仅路由竖向滚轮，其余报告仍丢弃——未来点击事件的缝」）；
  driver 段补 `scroll_keys` 与 `TUI(mouse=…)`；「Deliberately out of scope」删 mouse-wheel 条，
  并按 W11 先例加一句修订说明（2026-10-05 W16 落地）。

## 验收（完成前自测，报告给真实结论）

1. `uv run pytest -q` 全绿（贴真实输出末行：passed/skipped 计数；基线 707 passed / 2 skipped，本波应 ≥ 714 passed）
2. `python examples/pi_demo.py < /dev/null; echo exit=$?` → exit=0（贴末几行）
3. `uv run python -c "import mocode_tui; print(mocode_tui.MouseEvent("wheel_up", button=0, x=1, y=1))"` 通过
4. `git diff --stat main...HEAD` 确认写入范围外零 diff（贴输出）
5. 既有两条反向断言仍在：`grep -n "ENABLE_MOUSE_INPUT untouched" tests/test_keys_windows.py`、
   `grep -n "SGR mouse report: dropped" tests/test_keys.py`（贴命中行）

## 禁触清单

- `examples/pi_demo.py`（零改动即生效是本波的证明）、`probe_keys.py`
- `specs/`（归 lead；worker 不改任何 spec 状态）
- `src/mocode_tui/viewport.py`、`painter.py`、`lines.py`、`block.py`、`style.py`、`layout.py`、`components/**`
- `tests/` 除 `test_keys.py`、`test_ansi.py`、`test_screen.py`、`test_app.py` 外的文件
- 不 merge、不 push、不碰主检出与其他 worktree；阻塞即停，不越界自救

## 最终报告格式

工单状态表（T1/T2/T3 各 commit hash + message）/ 自测真实结论（逐条贴输出）/ 偏差与取舍 /
未决问题。禁止「应该没问题」。
