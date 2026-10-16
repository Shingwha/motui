# Spec base-components · 总纲（基础组件收口：hover / 可组合交互 / 删 chat / demo 重做）

> 操作启动日 **2026-10-16**（组内 slug `base-components`）。
> 本组是**一次库的减法 + 交互层的加法**：删掉 agent 专属展示层（`chat/`），把它的通用件
> 下沉到 `widgets/`；同时把「可点击 / 可 hover / 可组合」从各自为政的补丁收成一组**正交协议**，
> 并据此**整体重做展示台**——画廊里不再有常驻输入框，组件目录与「完整 app 外壳」物理隔离。
>
> 本组**不做向后兼容**：被取代的名字、模块、别名**同波删除**，全仓 grep 零残留
> （`docs/DESIGN.md` 的「no shim / no alias / no deprecation」契约，本组贯彻到底）。
>
> Git / worktree 协议见 `spec-team` SKILL（worktree 放仓库外、分支从合并时刻最新 main 切出、
> agent 不 merge / push / tag、lead 统一创建与销毁）。本组不重复。

> **✅ 全组合并（2026-10-16 @ main）**。基线 `6043db8`，合并记录：
> W1 `78fef97`（`bc1-kernel`）→ W2 `b7089b5`（`bc2-pointer`）→ W3 `499365c`（`bc3-salvage`）→
> W4 `45c751c`（`bc4-closeout`）→ W5 `32248e1`（`bc5-demo`）→ **W5b `a9b042e`（`bc5b-motion`，
> lead 授权追加波，见 `07-w5b-motion-decode.md`）** → W6 `40a0ffb`（`bc6-final`）；
> lead 收尾小修 `3184de1`（gallery `c-o` 清 hover）、`4fd9720`（pyproject 过时描述）。
> 分支全部保留、worktree 已清；门禁终态：`pytest` 985 passed / 1 skipped，demo piped 与 `--pages`
> 均 exit 0（12 页），`render-hash` 与基线逐字符一致（`5bcfdf16…aba9a`，原因见 `tools/framebench.py` 注记）。
>
> **W5b 的由来（前提修正，如实登记）**：总纲「现状」第 1 条原断言「decoder 已能把无按键 motion
> 解码出来」——lead 复核源码为**假**：SGR-1006 的无按键 motion 是低位 3（报文 35），decoder 直接
> 丢弃，console 记录桥也只合成按住键的 motion，hover 在任何真机上收不到 motion。W5b 把 wire 归一化
> 为 `MouseEvent("none", button=0, kind="motion")`（VT 解码器 + console 桥 hover 门控），
> 默认路径零行为变化。

## 目标与范围

1. **交互和渲染一样正交、可组合**：渲染仍只有 `render(width)` 一个协议；交互由一组并列协议表达——
   `Clickable` / `Activable` / `Focusable` / **新 `Hoverable`** / **新容器下钻 `Container.child_at`**。
   包装器（`Row` / `Column` / `Padding` / `Panel`）对交互**透明**。
2. **hover 落地**：由新的 `Pointer` tier 统一做「指针 → 命中 → 下钻 → 翻 hover」，组件只需声明
   `hover` 状态并按它渲染。hover 需要 DECSET 1003，**默认关，按需开**（见 D2）。
3. **库瘦身**：删除 `src/mocode_tui/chat/`；通用件 `StatusLine` / `SlashPalette` 下沉 `widgets/`，
   其余删除。新增最小交互原语 `Button` / `Checkbox` / `Link`。
4. **demo 不混杂**：重建为**一个画廊**，页面上**没有常驻输入框**；`/` 只开一个模态 `Palette`
   overlay（选完即关）。不再有「完整 app 外壳」模式——那正是要删除的混杂源。
5. **工程性照旧**：piped 回放与 `--pages` dump 仍是门禁级契约；`render-hash` 变化要重录基线并说明。

**范围**：`src/mocode_tui/**`、`tests/**`、`examples/**`、`docs/*.md`、`README.md`、`tools/framebench.py`。
不加依赖、不引网络/模型。

## 现状与问题清单（全部已核对源码）

1. **没有 hover 抽象**。decoder 会把 `kind="motion"`、低两位无按键的报解码出来
   （`keys/decoder.py:337`），但 `core/block.py` 只有 `Focusable`，`Theme` 没有 hover 样式，
   `focus.py` 明确写「no hover」。组件无法表达「鼠标在我上面」。
2. **容器吞交互**。`Row` / `Column` / `Padding` / `Panel` / `Spacer`（`widgets/layout.py`、
   `widgets/decor.py`）只有 `render`，不转发 `click` / `handle` / `focused`。
   于是 `Padding(Button())` 命中到 `Padding`、点击丢失；`FocusRing([Padding(Editor())])` 构造即 `TypeError`；
   一个 block 里 `Column([Select, Tree])` 无法区分点到谁。**包装/组合会杀死交互**。
3. **dispatch 全是宿主样板**。`examples/showcase/session.py:262` 的 `_page_click` 用 ~60 行手写
   press/motion/release 静止判定、再手工走 focus/activate。
4. **chat 层混装**。`chat/` 里既有 agent 专属展示（`Message` / `ToolBlock` / `EditBlock`），
   也有通用件（`StatusLine` 两侧对齐行、`SlashPalette` 命令面板）与通用控制器
   （`Composer` / `Transcript` / `StreamHandle`）。整包删除会连通用能力一起丢。
5. **demo 混杂**。常驻 `Composer`（聊天输入框）出现在每一个组件展示页上；`session.py` 935 行把
   shell + 页面 + 聊天 + 预览 pane + workspace 揉在一起；`script.py` 用硬编码屏幕坐标回放，极脆。
6. **缺少最小交互原语**。有 `Select` / `Input` / `Editor` / `Table` / `Tree` / `Tabs`，
   但没有 `Button` / `Checkbox` / `Link` 这类「最小可点单元」。

## 交互宪法（本组定稿，全部波次遵守）

```
1. 命中   Clickable.click(row, col) -> bool          （不变；坐标是块内 cell）
2. 激活   Activable.activate() -> bool               （不变；结果进 chosen，宿主读一次）
3. 焦点   Focusable.focused: bool + FocusRing        （不变）
4. HOVER  Hoverable.hover: bool（组件级）
          可选 Hoverable.hover_at(row, col) -> bool（行/格级；row < 0 表示指针离开）
          Pointer 负责命中→下钻→翻状态，组件只按 hover 渲染
5. 下钻   Container.child_at(row, col) -> (Component, row, col) | None
          容器用自己的几何把坐标翻译成「子组件 + 子坐标」；纯函数 descend() 递归到最深的组件
```

**边界**：不做回调 / 事件总线 / 全局单例（沿用 interaction-model 全局不变量 1）；
hover 默认关、按需开（D2）；容器只做下钻，不做「代理 `handle`/`move`/`activate`」（注册叶子，见 D4）。

## 决策登记（拍板，不再反复）

- **D1 无回调，`chosen` 仍是唯一通道**。新原语 `Button` / `Checkbox` / `Link` 也遵守
  「组件存状态、宿主读状态」：`activate()` / `click()` 把结果写进 `chosen`，宿主读一次清一次。
  不新增回调字段。
- **D2 hover 走 DECSET 1003，默认关**。1002 只在按住键时报 motion，真正的「无按键悬停」需要 1003
  （any-event tracking）。**这推翻 interaction-model 的 D5**（当时因事件风暴不做 hover）。
  缓解：`1003` 只在 `TUI(hover=True)` 时开启（`TerminalScreen(hover=...)` / `TUI(..., hover=...)`），
  默认仍是 1000+1002+1006；`Pointer` 只在**悬停目标变化**时 `invalidate()`，保住「无变化零字节」。
  事件风暴的代价是「每跨一格一次 `hit_test`」，不是「一次重绘」；真机代价由 lead 手测记录。
- **D3 hover 协议两个缝**。组件级 `Hoverable.hover: bool`（`Focusable` 的对称物）；行/格级可选
  `hover_at(row, col) -> bool`（`Select` / `Autocomplete` / `Confirm` / `Tabs` / `Tree` / `Table`
  实现它高亮指针下的行/标签）。`row < 0` 表示指针离开（清 hover）。`Pointer` 进入/移动时调
  `hover = True` + `hover_at(row, col)`，离开时调 `hover = False` + `hover_at(-1, -1)`。
- **D4 容器只下钻，不代理**。`Container.child_at` 读**上一次 render 缓存的几何**（与
  `TextBuffer.move_up` 读上次 render 的换行几何同一先例）。`Pointer` 与 `FocusRing.click` 都先
  `descend()` 再派发；容器**不**代理 `handle`/`move`/`activate`/`focused`——键盘焦点注册**叶子**。
- **D5 chat 拆解**：`StatusLine` 迁 `widgets/statusline.py`；`SlashPalette` 升级为
  **自带查询输入行的 `Palette`**（`widgets/palette.py`，组合 `Input` + `Autocomplete`），
  这样画廊不需要常驻 editor；`Message` / `ToolBlock` / `EditBlock` / `Composer` / `Transcript` /
  `StreamHandle` 删除（demo 需要就地重建）。`tui.add_band` / `Viewport` 保留为通用能力。
- **D6 Theme 收敛**：新增 `hover: Style = Style(reverse=True)`；删除只服务已删组件的
  `user_bg` / `tool_bg` / `code_bg` 与派生表 `tones` / `title_tones`。保留 `headings` /
  `notice_levels` / `scrollbar` / `scrollbar_thumb` / `toast` / `table_border` / `first_column`。
- **D7 demo 单画廊**：`demo.py` = 交互画廊（无常驻输入框，`/` 开模态 `Palette` overlay）；
  三条入口路径 `interactive` / `--pages` / piped 回放。**不设 `--app`**：用基础组件自举的完整外壳
  会重新引入常驻输入框、并逼我们在 demo 里重建刚删掉的 `Composer`/`Transcript`——即双份漂移。
  「如何组装 app」作为**文档配方**（`docs/COMPONENTS.md`），未来若要参考实现另立独立示例。
- **D8 命名**：`COMPOSER_KEYMAP` → **`EDITOR_SUBMIT_KEYMAP`**（editor 表去掉 `enter`，宿主拿 submit
  的通用表）；旧名同波删除，无 alias。
- **D9 新原语**：`Button`（`Hoverable + Clickable + Focusable + Activable`）、
  `Checkbox`（同上，`activate()` 翻转）、`Link`（`Hoverable + Clickable`）。
- **D10 不做**：回调/事件总线/全局焦点单例；容器代理键盘事件；`Text` 内联可点 span（Link 组件先顶上）；
  hover 的「离开窗口」边角（切 pane/窗口 resize 时的 hover 清理属最佳努力）。

## 波次表（严格串行；每波一个 agent，合并后再派下一个）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | 交互内核：`Hoverable` / `Container.child_at` / `descend` / `Theme.hover` + 容器几何缓存 + 单测 | `core/block.py` `core/theme.py` `core/__init__.py` `widgets/{layout,decor}.py` `tests/test_container_hit.py` | — |
| W2 | `Pointer` tier + 1003 开关 + `TUI.hit_component` + `Button`/`Checkbox`/`Link` + 既有组件 `hover_at` + 单测 | `pointer.py`(新) `app.py` `core/{ansi,screen}.py` `widgets/{button,checkbox,link}.py`(新) `widgets/{choice,tabs,tree,table,field}.py` `__init__.py` `tests/test_pointer.py` `tests/test_widgets_action.py` | W1 |
| W3 | chat 拆解：迁 `StatusLine`、升 `Palette`、删 `chat/`、keymap 改名、Theme 收敛、facade/doc 引用清理 | `widgets/statusline.py`(新) `widgets/palette.py`(新) 删 `chat/**` `keys/keymap.py` `keys/__init__.py` `core/theme.py` `widgets/__init__.py` `__init__.py` `gesture.py` `tests/**` | W2 |
| W4 | 库收口：root/facade 导出定稿、`test_api_root` 重 pin、theme/basics/readme 测试更新、DESIGN/COMPONENTS 更新 | `__init__.py` `test_api_root.py` `test_theme.py` `test_widgets_basics.py` `test_readme_examples.py` `docs/{DESIGN,COMPONENTS}.md` `README.md` | W3 |
| W5 | demo 重做：删 `examples/showcase/`，新 `examples/gallery/`（单画廊、无常驻输入框、`/` 模态面板）+ 瘦身回放 | `examples/demo.py` `examples/gallery/**`(新) 删 `examples/showcase/**` `README.md` demo 段 | W4 |
| W6 | 收尾：`framebench` render-hash 新基线 + README/docs 终稿 + 真机手测清单 | `tools/framebench.py` `README.md` `docs/**` `specs/**` 状态 | W5 |

> 调度顺序 = 表序，严格串行（W1→W6；W3 大面积删改、W5 大面积新增，无并行空间）。
> 每波自带「文档同步 + 回放/探针覆盖自己新增内容 + 门禁真实输出」。
> **追加波 W5b**（lead 授权，位于 W5 与 W6 之间）：无按键 motion 的 wire 解码修复，
> 见 `07-w5b-motion-decode.md`；W6 的门禁与文档终稿在 W5b 之后执行。

## 全局不变量（每波每 commit 都不得违反）

1. **组件保持纯渲染 + 状态**：`render(width)` 唯一渲染协议；交互 = 组件持有状态 + 控制器方法
   （`handle`/`move`/`click`/`activate`/`select`/`hover`/`hover_at`），**宿主路由事件**。
   不引入回调字段、事件总线、全局焦点单例、`async` 组件。
2. **一概念一名**：被取代的名字（`COMPOSER_KEYMAP`、`focus.py` 里对 chat 的引用等）在同一 commit
   删除，全仓 grep 零残留（含 docstring、文档表格、示例、测试）。
3. **kernel 纯净**：hover/点击/焦点策略留在 assembly tier（`focus.py` / `pointer.py` / `gesture.py`）；
   `core` 只加**无策略**的协议与纯函数（`Hoverable` / `Container` / `descend` / `Theme.hover` / 1003 字节）。
4. **行为变化要登记**：任何改变渲染字节或宿主可见行为的工单，须写明「改前 → 改后」与 A/B 证据；
   `render-hash` 故意变化时记录新基线并说明原因。
5. **测试与文档同波**：README 被 `tests/test_readme_examples.py` 执行的代码块、`docs/COMPONENTS.md`
   的组件表/交互表、`docs/DESIGN.md` 的命名表与 hover 节，必须与代码同波更新。
6. **命名与语言**：代码注释/docstring 英文，spec 中文；commit 风格
   `type(scope): 小写短句 -- 第二句`，单行、无句号。
7. **门禁不破**：`pytest`（只增不减，除非工单写明删了什么）、`examples/demo.py < /dev/null` exit 0、
   `--pages` 页头数 = 页表长度、`import mocode_tui` 干净、README 代码块通过。

## 门禁（每波合并前、合并后各跑一次，贴真实输出）

```bash
uv run pytest -q                                            # 基线以 main 实测为准；本组允许总数变化，工单写明
uv run python examples/demo.py < /dev/null; echo exit=$?    # exit=0（W5 前是旧 demo；W5 后是新 gallery）
uv run python examples/demo.py --pages                      # exit=0；页头数 = 页表长度
uv run python tools/framebench.py                           # W5 前 hash 必须不变；W5 后重录基线
uv run python -c "import mocode_tui"                        # exit 0
uv run pytest tests/test_readme_examples.py -q              # README 代码块
git grep -n "COMPOSER_KEYMAP\|mocode_tui.chat\|from .chat\|from \.\.chat"   # W3 后必须为空
```

harness 事实（agent 必读）：

- OS = win32（Git Bash），Python 3.12+，`uv run` 是唯一入口；无网络、无浏览器、**无真实终端**：
  hover / 鼠标 / 粘贴 / 键盘节奏只能 headless（`ScriptedKeys` + `HeadlessScreen`）验；
  真机项集中在每波验收末条，由 lead/用户终验。
- 库契约：**测试与 headless 路径零 sleep**；示例的交互路径才允许 `sleep` 出节奏。
- `HeadlessScreen` 忽略 tracking 字节：hover 的单测直接喂 `MouseEvent(kind="motion", button=0)`，
  不依赖 1003 真的被终端发出。

## 范围外（明确不做，附未来形状）

- **回调/事件总线**：本库仍是「组件存状态、宿主读状态」；`chosen` 是唯一通道。
- **容器代理键盘事件**：`Padding(Editor())` 要键盘就把 `Editor` 注册进 `FocusRing`；
  容器只保证点击/hover 下钻。未来若要代理，形状是容器 proxy `handle/move/activate/focused`。
- **`Text` 内联可点 span**：先由 `Link` 组件承担；未来形状 = `Segment` 携带一个 action id，
  `Pointer` 派发时按 id 查表。
- **真模型接入**：demo 永远本地 canned；要接 LLM 作为独立示例（新文件），不动本组契约。
- **跨窗格 hover / 拖拽 hover**：本组 hover 只在指针所在文档内、按住按钮时不做特殊处理。

## 交付后手测清单（终稿，真机，lead 终验用）

> 前置：真实终端，全程 `uv run python examples/demo.py`。hover 是本组唯一无法在 headless 证实的环节
> （wire→decoder→`Pointer`→组件链已有单测），**VT 路径（Windows Terminal / conpty）与传统 conhost
> 记录路径都要跑一遍第 4 条**。按序执行、逐条核对预期。

1. **画廊观感**：启动进 alt screen；顶部钉住 header（标题 + 12 个 `nav` 标签单行不截断），底部钉住
   单行 `StatusLine`（左 `<page> · focus=<target>`、右 fps）；滚轮滚动时 header/状态行不动，右侧
   `Scrollbar` 更新；任何页面**无常驻输入框**；开场 `/overview` 索引 12 行。
2. **页面导航三路**：点 header 标签直接开页；`c-n`/`c-p` 前后翻页且首尾回绕；`/` 面板按名开页。
   `/data` 的 `↑↓` 移行、`enter` 落选 → toast + `last pick:` 行更新。
3. **`/` 模态面板**：`/` → 底部浮出主题 band 面板，**自带查询输入行**；键入过滤实时生效
   （`str` → `/streaming` `/structure` `/styles`）；`↑↓` 走列表；`enter` 开页且面板整体消失；
   `Esc` 关闭且无选中；关闭态零行、零注册、零收键（`q` 直接退出）。
4. **hover 跟随（压轴）**：`/action` 指针划过 `Button`/`Checkbox`/`Link` → 悬停带跟随、移开即消失；
   `/data` 表行、`/navigation` 的 `Tabs`/`Tree` 行 → 行级 `hover_at` 高亮；指针静止不闪不重绘
   （无变化零字节）；悬停不触发点击/滚动。**VT 路径**（Windows Terminal）与 **传统 conhost 记录路径**
   各跑一遍——后者由 `TUI(hover=True)` 门控合成裸 motion（W5b 修复点），若完全无 hover 记机型回报。
   按住左键拖拽时 hover 不抢报告、selection 正常。
5. **容器包裹点击**：用一次性 headless/真机探针（`Padding(Row([Button]))` + `Pointer(ring=...)`）点击
   → 命中被包装的叶子（`chosen=True`）；点包装器内边距/间隙 → 无动作。点击丢失即容器吞交互回归。
6. **`c-o` 与 resize**：`/features` 或 `/split` 下 hover 后按 `c-o` → **悬停带立即清除**（画廊在
   `_cycle_panes` 调 `pointer.clear()`）；再移动一格 → 悬停落在新几何的正确叶子。窗口 resize 后
   移动指针一次，无错位残留（最佳努力）。
7. **selection 拖拽 + 复制**：按住拖过若干行 → 高亮带跟随、到边行自动滚动；松开 → "Copied N lines"
   toast 且 OSC 52 尽力写剪贴板（终端拒绝属预期）；单击只清选择、不清剪贴板。
8. **退出**：`q` 与 `c-c` 各跑一次 → 干净退出、alt screen 恢复、光标可见、shell 无残留转义。
9. **无终端两路**（可先跑）：`demo.py < /dev/null` → exit 0、无 stderr、末帧为 `/action`（含
   `last pick: True` 与 `[x] Trace`）；`demo.py --pages` → exit 0、恰好 12 个 `── /<page>` 页头、
   `/streaming` 读到 `98/98 blocks · paragraph · done · 1x`。
