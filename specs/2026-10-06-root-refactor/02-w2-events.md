# Spec root-refactor · 事件契约统一 + keys 清理（波次 W2）

> 分支 `rr/w2-events`；前置：无（与 W1 并行，写入范围不相交）。
> 深读：`specs/2026-10-06-root-refactor/00-overview.md`（总纲，必读，特别是「命名宪法」表）+
> `specs/2026-10-06-root-refactor/ref/audit-widgets-chat.md`（第 1、2 节）+
> `specs/2026-10-06-root-refactor/ref/audit-keys-api.md`（第 2、6 节）。

## 目标

**全库事件消费契约统一为 `handle(event) -> bool`**（含 SlashPalette 的三态返回改造），
keys 层死代码清除、三张默认 keymap 表归位。渲染字节零变化。

写入范围（范围外零 diff）：
- `src/mocode_tui/keys/**`
- `src/mocode_tui/widgets/input.py`、`widgets/editor.py`、`widgets/textbuf.py`
- `src/mocode_tui/chat/slash.py`
- `src/mocode_tui/chat/__init__.py`（仅 COMPOSER_KEYMAP 的 import 来源行）
- `tests/test_keys.py`、`tests/test_keys_sources.py`、`tests/test_widgets_editing.py`、
  `tests/test_chat_slash.py`、`tests/test_readme_examples.py`（仅契约调用点）、`tests/_doubles.py`（如需）
- `examples/pi_demo.py`（**仅机械同步调用点**：`editor.handle_key(`→`editor.handle(`、
  `palette.handle_key(`→`palette.handle(`+取值行；不得做任何其他改动）

禁触：`core/**`、`widgets/` 其他文件、`chat/` 其他文件、根 `__init__.py`、`app.py`、
`chrome.py`、`selection.py`、README、docs、tools。`chrome.py`/`selection.py` 的方法本就
叫 `handle`，无需触碰（若 import 行因 keys 改动需调整，仅限 import 行并在报告声明）。

## 工单（按序执行，每项一个 commit）

### T1 事件契约：handle(event) -> bool
- `TextBuffer.handle_key(key, indent=0)` → `handle(event)`。`indent` 参数现状只服务 Input 的
  自动缩进（先 grep 确认）：若能将缩进逻辑上移到 Input 而行为字节不变，就上移并删参数；
  否则保留参数并在报告声明理由。textbuf.py 的 docstring 与 input.py:121-136、editor.py:141-156
  的两份长契约文档合并为一份（放 TextBuffer.handle 或共享基类处，W3 才抽基类——本波先消除
  两份复制：Input/Editor 的 docstring 缩为一行引用）。
- `Input.handle_key` → `Input.handle`；`Editor.handle_key` → `Editor.handle`。
  返回值语义不变（消费=True，未消费=False 回宿主）。
- 全库同步调用点（你的范围内）：tests、pi_demo 机械同步。注意 `tests/test_readme_examples.py`
  里的 README 片段副本（该测试直接执行 README 中的代码字符串——确认其来源；若片段内嵌于
  README.md，README 本身禁触，只改测试文件里能改的部分；若测试从 README.md 抽取代码执行，
  则该测试**本波会失败**——此时允许改 README.md 中**仅** `handle_key`→`handle` 的词面
  （这是唯一允许的 README 改动，逐字最小，报告声明），保持门禁绿）。
- `MouseEvent` 判序事实：调用方先判 MouseEvent 再判 Key 的顺序**不得改变**（MouseEvent 是
  Key 子类）。顺手把你范围内冗余的 `Key | Paste | MouseEvent` 类型标注改为 `Key | Paste`。

### T2 SlashPalette 三态返回改造
- 现状 `handle_key(event) -> str | None | False`（slash.py:107）：返回选中命令值 / 导航消耗 /
  不是本 palette 的键。
- 目标：`handle(event) -> bool`（消费与否）+ 公开属性 `chosen: str | None`——选中命令时
  handle 返回 True 且 `chosen` 记录命令 value；宿主读后置 `None` 清空。
  与总纲命名宪法一致。
- pi_demo 机械同步（`selected = palette.handle_key(event)` → `if palette.handle(event): ... palette.chosen`）；
  tests/test_chat_slash.py 同步。

### T3 keys/console.py 死代码清除
- 删：`_key_from_console_event`（console.py:228-246，零调用）、`_MOUSE_HWHEELED`（:85）、
  `_DOUBLE_CLICK`（:83）、`AsciiChar` 死成员（:152）、模块 docstring 与结构体注释的重复段
  （19-25 vs 143-148）。
- **保留**：`_key_from_values` 的 ctrl+字母分支与 VK_A..VK_Z 兜底（非 VT 语义可达、有测试）、
  `keys_from_console_events`、`windows_input_mode`。
- sources.py 对 console 的 import 同步。

### T4 COMPOSER_KEYMAP 归位 keys/keymap.py
- 三张表的派生链同堂：`DEFAULT_INPUT_KEYMAP` → `DEFAULT_EDITOR_KEYMAP` → `COMPOSER_KEYMAP`
  全部定义在 `keys/keymap.py`（COMPOSER_KEYMAP 的构造从"过滤复制"改为显式字面量表或保持
  派生表达式，二选一，报告声明；表内容逐键不变——**enter 不绑定是 Input 的契约、c-j 是
  Composer 的 newline，逐键对比验证**）。
- `chat/composer.py` 改为 `from ..keys.keymap import COMPOSER_KEYMAP`；
  `chat/__init__.py` 的 import 来源行同步（facade `__all__` 不变，test_api_root 不动）。
- docstring 更新：keys/keymap.py 写明三表关系；chat 侧删重复叙述。

### T5 契约文档同步（代码内）
- 你范围内所有 docstring 中出现 `handle_key` 的地方改为 `handle`；"Consume a key" 一节的
  措辞统一为 "Consume an event"（事件不只 key）。
- keys/__init__.py 的层级叙述保持（事件模型归 core 的说明正确，保留）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 零失败。
2. `uv run python tools/framebench.py` 的 `render-hash` 逐字等于
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`。
3. `uv run python examples/pi_demo.py < /dev/null` 退出码 0。
4. `grep -rn "handle_key" src/ tests/ examples/ | grep -v "handle_keymap"` 零命中
   （除 keymap 值字符串如 "newline" 外，方法名 handle_key 全库清零）。
5. `grep -rn "str | None | False\|str|None|False" src/mocode_tui/` 零命中。

## 禁触清单

T1 列明之外的一切（见上）。特别地：`widgets/autocomplete.py`（它有 `set_query` 但没有
handle_key，不属本波）、`widgets/markdown/**`、`chat/composer.py` 的非 import 行、
`chrome.py`、`selection.py`、根 `__init__.py`、`app.py`。

## 最终报告格式

工单状态表（T1–T5）/ commit 清单（hash+message）/ 自测真实结论（四条命令输出摘要）/
偏差与取舍（indent 参数去向、README 词面改动清单、COMPOSER_KEYMAP 构造方式）/ 未决问题。
阻塞即停：报告阻塞点后停止，不越界自救。
