> ✅ 2026-10-05 @ 分支 lib-w6 — 已合并 main

# Spec W6 · chat 层(波次 W6)

> 分支 `lib-w6-chat`;前置:W2、W3、W4 已合并(W5 若已合并更佳,不冲突);深读:总纲、`examples/pi_demo.py` 全文(本波就是把它的装配代码提炼成库组件)、`src/mocode_tui/widgets/`(message.py、tools.py、autocomplete.py、editor.py)、`src/mocode_tui/core/block.py` 与 `core/app.py`。

## 目标

建立 `chat/` 包:pi 风格 coding-agent 组件层。message/tools 从 widgets 迁入并 Theme 化;把 demo 的 `_StatusRow`、`_MenuSlot`、`_WorkSlot`、footer 装配、消息流管理提炼为正式库组件。**demo 本波不改**(W7 重写);`src/mocode_tui/__init__.py` 与 facades 仍归 W7,本波符号走 `mocode_tui.chat.*` 全路径。

## 工单(按序执行,每项一个 commit)

### T1 建包 + message/tools 迁入

- 新建 `src/mocode_tui/chat/__init__.py`(re-export 本包公共符号;W7 会再审)。
- `git mv src/mocode_tui/widgets/message.py src/mocode_tui/chat/message.py`、`git mv src/mocode_tui/widgets/tools.py src/mocode_tui/chat/tools.py`;import 修正;两文件构造签名统一为 Theme 规则(`style=None` + `theme=None`)。
- `widgets/__init__.py` 移除 Message/ToolBlock/EditBlock 的 re-export(**此为本波被授权的 facade 例外**,总纲禁触条款在此豁免这一个文件);root `__init__.py` 暂不动(W7 统一),因此 `from mocode_tui import Message` 本波后会暂时失效——在报告中明确记录,W7 修复。tests 改走 `mocode_tui.chat` 路径。
- 测试迁移:`test_widgets_message.py`/`test_widgets_tools.py` → `test_chat_message.py`/`test_chat_tools.py`。
- demo 若从包根 import Message/ToolBlock/EditBlock 会断——**裁决:demo 临时改从 `mocode_tui.chat` 导入**(这是 examples/ 的唯一授权改动;W7 重写时改回包根)。

### T2 `chat/statusline.py`

- `StatusLine(*, left=(), right=(), theme=None, gap_style=None)`:双侧状态行;左右元素为 `str | (str, Style)`;渲染单行,左部左对齐、右部右对齐,中间 gap 填充;超宽时左部优先保留、右部从左侧 ellipsize(裁决写明,也可反过来,但选定后文档化)。
- 属性可变(`left`/`right` 可整体赋值),供宿主每帧更新。
- 提炼自 demo `_StatusRow`,语义保持一致。
- `tests/test_chat_statusline.py`:双侧对齐、超宽截断、tuple 样式段、单行恒定。

### T3 `chat/slash.py` SlashPalette

- 以 `widgets/autocomplete.py` 的 Autocomplete 为渲染内核,封装 pi 的 slash 语义:
  ```python
  class SlashPalette:
      def __init__(self, commands: list[Option], *, theme=None, max_rows=8): ...
      is_open: bool
      def open(self): ...; def close(self): ...
      def sync_query(self, text: str): ...   # 宿主把 editor 当前值喂进来;非 "/" 开头自动 close
      def handle_key(self, key) -> str | None | False:
          # up/down/enter/escape 被消费;enter 返回选中 value 并 close;
          # escape 返回 None(仅关闭);其他键返回 False(穿透给 editor)
      def render(self, width) -> list[Line]  # 关闭时零行
  ```
- 语义对齐 demo 现行为:palette 与输入解耦,只拥有导航与关闭。
- `tests/test_chat_slash.py`:开闭、`/` 查询过滤、导航消费、穿透键、enter 返回值。

### T4 `chat/composer.py` Composer(控制器)

- `Composer(theme=None, *, prompt="", placeholder="…", commands: list[Option] = ())`;`attach(tui) -> Composer`:一次性向 document 添加 pinned bottom 块链:上 Divider(`id="composer-top"`)→ Editor(`id="composer-input"`)→ 下 Divider → palette 槽(零行占位 block,SlashPalette 开闭时 `set_component` 换入换出)→ StatusLine(`id="composer-status"`)。
- 公开:`editor`、`palette`、`statusline`、`set_working(on: bool)`(ref-count;开启时 `tui.every` 驱动 braille Spinner 写入上 Divider 的 label,全部关闭时清 label 并 cancel handle)。
- IME 锚点辅助:`anchor_cursor(tui)`(取 editor.cursor_position + painter.set_cursor_anchor)。
- Composer 是控制器不是纯组件,依赖 TUI/Document——chat 层允许;模块 docstring 写明。
- `tests/test_chat_composer.py`:headless_tui 下 attach 后块链结构(snapshot 断言 pin 与顺序)、set_working 开关后 Divider.label 变化、palette 开闭块行数变化、detach 语义(如实现)。

### T5 `chat/transcript.py` Transcript(控制器)

- `Transcript(tui, *, theme=None, spacer=True)`:管理正文区消息流。
- `append(component, *, id=None) -> Block`:块间自动插入 `Spacer(1)`(W4 的件;若 W4 未合并则用 `Text("")` 兜底并在报告注明)。
- `stream(role) -> StreamHandle`:`StreamHandle.append(text)`(增量写 Message.text + `tui.invalidate()`)、`.seal()`(块 seal,缓存生效)。
- `clear()` 清空正文区(不动 pinned 区)。
- `tests/test_chat_transcript.py`:append 间隔行、stream 增量渲染、seal 后缓存路径、clear 保留 pinned。

## 验收

1. `uv run pytest -q` 全绿(贴真实输出)。
2. `uv run python examples/pi_demo.py < /dev/null` exit 0(渲染输出可与基线有 diff——仅允许因 Message/ToolBlock/EditBlock 的 Theme 默认值与旧常量逐项相等而**无 diff**;若有 diff 即默认值抄错,逐项核对)。
3. `uv run python -c "from mocode_tui.chat import Composer, Transcript, SlashPalette, StatusLine, Message, ToolBlock, EditBlock"` 正常。

## 禁触清单

`src/mocode_tui/__init__.py`、`core/`、`keys/`、`widgets/`(除 T1 的两个 `git mv` 与 `widgets/__init__.py` 豁免)、`tests/test_api_root.py`、`docs/`、`README.md`、`pyproject.toml`。`examples/pi_demo.py` 仅授权 T1 的 import 修正,其余一行不动。

## 最终报告格式

工单状态表 / commit 清单 / 门禁真实输出 / chat 包公开 API 签名表 / 从 demo 提炼时舍弃的 demo 专属逻辑清单 / 偏差与取舍 / 未决问题。
