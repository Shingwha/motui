# Spec tui-depth · 总纲（协议层 / 行内动作 / 搜索 / 开发者基建 / 组件深化）

> 操作启动日 **2026-10-16**（组内 slug `tui-depth`，紧随 `base-components` 组之后）。
> 本组是 base-components 收口后的**第一轮纵深**：终端协议质量（同步输出/焦点事件/颜色降级/超链接/
> 标题与光标形状）、交互延续（行内可点 span、点击计数、Tooltip、搜索）、开发者基建（录制回放、
> 不变量测试、黄金帧、DevStats）、以及一批新老组件的补齐与增强。
>
> 上一组的成果是前提：`Hoverable`/`Container.child_at`/`descend`（W1）、`Pointer` tier 与 1003（W2）、
> `Palette`/`StatusLine` 下沉（W3）、64 名定稿（W4）、`examples/gallery`（W5）、无按键 motion 的
> wire 归一化（W5b）、基线注记与文档终稿（W6）。**本组不推翻它们；被取代的名字同波删除，零 shim。**
>
> Git / worktree 协议见 `spec-team` SKILL（worktree 放仓库外、分支从合并时刻最新 main 切出、
> agent 不 merge / push / tag、lead 统一创建与销毁）。本组不重复。

> **✅ 全组合并（2026-10-17 @ main）**。基线 `0d8bdc7`（两日窗口：启动 10-16，收口 10-17），合并记录：
> W1 `2925ef6`（`td1-protocol`）→ W2 `68eaa31`（`td2-inline`）→ W3 `a0a204c`（`td3-clicks`）→
> W4 `e8ad18c`（`td4-search`）→ W5 `acd7555`（`td5-tools`）→ W6 `160adc3`（`td6-widgets`）→
> W7 `4812897`（`td7-widgets-a`）→ W8 `5af421e`（`td8-widgets-b`）→ W9 `32a91bc`（`td9-final`）。
> 分支全部保留、worktree 已清。
>
> **门禁终态（main 实测）**：`pytest` **1473 passed / 1 skipped**（基线 985）；`demo.py < /dev/null`
> exit 0 且 dump 与 W2 基线逐字节一致；`--pages` **14 页**；`NO_COLOR=1 --pages` exit 0；
> `golden --check` **14 pages match**；`apidoc --check` **199 entries**；`import mocode_tui` 干净
> （root **73** 名）；README 代码块 10 passed；`render-hash` = `de48e747…5122`（W1 因 2026 包裹重录，
> W2 起未变，注记在 `tools/framebench.py`）。
>
> **本组期间的追加修复（如实登记）**：W5 的 fuzz 基建揪出一个既有真机级 bug（bracketed paste 结束
> 标记跨 feed 拆分被吞进内容），lead 批准后同波修复（`84df7f7`，strict xfail 折回全矩阵等价性测试）；
> 同波补了两处宿主光标形状缝（find / palette 的查询行，`b721f28`/`8553bbc`）。
> 首次 CI（`.github/workflows/ci.yml`）尚未在 GitHub 上真实运行过——本环境无网络，留待首次 push 时闭环。

## 目标与范围

1. **协议层补齐**：DECSET 2026 同步输出、DECSET 1004 焦点事件、颜色能力探测与降级
   （`truecolor/256/16/none`）、OSC 8 超链接、OSC 2 窗口标题、DECSCUSR 光标形状；VT 侧补
   CSI 修饰参数（shift+方向）。
2. **行内可点 span**：`Segment` 长出 `link`/`action` 载荷；`Text`/`Markdown` 成为
   `Clickable + Hoverable(+hover_at)`，链接既是 OSC 8 真超链接也是应用内可点动作（`chosen` 读一次）。
3. **点击与提示**：双击选词、三击选行；`Pointer` 用 `name` 消歧拖拽与悬停；`chrome.Tooltip` 提示条。
4. **搜索**：新 assembly tier `Find`（自带查询行、overlay 高亮、`enter/↑↓/Esc`、reveal 当前匹配），
   `Viewport.scroll_to` / `TUI.reveal` 作为通用「滚到指定块行」能力。
5. **开发者基建**：`KeySource` 级录制/回放（真机事件流 → 仓库回归）、解码器 fuzz 与布局不变量、
   gallery 黄金帧工具、`chrome.Stats` DevStats overlay 与 `devtools` 页。
6. **组件补齐**：`Radio`/`Slider`/`Collapsible`/`ShortcutBar`；`TextBuffer` 的 undo/redo 与文本内选择
   （Editor/Input 的 shift+方向）；`Diff`、`List`（窗口化大列表）；`Table`/`Tree`/`Markdown` 增强；
   grapheme 边角（组合附标/VS/ZWJ/RI 对）。
7. **工程收口**：CI（ubuntu+windows）、发布 workflow（tag 触发、不执行）、`tools/apidoc.py` →
   `docs/API.md` 漂移测试、全组终稿与手测清单。

**范围**：`src/mocode_tui/**`、`tests/**`、`examples/**`、`docs/*.md`、`README.md`、`tools/**`、
`.github/workflows/**`（新增）。**不加运行时依赖**（仍只有 wcwidth）；不引网络/模型。

## 现状（侦察核实，写 spec 的事实底座）

| 事实 | 锚点 |
|---|---|
| 帧字节唯一出口：`Painter.paint` 一次 `join(writes)` + `flush`；未变化帧零字节 | `core/painter.py:84-115`、`:106`；`docs/DESIGN.md:382` |
| 样式→SGR 在 `Style.prefix()`（带实例缓存）与 `Line.styled()`（每 Line 一次） | `core/style.py:138-151`、`core/lines.py:140-165` |
| `Style` 颜色形态：名字 / `#rrggbb` / `(r,g,b)`；**无任何降级逻辑** | `core/style.py:35-108` |
| `Segment` frozen，只有 `text/style`（+ 派生 `_width`）；`Line` 不可变；`Text` 无几何缓存 | `core/lines.py:63-96`、`:258-293` |
| Markdown 链接 URL 被丢弃（只留 label），测试锁死 | `widgets/markdown/inline.py:162-176`；`tests/test_widgets_markdown.py:168,206` |
| 双击选中已存在（`_word_select`），三击无；console 的 double-click flag 故意忽略 | `gesture.py:240-260,292`；`keys/console.py:86-87`；`tests/test_gesture.py:657` |
| `Pointer.handle` 的 motion 分支只看 `button != 0`，`name` 不参与 | `pointer.py:150-157` |
| `Viewport` 只有 `scroll_up/down/to_bottom`，**无 scroll_to** | `core/viewport.py:267-289` |
| 编辑键表无 shift/undo/redo；decoder 丢弃修饰位（CSR 参数不支持） | `keys/keymap.py:54-82`；`keys/decoder.py:315-316` |
| `TextBuffer` 五个写点：insert/backspace/delete/newline/clear | `widgets/textbuf.py:143-203` |
| 输入源两只：`RawTerminalKeys` 字节路径与 console 记录路径，feed 分散（sources.py:305 + console.py:305+） | `keys/sources.py:274-306`、`keys/console.py:298-311` |
| `framebench.hash_workload` = paint 进 `HeadlessScreen.output` 的 sha256（含两个 Markdown） | `tools/framebench.py:139-157` |
| 全仓无 CI、无文档生成、无 hypothesis、dev 依赖只有 pytest 三件套 | `pyproject.toml:14-27`；根目录无 `.github/` |
| 字节级 pin 面（改动必触） | `tests/test_painter.py:36-37,51-52,85,140-142,174`、`test_screen.py:60-119,157-172`、`test_ansi.py:30-93`、`test_style.py:33-58`、`test_core_text.py:199-290`、`test_widgets_containers.py:224-233`、`test_api_root.py:16-104` |

## 本组宪法（在上一组交互宪法之上追加）

```
1. 组件保持「状态 + 控制器方法」；宿主读状态（chosen/query/index），无回调、无事件总线。  （沿用）
2. 协议字节只从 core/ansi.py 构造；能力开关在 screen/TUI 构造参数，默认不改变现状。      （新增）
3. Segment 是唯一行内载荷位：link（参与相等性，影响字节）、action（compare=False，纯元数据）。
   组件的行内命中一律读「上次 render 的行表」——与 Container.child_at 同先例。            （新增）
4. 缓存对能力冻结：Style.prefix()/Line.styled() 的缓存不得与终端能力相关；降级/包裹字节
   只能发生在 painter 的取字节路径（truecolor 默认路径继续走缓存，字节不变）。              （新增）
5. 新开关默认关或维持现状；「默认路径字节逐字节一致」是每波验收的硬项（除非该波写明重录）。  （沿用）
6. 文档与测试同波：README 表、COMPONENTS 协议/组件表、DESIGN 命名表与叙事段、facade docstring、
   test_api_root 的 pin——新增公开名当场同步。                                            （沿用）
```

## 决策登记（拍板，不再反复）

- **D1 同步输出（2026）默认开**：并入 `Painter` 那一次 `join` 的前后包裹；空帧（零 writes）仍零字节。
  `framebench` 基线**本组 W1 有意重录一次**（包帧字节改变 render-hash），W1 注记写明原因；此后各波不动。
- **D2 焦点事件（1004）默认关**：`TerminalScreen/HeadlessScreen(focus=False)` / `TUI(focus=False)`；
  decoder 把 `ESC[I`/`ESC[O` 解成 `Key("focus_in")`/`Key("focus_out")`。**Pointer 仍只看鼠标**；
  清理与暂停由宿主做（gallery 在 `focus_out` 调 `pointer.clear()`）。
- **D3 颜色模式**：`ColorMode = "truecolor" | "256" | "16" | "none"`。
  探测（`detect_color_mode(env)`）：`NO_COLOR` 存在或 `TERM=dumb` → `none`；`COLORTERM` ∈ {truecolor,24bit}
  → `truecolor`；`TERM` 含 `256color` → `256`；其余**保持现状**（`truecolor`）。
  `TerminalScreen(color_mode="auto")` 默认按环境探测；`HeadlessScreen(color_mode="truecolor")` 默认确定值；
  `TUI(color_mode=None)` 透传。降级是纯函数（`core/style.py`：`quantize`/`sgr_prefix(style, mode)`），
  只在 painter 的取字节路径应用：`mode=="truecolor"` 走 `Line.styled()`（缓存，字节不变），
  其余走新的纯函数 `lines.styled_with(line, mode)`（不缓存）。`"none"` 去色保属性。
- **D4 OSC 8 无开关**：`Segment.link` 有值时 `Line.styled()` 在该段外包裹 `ESC]8;;URL BEL`…`ESC]8;; BEL`
  （不支持的终端忽略未知 OSC，无害）。`link` 参与相等性（链接变了要重画）；`action` 是 `compare=False`。
- **D5 标题与光标形状**：`ansi.set_window_title(text)`（清洗控制字符）、`ansi.cursor_shape(shape)`
  （block/beam/underline/default → DECSCUSR 2/6/4/0）；`TUI.set_title()` / `TUI.set_cursor_shape()`。
  光标形状由宿主从聚焦叶子读（`getattr(leaf, "cursor_shape", "block")`），库不建新协议。
- **D6 行内动作**：`Segment.action: str | None`；`lines.action_at(line, col)` 纯函数（走段宽累加）。
  `Text`/`Markdown` 实现 `Clickable + Hoverable + hover_at`：`click(row,col)` 命中带 action 的段才置
  `chosen = action` 并返回 True；`hover` 段级 `merge(theme.hover)`（Markdown 用「缓存基行 + 后变换」，
  缓存键仍是 `(text,width)`）；**不新增回调**。Markdown 链接同时得 `link=url, action=url`。
- **D7 点击计数**：双击（既有词选）与三击（行选）都在 `SelectionGesture` 内用 `clock()` 计数；
  console 的 double-click flag 继续忽略（两下按键由 gesture 合并）。三击从「out of scope」转正。
- **D8 Pointer 消歧**：motion 报告 `name ∈ {left,middle,right}`（按住键）**或** `button != 0` → 拖拽分支
  （清待定、不动 hover）；否则（`name=="none"` 或合成事件）→ hover 分支。解 W5b 未决 #1。
- **D9 Tooltip**：`chrome.Tooltip(tui, pointer, *, theme=None)` 读叶子 `hint` 属性（getattr，str），
  在指针附近画单行提示（clamp 进 frame），宿主显式挂载/卸载。
- **D10 搜索**：新 assembly tier `mocode_tui/search.py` 的 `Find`：自带 `Input` 查询行、
  `matches`（块地址 + 列区间）、`index`、`is_open`；`enter`/`down` → 下一个、`up` → 上一个、
  `escape` → 关闭；overlay 高亮全部匹配、当前匹配用 `theme.selection` 加重；用新的
  `Viewport.scroll_to(offset)` / `TUI.reveal(bid, row)` 揭示当前匹配。**无 chosen**（持续态）。
- **D11 录制回放**：`KeySource` 装饰器（事件级，非字节级——Windows console 路径无统一字节缝）：
  `RecordingKeys(source, path)` 包真源写 JSONL（`{"ms":…, "event":…}`），`ReplayKeys(path, speed=1.0)`
  （`speed=0` 零 sleep，测试与回放用）；事件序列化含 `Key/Paste/MouseEvent` 三型，stdlib only。
- **D12 不变量与 fuzz**：无新依赖，用 `random.Random(seed)` 的确定性字节流喂 `KeyDecoder`
  （断言 total/不抛/pending 有界）+ 组件渲染不变量（`render(w)` 幂等、行宽 == w、`fit` 后不溢出）。
- **D13 黄金帧**：`tools/golden.py`（`--update` 写入 / `--check` 比对）把 gallery 全部页面渲染到
  `tests/golden/pages/<page>.txt`；`tests/test_golden_frames.py` 逐字节比对。新增页的波随波重录。
- **D14 DevStats**：`chrome.Stats` overlay：帧计数/帧间隔、事件计数、最近键名、hover 叶子与命中单元；
  数据全用既有字段（`painter.frames`、`tui.clock()`、pointer 的 `position/hovered`），不新增计时机制；
  gallery `c-g` 开关 + 新 `devtools` 页。
- **D15 组件基础**：`Radio`（组内单选，`chosen` = 选中项 label/value）、`Slider`（数值，←→/点击，
  `min/max/step`，`chosen`）、`Collapsible`（标题行可点/可聚焦，`open` 状态，`chosen` 回声）、
  `ShortcutBar`（`(key, label)` 列表单行渲染）；`TextBuffer` 加**有界 undo/redo**（五写点全过账）与
  **文本内选择**（`s-left/s-right/s-home/s-end/c-a` 扩展，选中即替换，`selected_text`/`clear_selection`），
  `DEFAULT_INPUT_KEYMAP`/`EDITOR_SUBMIT_KEYMAP` 同步。
- **D16 CSI 修饰参数**：decoder 支持 `ESC[1;2X` 家族（X∈{A,B,C,D,H,F}）→ `Key("s-up"/"s-down"/…"s-home"/"s-end")`；
  其余修饰组合与无参形态维持现状（`s-` 前缀与 `c-` 风格一致）。
- **D17 组件进阶**：`Diff(before, after)`（行级 LCS，`+/-/ ` 前缀与 `success/error/dim` 底纹，
  `chosen` 不用，纯展示 + 可滚动）；`List(items, *, window=…)`（窗口化渲染大列表：只渲染可见行；
  cursor/`chosen`/`hover_at`/前缀跳转）；grapheme 边角（组合附标/VS/ZWJ 零宽、RI 对成旗，`core/text.py` 纯函数）；
  `Table.sort_by(col)`、`Table.set_widths()`、`Table.header_line(width)`（sticky header 的 recipe 形态）；
  `Tree.filter(query)` + 前缀跳转；Markdown 任务列表（`[ ]/[x]` → 可点 span，`chosen = "todo:<i>"`）+
  `Markdown.fences()` 访问器（gallery `c-y` 复制代码块）。
- **D18 工程收口**：CI workflow（ubuntu+windows、uv、`pytest -q` + framebench + golden check）、
  发布 workflow（tag 触发，本组只写不跑）、`tools/apidoc.py` 生成 `docs/API.md` + 漂移测试（重生成比对）。

## 波次表（严格串行；每波一个 agent，合并后再派下一个）

| W | 分支 | 交付 | 前置 | `--pages` 页数 |
|---|---|---|---|---|
| W1 | `td1-protocol` | 2026 同步输出 / 1004 焦点 / 颜色降级 / OSC 8 载体 / 标题与光标形状 / CSI 修饰 | — | 12 |
| W2 | `td2-inline` | `Segment.link/action` + `Text`/`Markdown` 行内可点 + gallery 链接回声 | W1 | 12 |
| W3 | `td3-clicks` | 双击/三击、Pointer 消歧、`chrome.Tooltip` | W2 | 12 |
| W4 | `td4-search` | `Find` tier + overlay + `scroll_to/reveal` + gallery `c-f` | W3 | 12 |
| W5 | `td5-tools` | 录制/回放、fuzz/不变量、黄金帧工具、`chrome.Stats` + `devtools` 页 | W4 | 13 |
| W6 | `td6-widgets` | `Radio`/`Slider`/`Collapsible`/`ShortcutBar`、`TextBuffer` undo+选择 | W5 | 13 |
| W7 | `td7-widgets-a` | `Diff`、`List`、grapheme 边角 | W6 | 14 |
| W8 | `td8-widgets-b` | `Table`/`Tree`/`Markdown` 增强 | W7 | 14 |
| W9 | `td9-final` | CI / 发布 workflow / apidoc+漂移测试 / 终稿与手测清单 | W8 | 14 |

> 调度顺序 = 表序，严格串行。每波自带「文档同步 + 测试覆盖自己新增内容 + 门禁真实输出」。
> render-hash 在 **W1**（2026 包裹字节）与 **W2**（链接的 OSC 8 字节）各有意重录一次，
> 两波都更新 `tools/framebench.py` 的基线注记；此后各波若变化必须写明原因。

## 全局不变量（每波每 commit 都不得违反）

1. **无回调 / 无事件总线 / 无全局单例**：宿主读状态；`on_end` 式「构造默认参数」是唯一豁免形态。
2. **一概念一名**：被取代的名字同波删除；失败即全仓 grep 零残留（含 docstring/文档表/示例/测试）。
3. **kernel 纯净**：`core` 只加无策略的协议、纯函数与字节（`ColorMode`/`quantize`/`styled_with`/
   `action_at`/grapheme 边角）；策略留 assembly tier（`pointer.py`/`gesture.py`/`search.py`/`chrome.py`）。
4. **默认路径零变化**：每波验收含「默认参数下既有字节 pin 不红」；例外（W1 的 2026 包裹）写明并重录基线。
5. **测试与文档同波**；新增公开名当波同步 `test_api_root` 的 pin 与排序。
6. **命名与语言**：代码注释/docstring 英文，spec 中文；commit `type(scope): 小写短句 -- 第二句`，
   单行、无句号。
7. **门禁不破**（见下）。

## 门禁（每波合并前、合并后各跑一次，贴真实输出）

```bash
uv run pytest -q                                            # 只增不减（工单写明例外）
uv run python examples/demo.py < /dev/null; echo exit=$?    # exit 0
uv run python examples/demo.py --pages                      # exit 0；页头数 = 波次表
uv run python tools/framebench.py                           # render-hash：W1 重录后各波应不动
uv run python -c "import mocode_tui"                        # exit 0
uv run pytest tests/test_readme_examples.py -q              # README 代码块
NO_COLOR=1 uv run python examples/demo.py --pages           # W1 后：exit 0（无颜色路径）
uv run python tools/golden.py --check                       # W5 后：逐页一致
```

harness 事实（agent 必读）：OS = win32（Git Bash），Python 3.12+，`uv run` 唯一入口；
无网络、无浏览器、**无真实终端**——协议字节用 `HeadlessScreen.output` 断言，交互用
`ScriptedKeys + HeadlessScreen`，**库与测试零 sleep**（`ReplayKeys(speed=0)` 即此契约）；
`HeadlessScreen.output` 是 **str**（不是 bytes）。

## 范围外（明确不做，附未来形状）

- **终端查询应答替身（DA/DSR/OSC 11）**：本组能力探测走 env（D3），无查询协议消费者，不做。
- **文档级键盘选择**：文档没有 caret 模型（选择是鼠标地址）；键盘选择只落 Editor/Input（D15）。
- **Tree 懒加载**：需要数据源协议（回调形状），违背宪法；宿主重建树即可。
- **Kitty keyboard protocol**：支持面与收益不匹配，维持现状。
- **bidi / .gitattributes 换行规整**：不做；换行规整会动全树，另案。
- **真模型接入 / 内建完整 app 外壳**：沿用上一组决定。

## 交付后手测清单（终稿，真机，lead 终验用）

> 前置：真实终端，全程 `uv run python examples/demo.py`。按序执行、逐条核对预期；第 12 条可先跑。

1. **颜色升降级**：`COLORTERM=truecolor`（真彩）/ `TERM=xterm-256color`（256 降级）/ `TERM=xterm`（16 色）/
   `NO_COLOR=1`（无色保属性）四档都要能开；`/styles` 四档下不错色、不乱码，可读性递降但不崩。
2. **2026 无闪烁**：真机滚 `/content`（长页）与 `/streaming` 播放，整帧替换、无撕裂/闪烁；每帧被
   `ESC[?2026h`/`2026l` 夹住，空帧仍零字节（可对 `demo.py < /dev/null` 的字节）。
3. **焦点事件清理**：切走窗口（1004 的 `ESC[O`）→ hover 与 tooltip 清除；回来移动一格即恢复；
   窗口标题随页面切换（OSC 2）；输入聚焦时光标变 beam、失焦回 block（DECSCUSR）；悬停带 `hint`
   的叶子弹 `Tooltip` 一行、移开即撤。
4. **OSC 8 链接**：`/content` 链接带下划线/悬停高亮、终端原生 cmd/ctrl+click 可开 URL；
   应用内点击 → 页内回声 + toast。
5. **点击计数与拖拽消歧**：双击选词、三击选整行、第四击重开；按住左键拖动时 hover 不跟随；
   松手经 OSC 52 复制（支持的终端粘贴验证）；空白处三击也选中整行。
6. **搜索**：`c-f` 输入过滤、高亮全部、当前加重、回车/↓ 下一个、↑ 上一个、自动滚到可见、Esc 关闭；
   打开时按键归查询行（输入 `q` 只搜索不退出），行内光标为 beam。
7. **录制/回放**：按 README 配方 `RecordingKeys(RawTerminalKeys(hover=True), "session.jsonl")` 录一段
   （含鼠标与粘贴）；文件应为逐行 JSONL；`ReplayKeys(..., speed=0)` 回放行为一致；坏行报带行号
   ValueError。
8. **DevStats**：`c-g` 挂/撤 `chrome.Stats`——帧数/帧率、事件计数、最近键名、hover 叶子与命中单元
   实时更新；`/devtools` 页可读可交互。
9. **四个新组件**：`/choice` Radio（↑↓/点击单选）、`/data` Slider（←→ 步进/点轨道/enter 确认）、
   `/structure` Collapsible（enter 折叠、标题行可点）、footer ShortcutBar（窄宽就地截断、不参与焦点）。
10. **Diff / List / Tree / Table / Markdown 增强**：`/diff` 的 `+/-/空格` 前缀与底纹、可滚动；
    `/data` List 的窗口计数行、enter 取用、前缀跳转；`/navigation` Tree 的 `c-t` 过滤与前缀跳转
    （命中链自动展开、不写回 flags）；`/data` Table 的 `sort_by` 与 sticky header 配方。
11. **undo / 选择 / 任务框 / `c-y`**：`/input` 的 `c-z`/`c-y`（单字符连续输入合并一步）、`c-a` 全选、
    shift+方向扩展、打印/粘贴替换选中、移动清选择；Markdown 任务框可点（`chosen="todo:<i>"`）；
    `c-y` 复制代码块（OSC 52 落地率因终端而异）。
12. **无终端三路**（可先跑）：`demo.py < /dev/null` exit 0、`--pages` 14 页头、`NO_COLOR=1 --pages`
    exit 0；另跑全门禁九条 + `golden --check` + `apidoc --check`。
