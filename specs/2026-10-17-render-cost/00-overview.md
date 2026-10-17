# Spec render-cost · 每帧代价：行缓存、修订令牌与合成路径（波次 W1–W5）

> 日期 2026-10-17；基线 main `dae2e7a`；分支 `rc-w1-row-cache`、`rc-w3-compose`、`rc-w2-table-editor`、`rc-w4-markdown`、`rc-w5-docs`。
> 协议：见 spec-team SKILL 的「Git / worktree 协议」——worktree 在
> `C:\Users\shifu\.worktrees\mocode-tui\<分支>`，agent 不 merge / 不 push / 不 tag /
> 不 checkout main、不碰主检出与其他 worktree；spec 归 lead，agent 不更新任何 spec。
> commit 风格：英文一行祈使句。

## 目标与范围

最高约束：**渲染字节零变化**——本轮全是"同一份输出、更少的计算"。`golden` 11 页与
`framebench` 的 `render-hash`（`de48e747…`）必须保持一字不动；唯一允许的可见行为变化是
**修好 sealed 块的 hover/赋值不落屏**（那条现在是 bug，见 D4）。

**做**（lead 已拍板）：

1. **行缓存搬到 `Block` 上**（`Block.rows(width)`，键 = `(宽度, 修订令牌)`），全仓所有
   "走块拿行"的路径共用它：viewport 布局、`TUI.reveal`/`_body_address`、`Find`、
   gesture 的 `_walk`/双击、`Selection.extract`。今日的 5 处裸 `block.render(width)`
   逐个改掉。
2. **修订令牌（revision）协议**：组件可选实现 `revision()`，返回"行所依赖的一切"的值快照；
   缓存命中 = 令牌相等。**它同时是 sealed 块陈旧 bug 的解**：hover 变→令牌变→重渲。
3. **组件侧的记忆**：`Text`（最大头，29 ms/帧）、`Table`（24 ms）、`Editor`/`Input`
   （9 ms/帧、9 ms/键）加 `(内容, 宽度)` 记忆；`Markdown`（尾块增量、
   命中路径的 `_stamp_tasks`/`_span_index`）、语法高亮（按行）、容器（只包装可见行）。
4. **`frame.compose` 的每帧路径**：挂滚动条/split 时的 13.6× 关掉 pass-through 问题。
5. **度量尺**：`tools/framebench.py` 新增 `text-open`、`table-open`、`stream-paragraph`
   三行（只加不改），基线记进本 spec 与工具 docstring 的基线段落。

**不做**（遗留清单，报告里写明）：`Table`/`Tree`/`Radio` 的真窗口化（需要"块知道窗口"的
新协议，本轮用记忆把**稳态**代价按下去，首次全量物化的代价留着）；`List` 前缀跳转索引
（100k 项 4.94 ms/键，P2）；`Select`/`Autocomplete` 的 description 列记忆；`Spinner` 的
动画在 sealed 块里冻结（是否算 bug 待定）；`Document` 之外的第三方组件无 revision 时的行为
（保持今天：sealed 按宽度冻结）。

## 拍板决策（照抄执行，不现场猜）

| # | 决策 | 取值 |
|---|---|---|
| D1 | 缓存归属 | 从 `Viewport` 搬到 `Block`：新增 `Block.rows(width) -> list[Line]`（缓存入口，键 `(width, revision)`），`Block.render(width)` 保持原义（直通组件，不缓存）。`Viewport` 的 `_cache`/`_cache_width`/`_prune_cache`/`_block_rows` **删除**——缓存随 Block 生灭，换 id 复用/移除的陈旧问题自然消失 |
| D2 | 缓存条件 | 块 **SEALED** → 一律缓存（键含 revision，无 revision 时按 `(width, None)`，即今天的语义）；块 **OPEN** → 仅当组件实现 `Revisioned` 才缓存（键含 revision），否则每次直通（今天的语义）。`tests/test_viewport.py:175-196` 的调用计数断言必须**不改一行**继续绿 |
| D3 | 修订协议 | `kernel/block.py` 加 `Revisioned`（`runtime_checkable` Protocol）：`def revision(self) -> object`——"行的全部输入的值快照，相等 ⟹ 同宽下行相等"。`Block.revision` 无协议时取 `None`。快照必须是**值语义**（对可变字段要拷贝，如 `Table.rows` 的 `[list(row) …]` 快照），且代价必须 ≪ 它守的 render（验收：≤ render 的 5%） |
| D4 | sealed 陈旧 bug | 修法就是 D1+D3：sealed 块命中缓存的键含 revision，hover/赋值改了令牌 ⇒ 未命中 ⇒ 重渲。**W1 起**：`Text`、`Button`、`Checkbox`、`Link` 实现 `revision()`；**W2 起**：`Table`、`Editor`/`Input`/`Field`、`Select`/`Radio`/`Autocomplete`/`List`/`Tree`；**W4 起**：`Markdown` |
| D5 | `Text` 的记忆 | `Text.render` 在 `_revision()` 不变且宽度相同时返回缓存行的拷贝；`_rows_for` 仍是子类接缝，`_revision()` 是**可覆写**的接缝（子类加自己的状态；返回 `None` 即关闭缓存）。`_rows` 仍是"上次渲染的命中表"，语义不变 |
| D6 | `TextBuffer` 的 wrap 缓存 | 按逻辑行缓存 `(行文本, 内宽) → spans`；同行编辑只失效该行，结构性变更（换行/跨行粘贴/`set_text`）清空整表。`TextBuffer` 加单调 `version`（每次变更 +1），`Editor`/`Field`/`Input` 的 `revision()` 以它为主 |
| D7 | `Table` 的记忆 | 键 = `(rows 值快照, headers, 显式 widths, index, hover_row, focused, 相关样式/主题, width)`；值快照用于**探测原地修改**（`self.rows` 是裸可变列表，`rows == cached` 会因同一对象而恒真——必须存副本比较）。命中即返回缓存行的拷贝 |
| D8 | `Markdown` 的尾块增量 | 现有 `_resume` 只在存在"已封口边界"时生效；新增：**唯一的尾部开放块**在追加时只重渲该块（前缀行缓存按源行范围切片）。命中路径的 `_stamp_tasks`/`_span_index` 随 (text, width) 缓存一起走，不再每帧全量重建 |
| D9 | 语法高亮 | `RegexHighlighter` 加按行记忆：`(行文本, 语言) → Line`；`highlight` 逐行查表。跨行状态本来就没有（模块 docstring 已声明），所以按行缓存是完备的 |
| D10 | 容器 | `Panel`/`Row`/`Column`/`Padding`/`Collapsible` 包装时只处理**子组件已产出的行**，并按 `(子行对象元组身份, 内宽)` 缓存包装结果；`child_at` 的既有缓存语义（`tests/test_container_hit.py:135/145`）不动 |
| D11 | compose 直通 | `frame.compose` 的 pass-through 判定放宽到"**未变的行**"（逐行复用上一帧的 `Line`/FrameSpan，不重建）；`splice_row` 在窗口=整行或裁剪为空时早退；`Chrome.paint` 的结果按 `(offset, total_rows, height)` 缓存。**输出字节必须逐字节不变** |
| D12 | framebench | 只加行不改行：W1 加 `text-open`（3000 行 OPEN `Text`，一次 `paint()`）与 `table-open`（240×6 `Table`，一次 `paint()`）——注意 W1 只交付 `text-open`，`table-open` 是 W2 的；W4 加 `stream-paragraph`（单段不断变长的 Markdown，每帧追加一行）。新基线写进 spec 与本 spec 的探针表；`render-hash` 不许动 |
| D13 | 测试预算 | 允许：更新被契约改动逼着改的既有用例（D1 波及 `tests/test_viewport.py`、`tests/test_selection.py:216` 附近、`tests/test_container_hit.py`）；每波新增 ≤ 4 条（各自的核心行为 + 那条 sealed hover 回归）。**不新建测试文件、不做参数矩阵** |

## 波次与阶段

| 阶段 | 波 | 分支 | 写者 | 写入范围 | 前置 |
|---|---|---|---|---|---|
| 1 | **W1** 行缓存内核 | `rc-w1-row-cache` | A | `kernel/block.py`、`kernel/viewport.py`、`kernel/lines.py`、`kernel/selection.py`、`app.py`、`interaction/search.py`、`interaction/gesture.py`、`widgets/button.py`、`widgets/checkbox.py`、`widgets/link.py`、`tools/framebench.py`、`tests/test_viewport.py`、`tests/test_selection.py`、`tests/test_block.py`、`tests/test_core_text.py` | 无 |
| 1 | **W3** compose 路径 | `rc-w3-compose` | C | `kernel/frame.py`、`chrome.py`、`tests/test_frame.py`、`tests/test_chrome.py`、`tests/test_painter.py` | 无 |
| 2 | **W2** Table 与编辑器 | `rc-w2-table-editor` | B | `widgets/table.py`、`widgets/field.py`、`widgets/textbuf.py`、`widgets/choice.py`、`widgets/radio.py`、`widgets/autocomplete.py`、`widgets/list.py`、`widgets/tree.py`、`tools/framebench.py`、`tests/test_widgets_*` | W1 合并 |
| 2 | **W4** Markdown 与容器 | `rc-w4-markdown` | D | `widgets/markdown/**`、`widgets/syntax.py`、`widgets/decor.py`、`widgets/layout.py`、`widgets/collapsible.py`、`tools/framebench.py`、`tests/test_widgets_markdown.py`、`tests/test_widgets_containers.py`、`tests/test_widgets_basics.py` | W1 合并 |
| 3 | **W5** 文档 | `rc-w5-docs` | E | `docs/DESIGN.md`、`docs/COMPONENTS.md`、`CHANGELOG.md`、`README.md`（按需） | W1–W4 合并 |

`tools/framebench.py` 是**三个波的共享文件**（W1/W2/W4 各加自己的行）：按上表顺序合并，
每波只在自己的区域追加（W1 的 `text-open`、W2 的 `table-open`、W4 的 `stream-paragraph`），
合并冲突由 lead 处理；agent 只写自己那一段，不重排其它行。

## 度量尺与预期（lead 已实测；各波必须复现并贴真实输出）

`ref/probe.py` 是期望值生成器（对着**当前分支**跑）。改前基线（main `dae2e7a`，我的机器）：

| 探针 | 改前 | 目标 |
|---|---|---|
| `Text` 3000 行 OPEN 的整帧 | **29.4 ms** | ≤ 1 ms（W1） |
| 同块 SEALED 的整帧 | 0.076 ms | 不变 |
| `Table` 60×6 / 240×6 OPEN 整帧 | 5.7 / 24.1 ms | ≤ 1 ms @60×6、≤ 2 ms @240×6（W2） |
| `Editor` 3000 行 render / `move_down` | 9.0 / 9.1 ms | 冷渲染 ≤ 12 ms、暖（同内容）≤ 1 ms、每键 ≤ 1 ms（W2） |
| `Markdown` 单段流式 200/400 次追加 | 304 ms / 2417 ms（二次） | 每帧近平（尾次 ≤ 1 ms @1000 行）（W4） |
| `Panel(Markdown 2000 行)` render | 35.4 ms | ≤ 2 ms（W4） |
| 挂 `Scrollbar` 的 sealed 帧 | 0.988 ms（无 chrome 0.073） | ≤ 0.2 ms（W3，即 ≤ 3× 无 chrome） |
| 1000 个 sealed 块的帧 | 0.474 ms | ≤ 0.1 ms（W1，`_prune_cache` 消失） |
| sealed `Button` hover 后屏幕 | **0 字节变化（bug）** | 有变化（W1） |
| `Markdown` 2000 行 render（命中） | 0.89 ms | ≤ 0.3 ms（W4） |

`framebench` 的既有四行（`stream-single`/`stream-split`/`scroll`/`scroll-long`）：
对应波次必须让**自己那一行**动（W3 动 `scroll`/`scroll-long`，W4 动 `stream-single`/`stream-split`，
W1/W2 动新加的行）；`render-hash` 与 `replay` 不许动。

## 回归红线

- 基线：`uv run pytest -q` → **1407 passed, 1 skipped**；`golden: 11 pages match`；
  `apidoc: API.md matches the facades (169 entries)`；`render-hash = de48e747…`。
- **渲染字节零变化**（除修 bug 的 hover 落屏）：golden 必须 `--check` 绿且**不重录**；
  `framebench` 的 `render-hash` 必须逐字不变。任何字节移动 = 停下来报告。
- `render(width)` 的三条不变量（幂等 / 有界 / 换宽度无漂移，`tests/test_render_invariants.py`）
  一条不改；`tests/test_viewport.py:175-196` 的调用计数断言不改。
- 主检出不许出现未提交改动；探针与临时脚本写 `%TEMP%`，不进 worktree、不进提交。

## 诚实出口

- 某波的记忆策略在验收数字上达不到目标：**停下来报告真实数字**，不许放宽 spec 里的目标、
  不许改探针、不许重录 golden。
- 发现"零字节变化"做不到（例如容器包装必须改输出才能省算）：停下来报告，lead 裁决。
- 越出写入范围（哪怕一行）→ 停下来报告，不越界自救。

## 报告格式（最终消息，中文）

工单状态表 / commit 清单（hash + message）/ 自测真实结论（命令 + 用例数 + 失败项）/
探针表（改前 vs 改后逐行）/ framebench 六行（+ 本章新加的行）/ 既有用例的搬迁清单（哪条、为什么）/
偏差与取舍 / 未决问题 / 真机手测：未执行。
