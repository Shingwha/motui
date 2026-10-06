# Spec showcase-redesign · 总纲（按新组件整体重做展示台）
> ✅ **2026-10-07 全组五波已合并**（W1 `sr1-shell` → W5 `sr5-streaming`，每波合并前后各过一次全门禁）：

> 操作启动日 **2026-10-07**（组内 slug `showcase-redesign`；同日另有一组 `2026-10-07-interaction-model`，
> 本组在其六波全部合并之后启动）。
>
> 本组是一次**展示台的从展示角度的重做**：不做"在旧页面上加两行"的微调，而是先定一套
> **展品语法**与**导航/反馈/流式**的展示系统，再把每一页按它重建。目标读者是"第一次打开
> 这个库的人"：他要在 30 秒内知道**这是什么、怎么玩、对应哪行 API**。
>
> Git / worktree 协议见 `spec-team` SKILL（worktree 放仓库外、分支从合并时刻最新 main 切出、
> agent 不 merge / push / tag、lead 统一创建与销毁）。本组不重复。
>

## 目标与范围

1. **交互即证据**：interaction-model 刚落地的五个能力（`click(row, col)`、`activate()`/`chosen`、
   `FocusRing` 与失焦变暗、字段落点、bracketed paste）要在展台上**被看见、被玩到**，
   而不是只存在于文档。
2. **Markdown 流式是特性**：一份 346 行的 fixture（每种构造）按**块**流入，可 `play / pause /
   step / replay`——流式成为一个可反复把玩的展品，而聊天页的回复复用同一套流式机制。
3. **导航与反馈可见化**：顶部一条可点的 `Tabs` 导航（另配 `c-n`/`c-p` 前后展品），
   激活结果有回声（toast + 页内 last-action 行），焦点状态在状态行可见。
4. **统一语法**：每页三样东西——`header`（这是什么）、`try_line`（你该做什么）、
   `api_note`（对应哪行 API）；页面之间的观感与操作方式一致。
5. **工程性照旧**：piped 回放（`< /dev/null`）与 `--pages` dump 仍是门禁级契约，
   且流式展品必须 **dump-safe**（非交互路径构造即完整）。

**范围**：只动 `examples/`（`demo.py` + `showcase/` 包）与文档（README、相关 docstring）。
**不动 `src/` 一行**（要动先上报）；不加依赖、不引网络/模型。

## 现状与问题清单

完整审计在 `ref/showcase-audit.md`（文件规模、10 页各自的展示缺口、壳的事件路由、
键位空位、`--pages` 的 dump-safe 事实、七条可直接依赖的新能力）。压缩成五条：

1. 页表是静态 `Table`，不是活索引；页与页之间没有可见导航。
2. `chosen` 无声：宿主从不读它（W4 报告点名的缺口）——`activate()` 的成果观众看不到。
3. 失焦变暗（W4 的卖点）没有任何一页"点破"，观众看到变暗也不知道那是什么。
4. Markdown 页是静态整页；流式只发生在聊天回复里，且是"逐行赋值"的临时实现。
5. `features` 页用文字描述"怎么看到"，而不是让观众**做**那个动作。

## 设计定稿

### A. 壳（导航 + banner + 状态行）

- **顶部导航条**：一条 `Tabs`（12 个展品名）pin 在 top，紧跟标题行；**可点**
  （`tabs.click(row, col)` → 宿主读 `tabs.active` → `show(PAGES[i])`），`c-n`/`c-p` 前后翻展品，
  `/` 面板照旧（三条路并存）。换页/换主题后导航条 active 必须同步。
- **banner**：`标题 · <展品名>`（accent）→ 导航条 → 提示行（DIM，含当前展品的 `TRY` 短句 +
  全局键位）→ 分割线。提示行整行宽度预算 = headless 110 列内单行（沿用现状；超了会折行并
  改变 dump 行数——**新的页数/行数基线由 lead 重记**，见门禁）。
- **状态行**：footer 左侧加当前**展品名**与**焦点对象**（`interaction: focus=tree`），
  右侧保留 fps 读数。

### B. 展品语法（每页统一，`page.py` 提供助手）

```
header(title, blurb)        # 这是什么：标题 + 一句定位
try_line("…")               # 你该做什么：点哪 / 按什么 / 看什么（accent）
section("…")                # 分段
<展品块>                     # 活的组件，各自挂块
api_note("…")               # 它是什么 API：一行可复制（dim）
```

- `PageBody.hint` 保留（banner 用短版），`PageBody.focus` / `tick` 语义不变。
- `api_note` 的文案必须**可复制且真实**（源码里存在的名字与签名）。

### C. 反馈通道（`chosen` 的可见化）

- 宿主统一"读一次"：`activate()` 产生的 `chosen` 由宿主读一次、立即清空，然后
  **toast**（`Toasts.show`）报出拿到的值；`interaction` 展品另有一条页内 last-action 行（最近 3 条）。
- 每个可激活展品至少有一条可见回声路径（toast 或页内行），杜绝"按了没反应"。

### D. 流式（两个主角之一）

- **按块流入**：把源文本切成"块"（heading / 段落 / 围栏代码 / 表格 / 引用各算一块），
  一块一个 chunk；交互时每块有可见的短停顿，headless 不 sleep（库契约）。
- **控制条**：`play / pause / step / replay / 速度×2` 用一个**单项 `Select`** 实现
  （D6 配方：`activate()` → `chosen` 读一次 → 执行动作）——顺带演示"没有 Button 组件"的替代写法。
- **dump-safe**：`interactive=False`（piped 回放 / `--pages`）时，展品**构造即完整**；
  dump 必须显示完整 fixture。这是硬验收。
- **复用**：聊天页的流式回复改用同一 Streamer（保留原来的观感：thinking 逐词、正文按块）。

### E. 页表（终态 12 展品；`data`→`text`、`markdown`→`streaming` 更名）

| # | 页名 | 一句话定位 | 玩法（TRY） | api_note 方向 |
|---|---|---|---|---|
| 1 | `overview` | 这是 mocode-tui 的展台：12 个展品，一个库 | 点下面任意一行 / `c-n` | `Showcase.show(page)` |
| 2 | `text` | 承载内容的原语：Text / Markdown / Table / Divider | 点表格行、`↑↓`、`enter` | `Table.index` / `chosen` |
| 3 | `structure` | 盒子、列、页签、树 | 点 Tabs / Tree；`tab` 换焦点看变暗 | `FocusRing` / `Tree.activate` |
| 4 | `lists` | 菜单内核：Select / Confirm / Autocomplete | 点行 / `↑↓` / `enter` → toast 报 chosen | `Select.chosen` |
| 5 | `fields` | 两个文本字段："点哪儿，光标就落哪儿" | 在文本任意一格点一下 | `TextBuffer.place` |
| 6 | `feedback` | 进度与反馈：bar / spinner / notice / toast | 激活一个会弹 toast 的展品 | `Toasts.show` |
| 7 | `styles` | 主题与样式：换肤、色卡、属性 | 点一个主题名 → 整壳换肤 | `Theme` + `replace` |
| 8 | `keys` | 三张 keymap 与重绑故事 | 读表；复制一行重绑示例 | `DEFAULT_*_KEYMAP` |
| 9 | `features` | 壳的工程性：分屏、滚动、选择、无终端三条命令 | `/split`、拖动、跑 `--pages` | `tui.split` / `SelectionGesture` |
| 10 | `interaction` | **交互模型**：焦点环 / 点击 / 激活 / 落点 | `tab`→`↑↓`→`enter`；点一次聚焦、再点激活；点进文本落光标 | `FocusRing.handle/click` |
| 11 | `streaming` | **流式 Markdown**：346 行 fixture，按块流入，可重播/单步 | 控制条 `play/pause/step/replay` | `Markdown.text` + `StreamHandle` 思路 |
| 12 | `chat` | 聊天层组件 + 一个活回合 | 打字回车，看流式回复 | `Transcript.stream` |

## 决策登记（拍板，不再反复）

- **D1 导航三条路并存**：可点 Tabs 条（鼠标）+ `c-n`/`c-p`（键盘，audit 证实两键未被占用）+
  `/` 面板（原路）。`tab` 仍是**控件焦点**（D8 of interaction-model），不参与翻页。
  导航条渲染 `Page.nav` **短标签**（不是全名）：12 个全名约 117 列，会被 `Tabs.fit` 截断，
  而截断的 label 不可点——短标签组合必须 ≤110 列且不含 `…`（硬约束，实测为准）。
- **D2 展品语法三件套**：`header` / `try_line` / `api_note`（+ `section` 分段），由 `page.py` 提供；
  所有页统一，不允许某一页自己长一套排版。
- **D3 反馈统一走宿主**：`chosen` 读一次 → toast；`interaction` 页额外有 last-action 行。
  组件不新增回调（全局不变量 1）。
- **D4 流式按块、可控制、dump-safe**：块粒度流式 + 单项 Select 控制条；非交互构造即完整。
- **D5 键位增量最小**：只新增 `c-n`/`c-p`；`tab`/`c-o`/`enter`/`c-j`/`escape`/`c-c`/`/` 全部不变。
- **D6 只动 examples + 文档**：`src/` 零 diff；要改库代码 → 停下上报（新组另立）。
- **D7 页名更名**：`data`→`text`、`markdown`→`streaming`；README 与 help 同步（更贴内容）。
- **D8 流式内容就是 fixture 本体**：`examples/Markdown-Rendering-Test.md` 不新写第二份；
  聊天页保留 `REPLY_LONG/REPLY_SHORT`。
- **D9 契约照旧**：piped 回放、`--pages`、`framebench`、README 四段 python 块都不许破；
  dump 行数变化是**有意的**，由 lead 重记基线。
- **D10 不做**：hover、动画特效（只保留 bar/spinner/流式这类"内容在长"的动）、Button 组件
  （用单项 Select 配方）、真模型接入、i18n、库 API 更名。

## 波次表（严格串行；每波一个 agent，合并后再派下一个）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | 壳与语法：pinned Tabs 导航（点击 + `c-n`/`c-p`）、banner/状态行重排、`page.py` 的 `try_line`/`api_note`、`overview` 变活索引、`text` 页做语法样板、README demo 段骨架 | `examples/showcase/{page,session,registry,components,script}.py` `examples/demo.py` `README.md` | — |
| W2 | 展品 A：`structure` / `lists` / `fields` / `feedback` 四页重做，`lists` 的 chosen 回声（第一条可见反馈） | `examples/showcase/{components,session,registry,script}.py` `README.md` | W1 |
| W3 | 展品 B：`styles`（主题选择器，chosen → 换肤）/ `keys` / `features` / `chat` 四页套语法 | `examples/showcase/{styles,features,chat,registry,session,script}.py` `README.md` | W2 |
| W4 | `interaction` 展品：焦点三件套 + 实时 last-action 行 + 宿主反馈通道收口（导航点击也走同一套） | 新 `examples/showcase/interaction.py`、`session.py`、`registry.py`、`script.py`、`README.md` | W3 |
| W5 | `streaming` 展品：按块流入 + 单项 Select 控制条 + dump-safe + `chat` 回复复用同一 Streamer | 新 `examples/showcase/streaming.py`、`content.py`、`chat.py`、`session.py`、`registry.py`、`script.py`、`README.md` | W4 |

> 调度顺序 = 表序，严格串行（五波全部落在同一批文件上，无并行空间）。
> 每波自带"文档同步 + 回放覆盖自己新增内容 + 门禁真实输出"。

## 全局不变量（每波每 commit 都不得违反）

1. **`src/` 零 diff**：本组只动 examples 与文档；`git diff --stat <base> -- src/` 必须为空。
2. **交互即证据**：本波新增/改动的可激活展品，`chosen` 必须有可见回声（toast 或页内行）。
3. **dump-safe**：非交互路径下一切内容完整（尤其流式展品）；`--pages` 不许出现空展品。
4. **一致性**：同一套展品语法、同一套键位、同一套反馈通道；不允许"这一页特别"。
5. **文档同波**：README demo 段、`examples/demo.py` docstring、改动模块的 docstring 与代码同波更新。
6. **命名与语言**：代码注释/docstring 英文，spec 中文；commit 风格
   `type(scope): 小写短句 -- 第二句`，单行、无句号。
7. **门禁不破**：`pytest` 948/1、`framebench` hash、README 四段 python 块（`6 passed`）。

## 门禁（每波合并前、合并后各跑一次，贴真实输出）

```bash
uv run pytest -q                                            # 期望一字不变：948 passed, 1 skipped
uv run python examples/demo.py < /dev/null; echo exit=$?    # exit=0；dump 含本波展品内容
uv run python examples/demo.py --pages                      # exit=0；页头数 = 页表长度；streaming 页完整
uv run python tools/framebench.py                           # hash 与基线逐字符一致
uv run python -c "import mocode_tui"                        # exit 0
uv run pytest tests/test_readme_examples.py -q              # 6 passed
git diff --stat <base>..HEAD -- src/                        # 空
```

harness 事实（agent 必读）：

- OS = win32（Git Bash），Python 3.12+，`uv run` 是唯一入口；无网络、无浏览器、**无真实终端**：
  鼠标、粘贴、键盘节奏只能 headless（`ScriptedKeys` + `HeadlessScreen`）验；
  真机项集中在本文件末节，由 lead/用户终验。
- 库契约：**测试与 headless 路径零 sleep**；交互路径才允许 `sleep` 出节奏。
- dump 行数/页头数每波都会变：**agent 只报告真实数值，不改 spec/ref**（基线由 lead 重记）。

## 范围外（明确不做，附未来形状）

- **真模型接入**：展台永远本地 canned；未来若要接 LLM，作为独立示例（新文件），不动本展台契约。
- **hover**：interaction-model 的 D5 已拍板不做（1003 事件风暴）；本组不重启。
- **动画特效**（淡入/移动/过渡）：本库是无动画的 painter 模型；只保留"内容在长"的动。
- **`Button` 组件**：仍用"单项 `Select` + `activate()`/`chosen`"配方（D6），本组把它演给观众看。
- **页面深链/URL**：TUI 无 URL；`--pages` dump 就是"外部可引用"的形态。

## 交付后手测清单（真机，lead 终验用）

1. 打开即 overview：点导航条上任意 tab 名 → 直接切到该展品；`c-n`/`c-p` 前后切；`/` 面板照旧。
2. `interaction`：`tab` 在三个控件间循环 → 失焦控件的光标行**变暗**；`↑↓` 只动聚焦者；
   `enter` 激活 → toast 报出 `chosen`；点一次聚焦、同一控件再点一次激活；点 Editor 文本中间 → 块光标落在那一格。
3. `lists`：点一行 → 光标跟过去；`enter` → toast 报出 `option NN`。
4. `fields`：在 Editor 第三行中间点一下 → 光标落在那一格；粘 3 行文本 → 填一行/三行不提交（粘贴语义按组件而定）。
5. `streaming`：打开即见文档增长；控制条 `pause` 停住、`step` 走一块、`replay` 重头；切换展品再回来会重播。
6. `styles`：点一个主题名 → 整个壳（含导航条与页内组件）换肤。
7. `/split` + `c-o`：第二窗格独立滚动；拖动选择 → release 复制并弹 toast。
8. 无终端路径：`demo.py < /dev/null` 与 `--pages` 都 exit 0，`--pages` 的 streaming 页是完整 fixture。
