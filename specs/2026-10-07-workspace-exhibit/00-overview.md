# Spec workspace-exhibit · 总纲（`/workspace`：对话 + 可切标签的检查器）
> ✅ **2026-10-07 两波已合并**（W1 `ws1-aside` → W2 `ws2-agent-live`）：13 个展品、`--pages` 936 行 / 13 页头、
> `pytest` 保持 `948 passed, 1 skipped`、`render-hash` 未动、`src/` 零 diff。真机手测清单见本文件末节。

> 操作启动日 **2026-10-07**（组内 slug `workspace-exhibit`；本组是 `showcase-redesign` 组（12 展品）
> 的自然追加——第 13 个展品，一次**独立操作**，不改前组已定稿的展品）。
>
> 目标：新增一个展品页 `/workspace`，把"coding-agent 工作台"的版式演出来——
> **左边一段真实的对话，右边一个分屏检查器**（标签条 + 视图内容），标签可点、可键盘驱动，
> 视图内容取自对话产生的产物（工具调用 / 编辑差异 / 读到的文件 / 子代理消息流）。
> 这是对**分屏（frame 层）+ 标签条（组件层）+ 焦点环（focus 层）+ 流式（host 驱动）**
> 四层能力的一次合演，也是对"后续接真 subagent"的扩展点演示。
>
> Git / worktree 协议见 `spec-team` SKILL（worktree 放仓库外、分支从合并时刻最新 main 切出、
> agent 不 merge / push / tag、lead 统一创建与销毁）。本组不重复。

## 版式（定稿）

```
┌ 左：对话（内容 72 列）──────┬ 右：检查器（内容 36 列）─────┐
│ Message("user", …)          │  tools │ edits │ reads │ agent │ ← 标签条（pin top，可点）
│ Message("thinking", …)      │  ────────────────────────────  │
│ ToolBlock("$ pytest -q …")  │  当前视图的内容：              │
│ EditBlock("src/…py", diff)  │   tools → 命令与输出的全量      │
│ Message("assistant", …)     │   edits → 差异（新增/删除行）   │
│   （独立滚动，纯展示）      │   reads → 文件正文（fence 高亮） │
│                             │   agent → 子代理消息流（live）   │
├─────────────────────────────┴───────────────────────────────┤
│ composer（铺满整宽的底部 band，不变）                          │
└─────────────────────────────────────────────────────────────┘
```

## 决策登记（拍板，不再反复）

- **D1 页名与入口**：页名 `workspace`，导航条短标签 `work`；`PAGES` 12 → **13**，
  插在 `interaction` 之后、`streaming` 之前（"交互 → 工作台 → 流式"的叙事）。
- **D2 左栏只做展示**：一段 canned 对话，用真实组件（`Message` / `ToolBlock` / `EditBlock`），
  可独立滚动；**左栏不挂任何交互**（不做 jump 列表）。右栏是这一页唯一的交互面。
- **D3 右栏 = 检查器**：`pin="top"` 的 `Tabs` 条（**四个短标签** `tools/edits/reads/agent`，
  实测 31 列 ≤ 右栏 36 列、不截断）+ 一个内容块；**一次只挂一个视图**，
  切换 = `document.remove(old.id)` + `document.add(new)`，切完 `viewport.scroll_up(1 << 20)` 回顶。
- **D4 切换的两条路**：鼠标点标签（`Tabs.click(row, col)` → 宿主读 `tabs.active`）；
  键盘 `tab` 把焦点给标签条、`←→` 移动（`FocusRing` 的路由表把 `left/right` 交给 `Tabs.move`）。
  宿主新增 `PageBody.sync`（每轮事件后调用一次）：比较 `tabs.active` 与已挂视图，不同就换。
  **不允许依赖 `tick` 做切换**（非交互回放里 tick 不保证触发，会话是确定的）。
- **D5 agent 视图当场做 live**：canned 的 6~8 条子代理消息按 `tick` 逐条长出，切走再回来重播；
  **非交互路径构造即完整**（dump-safe，硬验收）。
- **D6 aside 机制（session 侧）**：`PageBody.aside: Callable[[Pane], None] | None` —— 页面用一个
  右窗格做检查器时声明它；`show()` **先关上一页的 aside 再开新的**；离开该页即关闭。
  `/split` 的预览与 aside **共用同一个右窗格槽位**：当前页自带 aside 时 `/split` 不叠第三个窗格
  （弹一条 toast 说明），其它页 `/split` 行为不变。
- **D7 右栏内容按 36 列设计**：短行、少列；长代码行会折行是可接受的（真终端同样如此）。
- **D8 只动 examples + 文档**：`src/` 零 diff；要动库代码 → 停下上报。
- **D9 门禁照旧**：`pytest` 948/1 一字不变、`render-hash` 不变、demo exit 0、
  `--pages` 13 页头（行数由 lead 重记）、README 六段可执行块不破。

## 扩展点（写进模块 docstring 与 README，本组交付的"后续"）

真宿主接 subagent 的配方：拿到消息就往 `agent` 视图的列表里 append + `tui.invalidate()`；
视图内的消息块与 `chat` 层的 `Message`/`ToolBlock` 是同一批组件，
`Transcript.stream` 那条 `StreamHandle` 路子同样适用。本展品用 canned 数据把这条管子演通，
**不引入任何回调、事件总线或异步组件**（沿用全局不变量 1）。

## 波次表（严格串行；每波一个 agent，合并后再派下一个）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | aside 机制 + 页面骨架：`PageBody.aside/sync`、`show()` 开关顺序、`/split` 规则、`workspace.py`（左对话 + 右标签检查器 + 四视图静态内容 + 切换 + 回放/文档同步） | `examples/showcase/{page,session,workspace,registry,script}.py`、`README.md` | — |
| W2 | agent 视图 live：canned 消息流按 `tick` 逐条长出（非交互即完整）、切走重播、回放覆盖、扩展点文档定稿 | `examples/showcase/{workspace,session,script}.py`、`README.md` | W1 |

## 全局不变量（每波每 commit 都不得违反）

1. **`src/` 零 diff**：本组只动 examples 与文档。
2. **左栏零交互**：左栏不挂 ring、不可点；这一页的交互面只有右栏标签条（D2）。
3. **dump-safe**：`--pages` 与 piped 路径下，右栏必须有**完整**的当前视图内容（agent 视图亦然）；
   分屏在 dump 里必须两栏并排可见。
4. **确定性切换**：视图切换只由 `sync`（事件后）驱动，不许依赖 tick/时间。
5. **一致性**：沿用前组的展品语法（`header` / `TRY ▸` / `API ·`）与反馈通道
   （`_report` / `PageBody.note`）；本页的 TRY 说明"点标签 / tab + ←→ 切视图"。
6. **命名与语言**：注释/docstring 英文，spec 中文；commit 风格
   `type(scope): 小写短句 -- 第二句`，单行、无句号。
7. **门禁不破**：`pytest` 948/1、`framebench` hash、README 四段 python 块（`6 passed`）。

## 门禁（每波合并前、合并后各跑一次，贴真实输出）

```bash
uv run pytest -q                                            # 期望一字不变：948 passed, 1 skipped
uv run python examples/demo.py < /dev/null; echo exit=$?    # exit=0
uv run python examples/demo.py --pages                      # exit=0；13 个页头；/workspace 两栏可见
uv run python tools/framebench.py                           # hash 与基线逐字符一致
uv run python -c "import mocode_tui"                        # exit 0
uv run pytest tests/test_readme_examples.py -q              # 6 passed
git diff --stat <base>..HEAD -- src/                        # 空
```

harness 事实：OS = win32（Git Bash），`uv run` 唯一入口；无网络、无真实终端——
鼠标与键盘只能 headless（`ScriptedKeys` + `HeadlessScreen`）验；**测试与 headless 路径零 sleep**。

## 范围外（明确不做）

- **接真 subagent**：展台永远本地 canned；本组只交付"管子"与扩展点文字。
- **左栏交互**（jump 列表）：D2 已拍板不做。
- **第三个窗格 / 嵌套分屏**：一页一个右窗格；`/split` 的预览不与 aside 叠加。
- **可拖拽分隔条**：窗格比例固定 2:1（比例可调是 `tui.split` 的能力，不是本页要演的）。
- **右栏富文本编辑器**：视图是只读展示（`ToolBlock`/`EditBlock`/`Markdown`），不做就地编辑。

## 交付后手测清单（真机，lead 终验用）

1. 打开 `/workspace`：左栏一段对话、右栏标签条 + 默认视图（tools），composer 仍在底部整宽。
2. 点 `edits` / `reads` / `agent` 标签 → 右栏立刻换成对应内容并回到顶部；点击无反应的分隔符区域不换。
3. `tab` 把焦点给标签条（左右两端不回头，`Tabs.move` 夹取），`←→` 换标签 → 右栏跟随；
   状态行 focus 读数正确。
4. `agent` 标签第一次进入时消息逐条出现；切走再回来重播；`--pages` 里它是完整的一段。
5. `c-o` 后滚轮/方向键滚的是右栏；再 `c-o` 回到左栏。
6. `/split` 在这一页弹 toast 说明（不叠第三个窗格）；切到别的展品后 `/split` 恢复原样。
