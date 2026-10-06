# 审计报告 B：widgets + chat（权威参考）

> 2026-10-06 全文审计取证。行号对应审计时刻的 main（c153d04），以符号名定位为准。

## Top 发现

| 级别 | 事实 | 证据 |
|---|---|---|
| P0 | 两套状态栏组件并存，StatusBar 零消费者，已被 StatusLine 取代 | widgets/status.py:28 / chat/statusline.py:71 / chat/composer.py:167,202 |
| P0 | Spinner.render 是死方法：两个真实消费者都只取 frame/text 自己拼行 | widgets/spinner.py:60-64 vs chat/composer.py:263-268、examples/pi_demo.py:309-314 |
| P0 | Input 与 Editor 对同一 TextBuffer 把全部编辑方法逐条复制转发，handle_key 契约两份文档 | widgets/input.py:139-175 vs widgets/editor.py:159-200 |
| P0 | 事件路由函数名/返回类型分裂：handle_key->bool、handle->bool、handle_key->str|None|False | widgets/input.py:120；selection.py:184；chat/slash.py:107 |
| P0 | Select.click(row)/Confirm.click(row) 与 move()/handle_key 并列成第二种交互方式，无协议 | widgets/choice.py:132-147；app.py:807 |
| P0 | 根层与 widgets 层各有一个 chrome.py，层性与职责完全相反 | mocode_tui/chrome.py:85（装配层）vs widgets/chrome.py:24（纯渲染） |
| P1 | Markdown 组件内嵌流式增量缓存补丁（错峰续渲染），含脆弱哨兵 | widgets/markdown/component.py:58-130,116-118 |
| P1 | 9 个导出组件在 src/examples 无消费者：Input, Panel, ProgressBar, Tabs, Tree, Confirm, StatusBar, Row, Column, Padding | 见第 4 节 |

## 1. 补丁式代码

**P1 — Markdown 流式缓存混在组件类内** `widgets/markdown/component.py:58-130`：_CachedRender +
_resume_append_only 约 70 行。脆弱点：`:116-117` 用 `resume == 0` 兼作"没有边界"哨兵；
`:118` 再次过滤与前文循环语义重叠；`_run_blocks` 为复用被加 start/out/boundaries 三个逃逸参数
（markdown/blocks.py:205-214）。

**P1 — Composer 的 _PaletteSlot 兼容适配器** `chat/composer.py:85-107`：palette 不直接换 block
component，而是包一层"永远渲染、关时零行"的槽；docstring 自述针对曾出现 stale palette 的补丁
（:90-95）。同文件 :15-24 记录 D6 拆波迁移史。

**P1 — COMPOSER_KEYMAP 是键盘解码缺陷的绕行** `chat/composer.py:32-36` "the decoder emits no
c-enter name"；`:79-82` 用过滤复制构造。

**P2 — 防御性早退分支** markdown/blocks.py:90、markdown/nested.py:133 各有"defensive: match()
gated this shape"；textbuf.py:281-283 标注 unreachable 分支。

**P2 — 历史常量/注释** table.py:43-46 DEFAULT_HEADER_STYLE 长注释；chat/tools.py:14-21、91-93
W8 迁移史；core/theme.py:165-169 W11 调色板迁移史；widgets/layout.py:12-19 迁移叙述；
widgets/__init__.py:11-13、chat/__init__.py:6-12 迁移叙述。

**P2 — 制表符归一化散落三处** textbuf.py:297、core/lines.py:290、core/text.py:463-464 各自
`text.replace("\t", " ")`，无单一入口。

**P2 — Input/Editor placeholder 光标语义分裂** input.py:216 传 0；editor.py:244 传
len(self.placeholder)；textbuf.py:400-408 同函数内混用字符索引与显示宽度。

**P3 — max_rows=0 协议洞** editor.py:237 render 返回 [] 而 cursor_position 仍报 (0, col)（226-228）；
tree.py:110-113 `_cursor` 可能越界旧值（158-160 只读夹取）。

## 2. 命名不一致

- **事件入口**：handle_key（input.py:120/editor.py:140/textbuf.py:108）vs handle（selection.py:184、
  chrome.py:267,781）vs 三态 handle_key（slash.py:107）。
- **生命周期词汇四套**：open/close（slash.py:80,90）、show/detach（chrome.py:730,760）、
  attach/detach（composer.py:182,212）、seal（transcript.py:50）。
- **同一"文本"属性两个名字、同一"光标"两种类型**：input.py:105 `text` vs editor.py:110 `value`；
  input.py:110 `cursor -> int` vs editor.py:134 `cursor -> (row, col)`；Input 没有 row/col/lines。
- **游标/选中状态命名各异**：Select.index（choice.py:117）、Autocomplete.index（autocomplete.py:78）、
  Tabs.active（tabs.py:69）、Tree._cursor 私有（tree.py:90）；布尔词分裂 TextBuffer.empty（textbuf.py:92）
  vs Autocomplete.is_empty（autocomplete.py:114）vs SlashPalette.is_open（slash.py:75）。
- **增删条目动作名五个**：Document.add、Transcript.append（transcript.py:75）、StatusBar.segment
  （status.py:49）、Toasts.show（chrome.py:730）。
- **样式参数命名家族漂移**：selected_style（choice）vs active_style（tabs）vs cursor_style（tree/input）；
  Spinner/StatusBar/Row/Column/Spacer 无 theme=。
- **构造参数风格**：Select(options) 必填位置（choice.py:99-101）vs Autocomplete(*, options=())；
  Composer(theme=None, *, ...) vs Transcript(tui, *, ...)。
- **同概念属性名**：Select.options、Tree.root_nodes、Tabs.tabs、SlashPalette.commands、Composer.commands。
- **文档漂移**：docs/COMPONENTS.md:136 声称 Autocomplete 有 handle_key；代码无此方法。

## 3. 重复逻辑

- **P0 Input/Editor 双份转发壳**：input.py:139-175 与 editor.py:159-200 逐条同体 11 个方法；
  handle_key docstring 两份长文，实现都只是转调。
- **P0 StatusBar vs StatusLine**：同一"单行状态条"两次实现（status.py:53-62 优先级裁剪 vs
  statusline.py:105-111 左右对齐）。Composer 只用 StatusLine；StatusBar 零消费者。
- **P1 注册表扫描循环复制**：syntax.py:455-477 与 markdown/inline.py:58-80 结构逐句对应
  （syntax.py:451-453 自认 "same guard the inline markdown engine uses"）。
- **P1 满宽色带/填充行构造 4 套**：message.py:80-103 手拼 Segment、tools.py:34-47 _banded_row、
  layout.py:183-199 Padding._content_row（绕过 core.lines.overlay）、table.py:222-248 _cell_parts。
  内核已有 Line.filled（lines.py:196）、overlay（lines.py:311）、pad_to（lines.py:188）。
- **P1 带标签横线渲染两遍**：widgets/chrome.py:106-120（Divider）与 174-181（Panel）各自
  ellipsize_tail + fill；table.py:250-260 _rule 第三种。
- **P1 语言标签归一化重复**：syntax.py:407-416 _normalize_lang、markdown/blocks.py:107-115
  _fence_lang、RegexHighlighter.highlight 内部再调一次（syntax.py:524）。
- **P1 "explicit > theme > DEFAULT" 解析模板复制约 19 处**：chrome.py:43,97,155、editor.py:93、
  progress.py:65、tree.py:92、choice.py:119,186、tabs.py:63、input.py:87、autocomplete.py:81、
  syntax.py:503、table.py:149、message.py:65、tools.py:86,143、statusline.py:101、
  markdown/component.py:188、composer.py:192。
- **P2 Input/Editor render 主循环近似复制**：input.py:208-225 与 editor.py:239-258 同构。
- **P2 窗口"保持游标可见"四种实现**：autocomplete.py:139-151（顶部悬挂）、editor.py:204-213
  （居中）、tree.py:158-160（夹取）、status.py:56-61。语义不同是特性，不强合。
- **P2 换行三个入口**：TextBuffer 用 wrap_spans（textbuf.py:298）、Markdown 用 wrap_line
  （blocks.py:98,202）、Message 用 wrap_text（message.py:76）——输出形态不同，行为保持。
- **P2 chat 内两个行构造 helper 同名不同义**：statusline.py:44-63 _row 与 tools.py:34-47 _banded_row；
  transcript.py:45 StreamHandle.append 与 :75 Transcript.append 同名不同事。

## 4. 死代码 / 冗余

- **P0 Spinner.render**（spinner.py:60-64）：库与示例均无消费者，仅测试调用。
- **P0 StatusBar/StatusSegment**（status.py:28）：零消费者（导出于 widgets/__init__.py:30,52、
  根 __init__.py:78；唯一使用 tests/test_widgets_basics.py:115-140）。被 StatusLine 取代。
- **P1 无库内消费者的导出组件**（公开 API 但无宿主路径验证）：Input（Composer 用 Editor）、
  Panel、ProgressBar、Tabs、Tree/TreeNode、Confirm、Row/Column/Padding。
  → demo.py 的职责之一就是把它们全部用起来。
- **P1 "写入即死"的公开样式属性**：构造存公开属性、渲染读私有副本——input.py:80-82 vs :211,220、
  editor.py:84-85、choice.py:112-115、autocomplete.py:73-75、tree.py:86-88、tabs.py:57-58、
  table.py:143-145、progress.py:61-62。例外（render 时读公开属性）：widgets/chrome.py:100-101,158、
  chat/message.py:71,73,89。两种可变性哲学并存且无标记。
- **P2 Composer.prompt 存而不用**（composer.py:160）。
- **P2 注册表双形态**：markdown/component.py:35-55 既有工厂 default_block_rules() 又有模块级单例
  BLOCK_RULES；默认路径直接引用可变共享 list（component.py:193-194），自定义规则可泄漏到其他实例。
- **P2 TextBuffer 带公开名却不在任何 facade**（textbuf.py:32 __all__）。
- **P3 仅内部使用的公开方法**：autocomplete.py:114-117 is_empty、editor.py:115-136 row/col/lines、
  textbuf.py:102-104 offset setter 只被 Input.cursor setter 转发。

## 5. API 不简洁处

- **P0 同一交互两套做法**：move(delta)/handle_key 与 click(row) 并列，无协议；文档示范
  duck-typing `hit.block.component.click(hit.row)`（app.py:807），Tabs/Tree/Autocomplete 须另写宿主循环。
- **P0 构造参数过多/多态 cell 类型**：table.py:128-140 单构造 7 参且 cell 类型四态；input.py:66-77、
  editor.py:71-82 各 8 个 kwarg；markdown/component.py:166-176 7 个。
- **P1 render(width) 之外的逃逸口无统一协议**：cursor_position(width)（input.py:179、editor.py:215，
  仅 composer.anchor_cursor 用，editor.py:226-228 内部重复计算 visual rows 两次）；
  TextBuffer.handle_key(key, indent=0) 的 indent 只为 Input 存在；Composer 生命周期
  attach/detach/set_working/anchor_cursor（未 attach 抛错 :248,:289）；advance()；set_query()；
  open/close；move/click/toggle/activate。
- **P1 anchor_cursor(tui) 重复传参**：composer.py:277 已由 attach 存 self._tui，宿主每次按键
  还要再传 tui（pi_demo.py:687,707,721,758）。
- **P1 SlashPalette.handle_key 三态返回**（slash.py:107）。
- **P2 Markdown 可变 text + 隐式缓存**（component.py:164 __slots__ 公开 text 私有 _cache）。
- **P2 三入口集合**：StatusBar segments= 构造 + segment() + 公开 self.segments；
  Autocomplete options + 公开 query/index + set_query；Editor.lines 直接暴露内部 list。
- **P2 默认值类型标注不实**：composer.py:157 `commands: list[Option] = ()`；status.py:45
  `segments: list[StatusSegment] = ()`；autocomplete.py:64 options 无标注；transcript.py:70 theme 无标注。
- **P3 构造风格各行其是**：Notice(text, *, ...)、Divider(*, ...) 全关键字、Panel(child, *, ...)、
  Message(role, text, *, ...)、ToolBlock(title, body, *, ...)、EditBlock(path, context, removed, added, *, ...)。

## 6. 组件协议一致性

- 纯渲染：Row、Column、Spacer、Padding、Notice、Divider、Panel、Table、ProgressBar、Message、
  ToolBlock、EditBlock、StatusLine、StatusBar（额外 segment()）。
- 纯渲染 + 控制器方法：Input/Editor（handle_key+编辑方法）、TextBuffer（纯引擎无 render）、
  Autocomplete（set_query/move）、Select/Confirm（move/click）、Tabs（activate/move）、Tree
  （move/toggle）、Spinner（advance）、SlashPalette（open/close/set_query/handle_key）、
  Markdown（可变 text + 缓存）。
- 完全不遵守 render 协议的控制器/引擎：Composer（attach/detach/set_working/anchor_cursor）、
  Transcript/StreamHandle（append/stream/clear/seal）、TextBuffer。
- widgets/__init__.py:3-4 声称 "Each component implements the frozen protocol"，但导出的
  Autocomplete/Select/Confirm/Tabs/Tree/Spinner/StatusBar/Input/Editor 半数是状态机——声明与
  导出面不符。控制器生命周期词汇互不兼容（attach/show/open/seal）。

## 7. chat 层与 widgets 层的边界

- **P0 模块名跨层冲突**：根 chrome.py（装配层，import TUI）vs widgets/chrome.py（纯渲染）。
- **P1 状态行同类组件被拆两层**：widgets/status.py（StatusBar）与 chat/statusline.py（StatusLine）。
- **P1 chat 里三个纯 core 依赖的组件其实属于 widgets 层**：Message（chat/message.py:21-29 只 import
  core）、ToolBlock/EditBlock（tools.py:25-29）、StatusLine（statusline.py:26-31）。
  反向：SlashPalette 只依赖 core.events + widgets（slash.py:42-46），是可复用的按键驱动命令面板。
  → **lead 裁决：四者全部留在 chat 层**（对话概念内聚；依赖方向仍干净），仅清理措辞。
- **P1 chat 控制器直接依赖 app 层**（composer.py:59、transcript.py:19 `from ..app import TUI`）——
  合法（chat 是 L2），但 chat 内纯组件与控制器混居，包级文档只口头区分。
- **P1 Composer 承担 widgets 层欠账**：_PaletteSlot（composer.py:85-107）、Spinner→Divider 标签
  耦合（263-268，致 Spinner.render 无人用）、COMPOSER_KEYMAP 过滤复制（79-82）。
- **P2 业务文案固化进库**：composer.py:12-13 "the demo's footer plumbing"、:127-132
  SPINNER_INTERVAL/WORKING_LABEL。
- **P2 facade 分层口径不一致**：根 __init__.py:29 直接 re-export Composer/StatusLine；而
  widgets/__init__.py:8-10 声明 chat 组件不再在 widgets 层 re-export——迁移期两套世界观并存。

## 附：重构优先建议（lead 已裁决采纳与否）

1. 合并 StatusBar/StatusLine → **删 StatusBar**（采纳）。
2. 统一事件契约 handle(event)->bool，click 收编为可选协议 → **采纳**。
3. Input/Editor 抽共同基类 → **采纳**。
4. Spinner.render 与 Composer 的 Divider 标签逻辑二选一 → **删 Spinner.render**（采纳）；
   清除 Composer.prompt（采纳）。
5. 收敛 theme/style 解析为共享 helper → **Themed 基类**（采纳）。
6. Markdown 缓存/续渲染抽成独立策略对象 → **采纳**（私有类，渲染字节不变）。
7. 根 chrome.py 保留；widgets/chrome.py 改名 decor.py（采纳）。
8. 清理迁移期 docstring 与 DEFAULT_HEADER_STYLE、W8/W11 历史注释（采纳）。
