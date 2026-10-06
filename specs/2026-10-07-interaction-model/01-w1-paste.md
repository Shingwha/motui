# Spec interaction-model · 粘贴即一个事件（波次 W1）
> 分支 `im1-paste`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`（宪法第 5 条、
> 决策 D9）、`ref/audit-paste.md`（本波全部证据与锚点）。
> **最高约束：不猜测、不启发式。** 能修的只有"让终端 bracket 粘贴"这一条路，
> 拿不到 bracketed paste 的输入路径写进文档，不假装能修。

## 目标

**一次多行粘贴必须是一个 `Paste` 事件，永远不等于一串 `enter`；`Paste` 永不触发提交。**

今天不是这样。全仓**没有任何一处**开启 bracketed paste（`grep 2004` 零命中），
终端因此把粘贴原文连 `\r\n` 一起送进来，`_char_key` 把 `\r` 与 `\n` **各**解成一个
`Key("enter")`，宿主的提交手势每见一个 `enter` 就提交一次——粘 3 行 = 4 次提交。
decoder 侧其实**已经支持** `\x1b[200~`/`\x1b[201~`（有单测），差的是让终端发它。

## 背景（锚点，不必再找）

| 事实 | 位置 |
|---|---|
| decoder 支持粘贴标记且有单测 | `src/mocode_tui/keys/decoder.py`（`_PASTE_START`/`_PASTE_END`、`_emit` 的粘贴分支）；`tests/test_keys.py:156-170` |
| 屏幕进入/离开当前只写三件事 | `src/mocode_tui/core/screen.py` 的 `TerminalScreen.enter/leave` 与 `HeadlessScreen.enter/leave`（两份实现） |
| 鼠标那对字节 | `src/mocode_tui/core/ansi.py` 的 `enable_mouse_tracking()` = `ESC[?1000h ESC[?1002h ESC[?1006h` |
| 测试把 enter/leave 字节钉死了 | `tests/test_screen.py:56-72`、`tests/test_ansi.py:50` |
| 已有同形状开关 `mouse: bool = True` | `core/screen.py` 构造签名与 `enter()` 分支 |
| `Paste` 在字段里被 verbatim 插入 | `widgets/textbuf.py` 的 `handle()`（对 `Paste` 返回 True），`Input.cursor` 的 docstring 自认"粘进来的换行留在文本里、不占新行" |
| 宿主侧其实是对的 | `examples/showcase/session.py` 的 `run()`：`editor.handle(event)` 对 `Paste` 返回 True，因此粘贴本身不会提交——**问题只在"终端没被要求 bracket"** |
| Windows 输入路径 | `keys/console.py` 打开了 `ENABLE_VIRTUAL_TERMINAL_INPUT`（0x0200）：现代终端走 VT 字节 → 2004 有效；只有拿不到 VT 输入的旧控制台走 console 记录路径（`keys_from_console_events`，VK_RETURN→`enter`），**无 bracketed paste 可依** |

## 工单（按序执行，每项一个 commit）

### T1 `ansi` + `screen`：开启 / 关闭 bracketed paste

- `core/ansi.py`：新增 `enable_bracketed_paste()` → `"\x1b[?2004h"`、
  `disable_bracketed_paste()` → `"\x1b[?2004l"`，加入 `__all__`；
  docstring 写明语义（让终端把粘贴内容包进 `CSI 200~` / `CSI 201~`，使一次粘贴成为一个事件）。
- `core/screen.py`：`TerminalScreen` 与 `HeadlessScreen` 的 `enter()`/`leave()` 都带上这一对；
  构造参数扩成 `mouse: bool = True, paste: bool = True`（同形状开关，文档写明"不需要时关掉"）。
  字节顺序：`enter = alt + hide_cursor + enable_mouse_tracking + enable_bracketed_paste`；
  `leave` 取严格逆序。
- **全仓 grep `enable_mouse_tracking()` / `hide_cursor()` 的全部断言点**（`tests/test_screen.py`、
  `tests/test_ansi.py`、`src/mocode_tui/testing.py` 与 README 的任何字节示例），一并更新。
- 验证：`tests/test_ansi.py` 加字节级用例；`tests/test_screen.py` 更新两枚钉子，
  并加 `mouse=False` / `paste=False` 的组合用例（关掉时那对字节消失）。

### T2 单行字段：粘贴里的换行折叠成空格

- 位置在 **`Input.handle(Paste)` 边界**：`Input` 覆写 `handle()`，遇到 `Paste` 先折叠文本
  （`\r\n` / `\r` / `\n` → 单个空格；连续空行也折叠成一个空格）再交给 `super().handle()`。
  `Editor` 不覆写（多行是它的能力）；`TextBuffer` 零改动。
- 为什么不做成 buffer 级不变量（备选方案，记录在案）：把"单行"变成 `TextBuffer.single_line` 会
  同时改掉 `insert()` 的语义与既有测试用例（`tests/test_widgets_editing.py` 里
  `Input` 渲染 `"a\nbb\nccc"` 为三行是一条现行行为），影响面大于本 bug；
  `insert()` 是共享引擎 API，机制层不该知道谁在用它。若 lead 要更严的不变量，
  这是一次一行代码的搬家（在 `TextBuffer.insert` 里按 flag 折叠），但必须同波改那三条测试并登记行为变化。
- 验证：`tests/test_widgets_editing.py` 新增——`Input` 粘 `"a\r\nb\nc"` → `text == "a b c"`、
  光标在末尾、渲染**一行**；`Editor` 同样输入 → 三行不变；`Input.insert("\n")` 行为不变（宿主显式插入仍是旧语义）。
- **行为变化登记**：`Input` 的粘贴路径从"换行留在文本里"变成"换行变空格"——写进最终报告的 A/B 段。
- 文档：`Input` / `Editor` 的 docstring、`docs/COMPONENTS.md` 两行、README 组件表两行同步。

### T3 示例与文档：粘贴语义落地

- `examples/showcase/script.py`：在提问之前加一段 headless 粘贴回放
  （`Paste("pasted first\npasted second\npasted third")` 后**不**回车，再单独 `Key("enter")`），
  使 piped 回放覆盖"粘贴不提交、回车才提交一次"。
- `examples/showcase/session.py` 的主循环**不需要改**（若你认为要改，停下上报）。
- `docs/DESIGN.md`：在键盘 / 非 TTY 章补"粘贴语义"一段——2004 开了什么、`Paste` 与 `enter` 的分工、
  **两条降级路径**（旧 console 记录路径、cooked 管道 / 重定向：拿不到 bracketed paste，
  逐行到达 = 逐行提交；库不猜测）。
- `README.md`：若"键位/交互"段提到粘贴，补一句"多行粘贴是一个事件，不会逐行提交"。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 全绿；总数 = 基线 846 passed + 1 skipped + 本波新增（只增）。
2. **探针 A（回归，证明 decoder 侧就绪）**：
   `KeyDecoder().feed(b"\x1b[200~a\r\nb\x1b[201~")` → `[Paste("a\r\nb")]`。
3. **探针 B（降级证据，写进文档）**：同一 decoder 喂**裸** `b"a\r\nb"` → 2 个 `Key("enter")`
   ——这就是旧路径的现状，也是"必须开 2004"的理由。
4. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；
   `grep -c 'pasted first' <dump>` 证明粘贴文本整段进了同一条消息。
5. `uv run python tools/framebench.py` → render-hash 与基线一致（贴值）；
   `uv run python examples/demo.py --pages | head -20` 正常。
6. 真机（Windows Terminal）：粘 3 行 → 一个用户消息、一次回车一次提交。

## 禁触清单

- `src/mocode_tui/keys/decoder.py`（粘贴状态机已正确；要改先上报）。
- `src/mocode_tui/widgets/` 除 `input.py` 的 `handle` 覆写与 docstring 外的一切
  （`choice/tabs/tree/table/textbuf` 属 W2+）。
- `examples/showcase/session.py`、`examples/showcase/components.py`（本波不改主循环与页面）。
- `specs/`（spec 归 lead，worker 不写状态）。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令 + 输出）/
行为变化 A/B（Input 粘贴）/ 偏差与取舍（尤其降级措辞）/ 未决问题 / 真机手测结果。
