# 审计报告 C：keys + 顶层装配件 + API 面 + example + 测试（权威参考）

> 2026-10-06 全文审计取证。行号对应审计时刻的 main（c153d04），以符号名定位为准。

## 1. 顶层三件套（selection.py / chrome.py / testing.py 置于包根）

- 三者一致自称 assembly tier，仅被根 facade 导入（src/mocode_tui/__init__.py:30,59,60），
  无任何下层反向导入。与 app.py 并列构成根级装配件，放包根与分层自洽。
- **命名冲突风险**：根级 chrome.py（Scrollbar/Toasts）vs widgets/chrome.py（Divider/Notice/Panel，
  widgets/__init__.py:23）；根级 selection.py（手势策略）vs core/selection.py（Selection 模型）。
- chrome.py 的 Scrollbar（157-545）结构：模块级纯几何 TRACK/THUMB/_thumb_of（98-154）；
  类内 handle（267）、detach（306）、_paint（322）、几何 _strip/_covers/_geometry（363-387）、
  手势 _press/_motion/_drag/_release/_page/_tick（402-520）。与 kernel 边界干净
  （Chrome 协议 + pane.add_chrome/remove_chrome + frame.pane_layout；几何读 pane.band；
  分页操作 pane.viewport.scroll_down/up；时间走 tui._clock()）。
- 防御式痕迹：Scrollbar.__init__ 无 pane 时伪造 id "primary" 再必然抛 ValueError（243-253）；
  detach 双重守卫（317）；Toasts.detach 身份扫描避免二次 detach（776-777）、paint 里再查
  self._detached（859，docstring 自认 belt-and-braces）。
- Toasts（644-884）：纯函数 _stack（576-627）/ _band_row（630-641）；_Toast frozen dataclass
  （560-573）；show 用 tui._clock() 打时间戳 + tui.every(EXPIRY_TICK, ...)（751-758）；
  handle 按压命中即 dismiss（781-807）；paint 为 overlay 协议（847-875）。
- selection.py：copy_on_select（87-108）；SelectionGesture（111-553）handle（184-217）、
  双击/锚定（238-357）、拖动扩展（359-395）、release（397-411）、edge auto-scroll ticker
  （434-511）、document-walk（513-553）。时间戳存控制器（_press 里 tui._clock()，248）。
- testing.py（61 行）：headless_tui（25-41）、snapshot（44-61）。

## 2. keys 层

- 职责清晰：decoder.py 纯 bytes->events 状态机（无平台/无 IO）；keymap.py 纯数据表 58 行；
  sources.py 平台/线程/异步生命周期（RawTerminalKeys、_SETTLE_SECONDS=0.050）；
  console.py Windows-only ctypes 结构 + 纯映射/回放缝（keys_from_console_events 400-421）；
  keys/__init__.py facade 5 名。
- 三张 keymap 表派生链分居两包：DEFAULT_INPUT_KEYMAP（keymap.py:40-52，无 enter）→
  DEFAULT_EDITOR_KEYMAP = {**INPUT, "enter": "newline"}（keymap.py:58）→ COMPOSER_KEYMAP =
  EDITOR 去 enter + "c-j": "newline"（chat/composer.py:79-82）。重构需三处同步。
- console.py（421 行）死代码（实证）：
  - 死函数 _key_from_console_event（228-246）：src/tests 零调用；活路径是 _console_record_events。
  - 死常量 _MOUSE_HWHEELED（:85）零引用；_DOUBLE_CLICK（:83）src 零引用（测试自建同名常量）。
  - AsciiChar union 成员（:152）仅定义；无测试断言结构体尺寸。
  - 模块 docstring 19-25 与结构体区注释 143-148 近乎逐字重复。
  - 可疑非死：_key_from_values 的 ctrl+字母分支（261-262）与 VK_A..VK_Z 兜底（328-329）
    只在 char == "\x00" 时可达（非 VT 语义），有测试覆盖（test_keys_sources.py:136-137）。**保留**。

## 3. 公开 API 盘点

- 根 __init__.py:86-155 共 68 名（test_api_root.py:94-97 逐字锁定）：
  ACCENT, DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, DEFAULT_THEME, DIM, ERROR, MUTED,
  SUCCESS, WARNING, Autocomplete, Block, Column, Component, Composer, Confirm, Divider,
  EditBlock, Editor, EveryHandle, HeadlessScreen, Hit, Input, Key, KeySource, Keymap, Line,
  Markdown, Message, MouseEvent, Notice, Option, Padding, Pane, Panel, Paste, ProgressBar,
  RawTerminalKeys, Row, Screen, ScriptedKeys, Scrollbar, Segment, Select, SelectionGesture,
  SlashPalette, Spacer, Spinner, StatusBar, StatusLine, StatusSegment, StreamHandle, Style,
  TUI, Table, Tabs, TerminalScreen, Text, Theme, Toasts, ToolBlock, Transcript, Tree, TreeNode,
  copy_on_select, headless_tui, snapshot, visible_width, wrap_text。
- 各层 facade：core 60 名（core/__init__.py:86-147）、keys 5 名、widgets 22 名、chat 9 名、
  markdown 19 名、app 3 名（EveryHandle/Hit/TUI）、chrome 2 名、selection 2 名、testing 2 名。
  全部由 test_api_root.py:28-53（LAYER_ALLS）逐字 pin。
- 导出面问题：
  - 根手势在、模型不在：SelectionGesture/copy_on_select 上根，Selection/extract/highlight 只到
    core（core/__init__.py:65）；pi_demo 被迫 `from mocode_tui.core import Selection, extract`。
  - 键位表家族拆散：两张 DEFAULT 表在根，COMPOSER_KEYMAP 只在 chat facade。
  - down-list 不对称：Pane 上根，Document/Frame 只在 core。
  - 双主人：Text 由 core 定义、widgets 再导出。
  - 风格：TUI 是唯一 all-caps 类（test_api_root.py:83-84 特判）；Keymap 是 dict 别名混在类列表；
    EveryHandle/Hit 是控制器类型也上根。
  - __all__ 干净，但模块命名空间有"意外公开"（selection.py:73-77 把 Selection/extract/Pane/Hit
    导进模块命名空间而 __all__ 不含）。

## 4. examples/pi_demo.py 审计（849 行）

四段：1-193 常量/imports；196-234 static regions（banner/footer）；237-664 假模型轮次
（_stream/_answer/_spin_tool/_Fold/_tool_call/_apply_edit/_summary/_run_tools/_show_fixture/
_stream_preview/_Preview/_copy_and_toast/_fold_press/_cycle_focus/_run_command/_close_preview）；
667-781 交互循环 chat()；784-849 入口（_script 27 个脚本事件/_headless/main）。

展示了：TUI 文档/流式/seal、anchor_cursor、chat 全家、Markdown 流式（半开 fence/表格安全）、
Table 带样式单元格、Scrollbar、split("vertical", ratios=(2,1)) + pane.close() + tab 焦点循环 +
escape 关预览、Toasts 自定义 on_end（OSC52 + toast）、Selection 手势 + 双击选词 + 拖动、
折叠交互 _Fold、headless 回放。

pi 模仿包袱（可裁剪）：假状态行 token/成本串 _STATUS_LEFT、假模型名 _MODELS、
Update Available 通知、[Skills] 区、π banner/版本、假工具输出文案、example.invalid URL、
pytest 假输出、VERSION 与更新日志文案。

**没展示到的能力**（grep 计数 0）：Tree、Tabs、Panel、Row、Column、ProgressBar、Select、
Confirm、Input、Autocomplete、StatusBar/StatusSegment、Highlighter/RegexHighlighter/highlight
直用、Keymap 重绑定、testing.headless_tui/snapshot、水平拆分、Spacer/Padding、Screen 光标 API。

驱动方式：main 判 sys.stdout.isatty() 走 asyncio.run(TUI().run(chat))，否则 _headless 回放；
chat 循环 read_key → scrollbar.handle or toasts.handle or _fold_press or gesture.handle →
palette.handle_key → editor.handle_key → tab 焦点/escape 关预览/enter 提交 →
create_task(_answer) 后台流式 → anchor_cursor + invalidate。
关键事实：wheel 被吸收依赖 MouseEvent(Key) 继承（core/events.py:51）。

## 5. tools/framebench.py

- 帧开销基准 146 行 stdlib-only；依赖根 API HeadlessScreen/Markdown/Scrollbar/TUI；
  模块导入时读 examples/Markdown-Rendering-Test.md；replay_workload 子进程跑 pi_demo；
  hash_workload 是"渲染字节哈希门禁"（docstring 未提，文档滞后）。--frames 解析简陋。
- **保留**：specs/2026-10-06-frame-budget 各工单把它作为唯一门禁工具。W6 需把 replay 指向 demo.py。

## 6. 测试盘点

31 个测试文件（每个测什么见仓库）；tests/_doubles.py（69 行）共享替身：
Rows（渲染替身）、RecordingScreen（write 记录 + delta()）、texts/many/key。

直接调用私有方法的测试（转正目标）：
- test_app.py:189,253 tui._focused_viewport()；:292-298,344 tui._scroll_viewport(...)；
  :467,563,598 tui._clock = lambda（"documented clock seam"）；:468-612 多处 tui._tick(now[0])。
- test_selection_gesture.py:103,457,478,549,664 tui._clock=...；:115,364,526 tui._tick(...)。
- test_chrome_scrollbar.py:72,305 tui._tick；:227 tui._clock=...。
- test_chrome_toasts.py:64 tui._clock=...；:73,307,311,440 tui._tick；:246,432 tui._frame.overlays
  （公开 TUI.frame 已存在）。
- test_keys_sources.py:307 source._thread（只读）。
- 无测试 import 库内下划线函数；Scrollbar/Toasts/SelectionGesture/KeyDecoder 均经公开
  handle/paint/settle/finish 测试。

附带：tests/__pycache__ 存有 test_chat_tools/test_chat_message/test_components_choice 旧 .pyc
（对应 .py 已不存在）。

## 跨项补充

- MouseEvent 是 Key 子类（core/events.py:51）——app.py:759 的 isinstance(event, Key) 同时拦截
  滚轮；chrome.py:65-69 "wheel is nobody's chrome" 依赖此继承。**重构事件模型必须保留该关系**。
- keys/__init__.py:5-11 明确事件模型归 core、解码/源归 keys；core/__init__.py:37-42 记录迁移史——
  这类 "moved/used to" docstring 叙述是清理项。
