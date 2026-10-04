# Spec W4 · 驱动与键盘（波次 W4）
> ✅ 2026-10-04 已交付合并；终验 585 passed（main）。分支见 git log --merges。
> 分支 `wfs4-driver`；前置：**W3 已合并**（从合并时刻最新 main 切出）；深读：`00-overview.md` + `01`~`03`

## 目标

打通最后两层：`keys.py`（事件模型 + 字节解码 + 键源）与 `app.py`（TUI 驱动：全屏进出、
pinned/滚动门面、page 键拦截、pump、管道 dump 契约），`testing.py` 测试助手，
并**定型**根 `__init__.py` 最终导出面。最高约束：库不建事件循环（协程纪律）；
pump/throttle/时钟 seam 语义按本单定格；非 live = 运行期静默 + 退出 dump。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `keys.py` — 事件模型与解码器
- `Key(name, char="")` frozen dataclass（name 路由身份：`"a"`/`"enter"`/`"c-c"`/`"escape"`/`"up"`/…；char 可打印字符）。
- `Paste(text)` frozen dataclass。
- `KeySource` runtime_checkable 协议：`async read() -> Key | Paste | None`（None = EOF）。
- `KeyDecoder()`：
  - `feed(data: bytes) -> list[Key|Paste]`；`flush() -> list[Key|Paste]`（EOF 收尾）；
  - 增量 UTF-8（`errors="replace"`）；`\r`/`\n`→enter；`\t`→tab；0x7F→backspace；0x01-0x1A→c-a..c-z；
    0x20→space；其余可打印→该字符自身为 name；
  - CSI：`A/B/C/D/H/F`→up/down/right/left/home/end（无参数）；`~` 族按第一参数：
    1/7→home、3→delete、4/8→end、**5→page_up、6→page_down**；200/201 → bracketed paste 始末；
  - escape 处理策略（**定格**）：完整序列一 feed 到达则解析；feed 末尾遗留的裸 escape 判为孤立 escape 键；
    遗留的不完整 CSI 退化为 escape + 参数字面字符重读；未知序列丢弃（不许抛）。
  - 覆盖之外一律不抛：丢键优于崩。
- 测试 `tests/test_keys.py`：可打印/修饰键/CSI 各路线；paste 跨 feed 聚合与 stray end marker；
  孤立 escape 策略；残缺 CSI 退化；未知序列丢弃；flush 收尾（未闭合 paste 交付原文）。

### T2 `keys.py` — 键源
- `ScriptedKeys(events)`：iterable 事件序列，耗尽返 None。`async read()`。
- `RawTerminalKeys(fd=None)`：
  - `start()`：POSIX `termios`/`tty.setraw` 或 Windows `SetConsoleMode`（清 LINE/ECHO 位、置
    `ENABLE_VIRTUAL_TERMINAL_INPUT`，保留 PROCESSED 让 Ctrl-C 走 KeyboardInterrupt 双保险）；
    失败 → cooked 行回退；起 daemon 读线程。
  - Windows **console-record 路径**：`msvcrt.get_osfhandle(fd)` 后 `ReadConsoleInputW` 逐 record；
    只处理 `EventType==1`（KEY_EVENT）且 `bKeyDown`；Unicode 字符直出（绕开代码页，宽字符原样）；
    Ctrl+字母 → c-a..c-z；VK 表：ENTER/BACK/TAB/ESCAPE/HOME/END/DELETE/LEFT/UP/RIGHT/DOWN +
    **PRIOR(0x21)→page_up、NEXT(0x22)→page_down**；非键 record 跳过；repeat count 忽略。
  - POSIX 路径：`os.read` → `KeyDecoder.feed`。
  - `async read()`：线程 queue 取事件（executor 桥接，禁跨线程摸 asyncio.Queue）；None sentinel 唤醒。
  - `close()`：停线程、恢复终端模式。
  - `windows_input_mode(old) -> int` 纯函数（可单测）；cooked 回退：整行按字符 + enter 交付。
- 测试 `tests/test_keys_windows.py`：`windows_input_mode` 纯函数（LINE/ECHO 清除、其余位透传）；
  `_key_from_console_event` 映射（Unicode 宽字符、Ctrl 组合、VK 表含 page 键、key-up 返 None）；
  ctypes 结构体尺寸 sanity（只在 os.name=="nt" 下跑，POSIX 环境 skipif 并如实标注）。

### T3 `app.py` — TUI 驱动
- `TUI(*, screen=None, keys=None, throttle=0.030, interactive=None)`：默认 TerminalScreen；
  持 Document + Painter；`interactive` override 优先，否则 `screen.live and sys.stdin.isatty()`。
- 文档门面：`add(component, *, id=None, pinned=False)`（+invalidate）；`get/remove`；
  `print(text)` = 追加 `Text(text, style=MUTED)` 系统块（+invalidate）——外部输出即系统块，不再裸 stdout。
- 滚动门面：`scroll_up(n=1)/scroll_down(n=1)/scroll_to_bottom()` → painter 转发 + invalidate。
- `invalidate()/flush()`（flush 直灌 force）/`every(seconds, fn)`（可取消句柄；fn 自决是否 invalidate）/
  `read_key()`（**拦截 page_up/page_down**：执行滚动+invalidate 后继续读；其余键/Paste 原样返；
  无源/EOF → None。docstring 写明裸键逃生口 `tui.keys`）/`stop()`。
- pump：`_tick(now)`（跑到期 every；dirty 且过 throttle 则 flush；返回下次唤醒秒数或 None）+
  `_clock()`（monotonic；测试 monkeypatch 注入）+ `_wake_up`（asyncio.Event，惰性建、按 loop 绑定）。
- `run(body)`：
  1. interactive 且 live → RawTerminalKeys().start() 挂上；
  2. live → `screen.enter()`；非 live 不调 enter/leave（全静默）；
  3. pump 启动 → `await body(self)`；KeyboardInterrupt=stop；其他异常 finally 后重抛；
  4. finally：停 pump/停键盘；live → `screen.leave()`；flush 一次；
  5. **非 live dump**（body 正常结束或异常都执行；异常路径 dump 完再抛）：`painter.rows()` 逐行 `.text`，
     去掉尾部全空行，`"\n"` 连接 + 末尾 `"\n"`，经 `screen.write`+`flush` 输出。
- `rows()` 门面（调试/测试）。
- `testing.py`：`headless_tui(width=80, height=24, *, script=None, keys=None)`（HeadlessScreen live=True
  + ScriptedKeys + interactive=False）；`snapshot(tui)`（每块 `[id | state(,pinned)]` 头 + `  |行文本`）。
- 根 `__init__.py` **定型**总纲「模块契约」表的最终导出面（`__all__` 与之逐一对齐）。
- 测试 `tests/test_app.py`：add/get/remove/pinned 门面；print 系统块；滚动门面改 `rows()` 窗口；
  read_key 拦截（返回值 + 副作用）与 `tui.keys` 逃生口；run 生命周期：enter/leave 成对
  （正常/异常/stop 三路径都断言 leave 字节出现在 output）；非 live：运行期 output 空 + dump 内容
  （含尾空行修剪）；pump throttle 与 every（注入时钟推进 `_tick`，无 sleep）。

### T4 自测与证据
- `uv run pytest` 全绿（贴尾部输出；总数 ≥ W3 的数）。
- 冒烟脚本：headless TUI + 12 个短块 + pinned 输入块；写内容、scroll_up(3)、`print("hi")` 系统块、
  断言 `len(rows())==24`、dump 形状（经 run 或手动调用等价路径）。贴输出。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest`：`N passed`，0 失败（贴尾部原文）。
2. T4 冒烟输出。
3. `git diff --stat main..HEAD` 证明写入范围仅
   `src/mocode_tui/{keys,app,testing,__init__}.py` + `tests/test_{keys,keys_windows,app}.py`。
4. `uv run python -c "import mocode_tui as m; assert set(m.__all__) == {...总纲表最终面...}"` 贴输出
   （把总纲表逐符号列全再跑；不一致即失败）。

## 禁触清单

- `block.py style.py text.py lines.py ansi.py screen.py viewport.py painter.py components/** layout.py`、
  `examples/**`、`docs/**`、`README.md`、`pyproject.toml`、`specs/**`。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- `test_keys_windows.py` 若本机探测规则无法单测 ctypes 交互：以纯函数 + 结构体尺寸静态断言覆盖，
  真实 record 读取留待 lead 真机验收，报告如实登记。
- `run()` 非 live dump 若与异常路径互斥：异常路径 dump 完再抛必须成立；实现冲突时
  在报告未决问题显式登记，不许静默省略。

## 最终报告格式

同前波：工单状态表（commit hash+message）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
