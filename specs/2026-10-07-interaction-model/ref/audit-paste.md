# ref · 粘贴审计（W1 的证据底稿）

> 采集日 2026-10-07，仓库 `mocode-tui` @ `59dee9d`（工作区另有未提交改动时以实跑为准）。
> 本文件是 W1 的唯一权威证据：所有命令都可原样重跑，输出即贴。

## 1. 结论

**decoder 与文档早已支持 bracketed paste，但终端从未被要求发它**：全仓没有任何一处
`DECSET 2004`（`grep -rn "2004" src/ tests/ docs/ README.md` 只命中 decoder 的字节常量、
文档叙述与 `events.Paste` 的 docstring，没有任何 `\x1b[?2004h`）。后果：一次多行粘贴
按原文字节到达，`\r` 与 `\n` **各**解成一个 `Key("enter")`，宿主的提交手势逐行提交。

## 2. 证据

### 2.1 裸多行粘贴 = 一串 enter（今天的真实行为）

```console
$ uv run python -c "
from mocode_tui.keys.decoder import KeyDecoder
d = KeyDecoder()
ev = d.feed(b'one\r\ntwo') + d.finish()
print([(type(e).__name__, getattr(e, 'name', '')) for e in ev])
"
[('Key', 'o'), ('Key', 'n'), ('Key', 'e'), ('Key', 'enter'), ('Key', 'enter'), ('Key', 't'), ('Key', 'w'), ('Key', 'o')]
```

两行文本 → **两个** `enter`（`\r` 一个、`\n` 一个）。粘 N 行 → 约 2N 个 enter。

### 2.2 decoder 侧就绪：bracketed paste 已被正确解析

```console
$ uv run python -c "
from mocode_tui.keys.decoder import KeyDecoder
d = KeyDecoder()
print(d.feed(b'\x1b[200~one\r\ntwo\x1b[201~'))
"
[Paste(text='one\r\ntwo')]
```

单测早已钉住这条路径：`tests/test_keys.py:156`（`feed(b"\x1b[200~hello\r\nworld\x1b[201~") == [Paste("hello\r\nworld")]`）、
`:158`（marker 出现在内容里也不误判）、`:159`（空粘贴是粘贴）、`:167`（跨 feed 的粘贴）、
`:170`（未闭合的粘贴在 `finish()` 时整段交付）。

### 2.3 屏幕进入/离开的字节（缺的就是最后一段）

```console
$ uv run python -c "
from mocode_tui.core import ansi
print('enter:', repr(ansi.enter_alt_screen() + ansi.hide_cursor() + ansi.enable_mouse_tracking()))
print('leave:', repr(ansi.disable_mouse_tracking() + ansi.show_cursor() + ansi.leave_alt_screen()))
print('has 2004 helper:', hasattr(ansi, 'enable_bracketed_paste'))
"
enter: '\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h'
leave: '\x1b[?1006l\x1b[?1002l\x1b[?1000l\x1b[?25h\x1b[?1049l'
has 2004 helper: False
```

写这两串字节的地方：`src/mocode_tui/core/screen.py` 的 `TerminalScreen.enter/leave`（live 路径）
与 `HeadlessScreen.enter/leave`（headless 路径）；`mouse: bool = True` 开关已存在（`mouse=False`
去掉 `1000/1002/1006` 三段）。

钉住它们的测试（W1 必须同步更新）：

- `tests/test_screen.py:56-72`：`screen.output` 与上面两串**逐字节**相等；
- `tests/test_ansi.py:50`：`enable_mouse_tracking() == "\x1b[?1000h\x1b[?1002h\x1b[?1006h"`。

### 2.4 Windows 的两条输入路径

| 路径 | 机制 | bracketed paste 可用性 |
|---|---|---|
| 现代终端（Windows Terminal / conpty） | `keys/console.py` 打开 `ENABLE_VIRTUAL_TERMINAL_INPUT`（0x0200），字节走 `KeyDecoder` | **可用**——开了 2004 即生效 |
| 旧控制台（拿不到 VT 输入） | `keys_from_console_events()`：VK_RETURN（0x0D）→ `Key("enter")` | **不可用**——一次粘贴是一串按键记录，逐行 `enter`；文档写明降级，不做猜测 |
| POSIX cooked / 管道 / 重定向 | `RawTerminalKeys` 的 cooked-line 回退（逐行读） | **不可用**——每行到达即一行 + 回车语义 |

### 2.5 字段侧今天怎么处理粘贴

`widgets/textbuf.py` 的 `handle()`：`Paste` 直接 `insert(event.text)`（verbatim，含换行）。
`Input.cursor` 的 docstring 自认这个形状："a pasted newline stays in the text but adds no row
to the field's line"。现行行为被测试钉住：`tests/test_widgets_editing.py:277`
（`(Input, 6, "a\nbb\nccc", ["❮ a", "  bb", "  ccc "])` —— Input 渲染成三行）。

宿主侧（示例）的提交路径**是对的**：`examples/showcase/session.py` 的 `run()` 先
`editor.handle(event)`，`Paste` 被字段消费 → 不提交。问题只在"终端没被要求 bracket"这一步。

### 2.6 文档已经写着它有（但没开）

- `docs/DESIGN.md:661-664`：描述 decoder 支持 `\x1b[200~ … \x1b[201~` 与未闭合粘贴的交付；
- `README.md:36`：拿 bracketed paste 与鼠标选择类比（"the same bargain bracketed paste made"）；
- `core/events.py:81`：`Paste` 的 docstring 是"a bracketed-paste payload"。

→ W1 的文档工作不是"新增说明"，而是**让文档描述的机制真正被开启**，并把两条降级路径补进去。

## 3. 复现命令汇总

```bash
uv run python -c "from mocode_tui.keys.decoder import KeyDecoder; d=KeyDecoder(); print(d.feed(b'\x1b[200~a\r\nb\x1b[201~'))"
uv run python -c "from mocode_tui.keys.decoder import KeyDecoder; d=KeyDecoder(); print([(type(e).__name__, getattr(e,'name','')) for e in d.feed(b'a\r\nb')+d.finish()])"
uv run python -c "from mocode_tui.core import ansi; print(repr(ansi.enable_mouse_tracking()), hasattr(ansi,'enable_bracketed_paste'))"
grep -rn "2004" src/ tests/ docs/ README.md
grep -rn "enable_mouse_tracking()\|hide_cursor()" tests/ src/mocode_tui/testing.py
```

## 4. W1 的行为变化基线（A/B 用）

| 场景 | 改前 | 改后（W1 目标） |
|---|---|---|
| 多行粘贴（支持 2004 的终端） | 每行一个 `enter` → 逐行提交 | 一个 `Paste` → 不提交，文本整段进字段 |
| `Input` 粘贴 `"a\r\nb"` | `text == "a\r\nb"`（渲染三行） | `text == "a b"`（渲染一行） |
| `Editor`/composer 粘贴多行 | 多行（正确） | 不变 |
| 旧控制台 / cooked 管道 | 逐行提交 | 不变（**已知降级**，文档写明） |
| headless 回放的屏幕字节 | 无 2004 | 多一对 `\x1b[?2004h` / `\x1b[?2004l`（`HeadlessScreen.output`，piped dump 的 rows 不受影响） |
