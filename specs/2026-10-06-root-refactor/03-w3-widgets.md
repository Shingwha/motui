# Spec root-refactor · 组件层统一清理（波次 W3）

> 分支 `rr/w3-widgets`；前置：W2 已合并（handle 契约）。
> 深读：`specs/2026-10-06-root-refactor/00-overview.md`（总纲，必读，特别是「命名宪法」）+
> `specs/2026-10-06-root-refactor/ref/audit-widgets-chat.md`（全文，本波权威事实清单）。

## 目标

**widgets + chat 组件层按统一规则收敛**：主题解析一个基类、编辑组件一个基类、样式属性
私有化、死组件删除、Markdown 缓存对象化、注册表不可变化、Composer 现代化、模块改名消除
同名冲突。渲染字节零变化（组件的公开行为等价，删除项除外）。

写入范围（范围外零 diff）：
- `src/mocode_tui/widgets/**`（含 `widgets/__init__.py`；`chrome.py`→`decor.py` 改名）
- `src/mocode_tui/chat/composer.py`、`transcript.py`、`message.py`、`tools.py`、`statusline.py`
- `src/mocode_tui/chat/__init__.py`
- 根 `src/mocode_tui/__init__.py`：**仅**删除 `StatusBar`/`StatusSegment` 相关行（授权例外）
- `tests/test_widgets_*.py`、`tests/test_chat_components.py`、`tests/test_chat_composer.py`、
  `tests/test_chat_statusline.py`、`tests/test_chat_transcript.py`、`tests/test_theme.py`
- `examples/pi_demo.py`（仅机械同步：`Composer(commands=...).attach(tui)` → `Composer(tui, commands=...)`；
  `composer.prompt` 若被引用则删该行）

禁触：`core/**`（`core/theme.py` 加 `Themed` 基类除外——这是你唯一允许的 core 改动）、
`keys/**`、`app.py`、`chrome.py`（根）、`gesture.py`/`selection.py`、`tests/test_app.py`、
`tests/test_api_root.py`（根面只剩删 StatusBar 两行，test_api_root 的 ROOT_ALL 由 lead 在合并时
同步——**若 pytest 因 test_api_root 断言 68 名而失败，改 test_api_root.py 的 ROOT_ALL 行
删除 StatusBar/StatusSegment 两个名字**，这是第二处授权例外，报告声明）、README、docs、tools。

## 工单（按序执行，每项一个 commit）

### T1 Themed 基类 + 主题解析收敛
- `core/theme.py` 新增：

  ```python
  class Themed:
      """Base for components that resolve styles against a theme at construction."""
      def __init__(self, theme: Theme | None = None) -> None:
          self._theme = theme or DEFAULT_THEME
      def _pick(self, style: Style | None, field: str) -> Style:
          return style if style is not None else getattr(self._theme, field)
  ```

  （签名可微调，语义不变。）
- 全部有色组件（audit B 第 3 节列出的 19 处 `theme or DEFAULT_THEME` 消费者）改继承
  `Themed`，构造存 `super().__init__(theme)`，渲染取 `_pick(self._x_style, "field")`。
- **样式属性私有化**：删除"写入即死"的公开样式属性（`self.style`/`self.prompt_style`/…），
  一律 `self._style` 等私有（audit B §4 P1 的清单）。例外保留：内容属性
  （`Text.text`、`Divider.char/label`、`Message.text`、`ToolBlock.title/body/footer`、
  `Notice.text/level`、`Markdown.text` 等）公开可变不变。
- 无色组件（Row/Column/Spacer/Padding）不加 `theme=`（保持现状）；`Spinner` 保持无 theme。
- 渲染字节必须逐字节不变（每个组件 render 的输出与改前一致）。

### T2 Input / Editor 基类抽取 + 属性统一
- 新建共享基类（放 `widgets/editor.py` 内或新文件 `widgets/field.py`，命名如 `_TextField`
  或 `TextEntry`——建议 `widgets/field.py` 的 `_TextField` 私有基类，Input/Editor 是薄子类）：
  承载 TextBuffer 组合、`handle(event)`、11 个编辑方法转发、render 主干（prefix/placeholder/
  cursor 三分支）、`cursor_position(width)`。
- Input = 单行窗口 + prompt；Editor = 多行窗口 + max_rows + 居中滚动。
- **属性统一**：`Editor.value` → `Editor.text`（与 Input.text 对齐）；`Input.cursor`/`Editor.cursor`
  统一返回 `tuple[int, int]`（row, col；Input 的 row 恒 0）。`Editor.row/col/lines` 若仅测试用
  则删，测试改走 cursor/text。
- placeholder 光标语义分裂修复：Input 传 0 vs Editor 传 len(placeholder)（audit B §1 P2）——
  统一为一种（以渲染字节不变为准绳，选现状字节等价的那种；若两者渲染本就不同，保持各自
  行为并在报告声明——**行为保持优先于统一**）。
- textbuf.py:400-408 的字符索引/显示宽度混用：**行为保持**，仅补注释说明两制度边界，
  不强改（这是 wcwidth 语义问题，留给未来）。

### T3 删除 StatusBar / Spinner.render
- 删 `widgets/status.py` 整文件（StatusBar/StatusSegment 零消费者）。
- 删 `Spinner.render`（死方法）；`Spinner` 保留 frames/advance/frame/text。
- `widgets/__init__.py`、根 `__init__.py`（授权例外两行）同步删。
- `tests/test_widgets_basics.py` 中 StatusBar 段删除、Spinner.render 断言删除。
- 若 `tests/test_api_root.py` 因根面名单失败 → 授权例外第二处（见上）。

### T4 Markdown 清理
- 流式缓存抽独立类：`_CachedRender` + `_resume_append_only`（component.py:58-130）收编为
  一个私有 `_StreamCache` 类（可放 component.py 内）；`_run_blocks` 的 start/out/boundaries
  逃逸参数（blocks.py:205-214）随之清理。`resume == 0` 兼作哨兵的脆弱点改为显式
  `boundaries` 空列表判断。渲染字节不变（`tools/framebench.py` 的 stream 单元是它的直接验证）。
- 注册表不可变化：`BLOCK_RULES`/`INLINE_RULES` 改为 `tuple`（模块级单例不再可变）；
  `default_block_rules()` 返回**新 list**（每次调用新建），新增对称的 `default_inline_rules()`；
  `Markdown(block_rules=None)` 默认取 `list(BLOCK_RULES)`（防御共享泄漏，audit B §4 P2）。
  markdown/__init__.py 的导出同步（default_inline_rules 加入）。
- markdown/blocks.py:90、nested.py:133 的 "defensive" 分支：核对后删或保留（若 match()
  真的 gate 住了形状，删；不确定就保留但把注释写实）。

### T5 widgets/chrome.py → decor.py
- `git mv widgets/chrome.py widgets/decor.py`（Notice/Divider/Panel；保留 DEFAULT_HEADER_STYLE
  的长注释清理）。
- `widgets/__init__.py`、tests 的 import 同步；模块 docstring 去 "used to live" 迁移史。
- 带标签横线渲染两遍（Divider vs Panel 的 ellipsize_tail+fill，audit B §3）：收敛为一个
  模块内 helper（decor.py 私有函数），渲染字节不变。

### T6 Composer / chat 清理
- **构造即挂载**：`Composer(theme=None, *, prompt=..., placeholder=..., commands=[])` →
  `Composer(tui, *, theme=None, placeholder=..., commands=[])`——构造内完成原 attach 的
  全部动作；`attach` 方法删除；`detach()` 保留。与总纲命名宪法一致。
- `anchor_cursor(tui)` → `anchor_cursor()`（用构造时存的 tui；宿主不再重复传参）。
- 删 `Composer.prompt`（存而不用）。`SPINNER_INTERVAL`/`WORKING_LABEL` 保留为类常量
  （默认值语义），docstring 去 "the demo's footer plumbing" 叙述。
- `_PaletteSlot` 保留（它是防 stale palette 的正确组合方式），docstring 压缩为三行内。
- chat 四个纯组件（Message/ToolBlock/EditBlock/StatusLine）与 SlashPalette **留在 chat 层**
  （lead 裁决，概念内聚）；它们的 docstring 去 pi 化措辞（"pi-style"/"pi rhythm" 等改写为
  "the conversational rhythm" 之类的通用表述）。
- `Transcript`/`StreamHandle`：`StreamHandle.append` 与 `Transcript.append` 同名不同义——
  StreamHandle 改名 `write(chunk)`？**不**：StreamHandle.append 语义正确（流式追加），
  Transcript.append 也是（追加一个 component）。保留，docstring 各自写清。
  `tests/test_chat_transcript.py` 不动。
- chat/__init__.py 与 widgets/__init__.py 的 docstring 去迁移史叙述。

### T7 交互协议：click 收编
- `core/block.py` 加（你唯一的另一处 core 授权改动，与 T1 的 core/theme.py 并列）：

  ```python
  class Clickable(Protocol):
      def click(self, row: int) -> bool: ...
  ```

  （runtime_checkable，可选协议——组件可以不实现。）
- `Select.click`/`Confirm.click` 保留（已内部消化 title 偏移）；`Tabs.click(row)`、
  `Tree.click(row)` 新增（行为=activate 对应行，越界返回 False）；
  `Autocomplete.click(row)` 新增（行为=选中可见窗口内第 row 行的项，越界 False）。
- 返回值统一 `bool`（是否命中）。
- tests：test_widgets_choice/tabs/basics/autocomplete 各加最小断言。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 零失败。
2. `uv run python tools/framebench.py` 的 `render-hash` 逐字等于
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`。
3. `uv run python examples/pi_demo.py < /dev/null` 退出码 0。
4. `grep -rn "theme or DEFAULT_THEME" src/mocode_tui/ | grep -v "core/theme.py"` 零命中
   （解析模板清零，Themed 基类独占）。
5. `grep -rn "StatusBar\|StatusSegment" src/ tests/` 零命中。
6. `grep -rn "\.attach(" src/ examples/ | grep -i composer` 零命中。
7. `uv run python -c "from mocode_tui import Composer, Transcript, Markdown, Table, Tree, Tabs, Panel, Row, Column, ProgressBar, Select, Confirm, Input, Autocomplete, Spinner"` 成功。

## 禁触清单

见上。特别地：`core/` 除 theme.py 的 Themed 与 block.py 的 Clickable 外一行不动；
`tests/test_app.py`、`tests/test_frame.py` 等 W1/W4 的测试文件不动；`tools/**` 不动。

## 最终报告格式

工单状态表（T1–T7）/ commit 清单 / 自测真实结论（七条命令输出摘要）/ 偏差与取舍
（placeholder 语义选择、_StreamCache 设计、保留的 defensive 分支清单）/ 未决问题。
阻塞即停：报告阻塞点后停止，不越界自救。
