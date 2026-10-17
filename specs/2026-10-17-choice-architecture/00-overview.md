# Spec choice-architecture · 总纲（归并、模态层与组件族收口）

> 操作启动日 **2026-10-17**（组内 slug `choice-architecture`）。
> 基线：`main` @ `fb89f2a`（v1.1.0）。**门禁基线（lead 已实测）**：
> `uv run pytest -q` = **1422 passed / 1 skipped**；`tools/golden.py --check` = 11 页全等；
> `tools/apidoc.py --check` = 170 条目；`tools/framebench.py` render-hash =
> `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`；
> `python -m motui < /dev/null` 与 `--pages` 均 exit 0。
> 版本**不 bump**（lead 决定：本组只做重构与补齐，发版另等指令）。
>
> **✅ 全组合并（2026-10-17 @ main）**。基线 `fb89f2a`（1422p/1s、golden 11、apidoc 170、
> hash `de48e747…`），合并记录：spec `f6723f0` → W1 `c9483e2`（`arch1-kernel`）→
> W2 `090f0a7`（`arch2-widgets`）→ W3 `1fa1406`（`arch3-modal`）→ W4 `a91629c`（`arch4-demo`）。
> 门禁终态：`pytest` **1472 passed / 1 skipped**，golden **12 页**全等（新增 modal 页），
> apidoc **186 条目**，`render-hash` 与基线**逐字符一致**（`de48e747…`），demo piped 与
> `--pages` 均 exit 0（12 页）。分支全部保留、worktree 已清。两处登记：根门面最终
> **33 名**（工单 T4 文案误写 31，枚举列表 33 为准——`Dialog`/`Modal` 进根）；
> W4 worker 报告过一条来源不明的夹带"lead 消息"（非 lead 所发），worker 已按"不可信通道"
> 拒绝执行，行为无污染。
>
> **后续修正（2026-10-17，`docs-drop-apidoc` → main `3459a42`）**：本组各工单里的
> `apidoc --check/--write` 门禁**已不存在**——用户判定生成式 `docs/API.md` 为无价值产物，
> `docs/API.md`、`tools/apidoc.py`、`tests/test_api_doc.py` 整体删除，门禁清单与
> CONTRIBUTING/README/DESIGN/CHANGELOG 同步；facade 名字仍由 `tests/test_api_root.py` 钉住。
> 本组"门禁终态 apidoc 186 条"一语自此仅作历史记录。


本组是**一次库的减法 + 一层新机制**：删掉错位与重复的实现（`Confirm`、
顶层 `chrome.py`、碎文件）、把「一组行 + 单游标」收敛成一个基类、把
「模态/浮层」从三处手写升级为一层统一机制（`Modal` + `Dialog`），
再顺带补齐表单侧缺件（多选标记、掩码输入、组合框）。

**不做向后兼容**：被取代的名字、模块、别名同波删除，全仓 grep 零残留
（沿用 `docs/DESIGN.md` 的 no shim / no alias 契约）。

## 红线（每波都适用，写进每个 agent 的提示词）

1. **不新增冗余测试**（用户明示）：按行为写断言，不按类/文件写；合并组件在
   既有测试文件上扩断言，不另开重复用例；不写「每个方法一个 happy path」的
   填充用例；失效旧用例删除而不是保留；golden/`--pages` 覆盖的输出不再手写断言。
2. 每个 commit 独立过门禁（`pytest` + `golden --check` + `apidoc --check`；
   动到 demo 或可见画面的波加 `python -m motui < /dev/null`、`--pages`；
   动到热路径加 `framebench.py`）。
3. **行为变化要重录 golden 并在 commit message 里解释**；重录必须在同一 commit。
4. 写入范围外零 diff；禁触清单逐文件写明；越界即停，报告阻塞点。
5. agent 不 merge / 不 push / 不打 tag / 不 checkout main / 不碰主检出与其他 worktree；
   spec 归 lead 所有，agent 不更新任何 spec 状态（完成信号 = 最终报告 + 分支 commit）。
6. 环境：win32 + Git Bash；命令一律 `uv run …`；不保证真 TTY；文档语言中英混排沿用
   既有多数习惯（模块 docstring 英文、spec 中文）；注释写约束不写「我为什么改」。
7. **单一事实源**：模块 ↔ 测试文件按 `CONTRIBUTING.md` 的「one source module, one test
   file」对应，改名/合并同波完成。

## 目标结构（四波后的终态）

```
src/motui/
├── kernel/
│   ├── cursor.py       ★新  CursorWindow：光标+窗口的纯算术（Select/List 共用）
│   ├── mark.py         ★新  MarkSet + mark_prefix（多选标记共用）
│   └── …（其余不动）
├── interaction/        策略层：所有控制器住这里
│   ├── focus.py pointer.py gesture.py search.py         不动
│   ├── modal.py        ★新  Modal：注册/遮罩/定位/统一事件路由
│   ├── overlays.py     ★新  Toasts · Tooltip · Stats（原 chrome.py 三个 overlay）
│   └── scrollbar.py    ★新  Scrollbar（原 chrome.py）
├── widgets/            纯组件层
│   ├── action.py       ★合并  Button · Checkbox · Link（原 3 文件）
│   ├── choice.py       ★重构  Option · Select(Base) · Autocomplete · Radio · CheckGroup
│   │                        （原 choice.py + radio.py；删旧 Confirm）
│   ├── textfield.py    ★合并  Input · Editor（原 input.py + editor.py + field.py）
│   ├── dialog.py       ★新   Dialog · Confirm（纯组件）
│   ├── rows.py         ★合并  StatusLine · ShortcutBar · Notice
│   ├── indicators.py   ★合并  ProgressBar · Slider · Spinner
│   ├── layout.py decor.py diff.py list.py table.py tabs.py tree.py
│   ├── markdown/ syntax.py
│   └── （删）button.py checkbox.py link.py input.py editor.py field.py
│              radio.py statusline.py shortcutbar.py progress.py spinner.py
│              slider.py palette.py choice.py(旧)… 见「删除清单」
├── keys/ app.py testing.py                          不动
└── __init__.py                                      根门面重钉；删顶层 chrome.py
```

## 删除 / 合并 / 新增清单（决策已拍板，不再反复）

**删除**

| 对象 | 去向 |
|---|---|
| `widgets/choice.py` 的 `Confirm`（Select 特化） | 由 `widgets/dialog.py` 的 `Dialog` + `Confirm` 取代 |
| `motui/chrome.py`（顶层模块） | 拆入 `interaction/overlays.py` + `interaction/scrollbar.py`；`Scrollbar`/`Toasts` 根名保留 |
| `widgets/field.py` / `input.py` / `editor.py` | 合并为 `widgets/textfield.py` |
| `widgets/radio.py` | 并入 `widgets/choice.py` |
| `widgets/button.py` / `checkbox.py` / `link.py` | 合并为 `widgets/action.py` |
| `widgets/statusline.py` / `shortcutbar.py` | 合并为 `widgets/rows.py`（+ `Notice`，从 decor 迁出） |
| `widgets/progress.py` / `spinner.py` / `slider.py` | 合并为 `widgets/indicators.py` |
| `widgets/palette.py` | `Palette` 迁 `interaction/palette.py`，改用 `Modal` |
| `interaction/search.py` | 改名 `interaction/find.py`（内容基本不动） |

**新增**

- `kernel/cursor.py`：`CursorWindow`（Select/List 共用窗口算术）。
- `kernel/mark.py`：`MarkSet` + `mark_prefix`（多选）。
- `widgets/dialog.py`：`Dialog`（标题+正文+按钮行，纯渲染+键盘状态机）、`Confirm`（薄包装）。
- `widgets/choice.py`：`CheckGroup`（多选）。
- `widgets/textfield.py`：`Input(mask=…)`、`Editor`。
- `interaction/modal.py`：`Modal`（控制器：遮罩、居中/锚定、事件路由、点击外部关闭）。
- `interaction/palette.py`：`Palette`（Modal + Input + Autocomplete 组合）。
- `widgets/dialog.py` 附带 `Prompt`（Dialog + Input body，W3 加）。

## 决策登记（拍板，执行时不得再改）

- **D1 `Select` 是唯一菜单基类**，五个旋钮表达全部变体：`wrap`（菜单 True / 数据视图
  False）、`commit`（表单控件 True：移动/点击即写 `chosen`；菜单 False：只有 `activate`
  写）、`multi`（True 时 `chosen` 携带**被标记的全部值**，Toggle 语义）、`marker`、`window`。
  `Autocomplete` 只覆写 `_rows()`；`Radio` 与 `CheckGroup` 是同一基类的两个常量预置。
- **D2 `Dialog` 纯组件 / `Modal` 控制器**：`Dialog` 不知道屏幕几何，`Modal` 负责 overlay
  注册、全屏遮罩、矩形定位与事件路由。定位策略：`place="center"` 与 `anchor=(y, x)`
  （锚定框的左上角，钳制入屏）两种，`ComboBox` 与未来右键菜单复用后者。
- **D3 按钮行顺序恒为「主动作在左、取消在右」**，与 danger 无关；
  `danger=True` 的默认焦点落在**最后一个非危险按钮**（通常即取消），且危险按钮不绑定
  Enter（GNOME HIG 规则）。左右方向键 / Tab 在两个按钮间移动；`Escape` 恒取消；点击框外
  即取消。
- **D4 遮罩 = 属性 dim，不清屏**：`overlay(Style(dim=True), row.segments)` 逐行合并
  （颜色保留、权重降下，Textual 的 60% scrim 手法）；`Dialog(shade=…, scrim_style=…)`
  全可覆盖。
- **D5 语义与自定义性一个不少**：每个可见部分 = 显式参数 > theme 字段 > `DEFAULT_THEME`
  的既有 `_pick` 约定；文字（标题、按钮 label、placeholder）均可覆盖；
  `Dialog` 的每个按钮可用 `ButtonSpec(label, value, style, hover_style, focus_style,
  danger)` 单独定制。
- **D6 多选不进 `Tree`**：父子半选态是另一尺度，明确不做（写进 COMPONENTS.md 的
  「刻意不做」）。
- **D7 模态的返回语义**：`modal.chosen` 是**任意的按钮 value**（`object | None`，初始
  `None`）；`Escape` / 点框外 / `close()` 一律 `None`；宿主读一次并重置为 `None` ——
  与库内 `chosen` 约定一致。
- **D8 `Find` 本组不动**（它没有"模态打开"的重复：全屏 overlay + 底部查询行是它自己的
  形态）；只有 `Palette` 从手写 open/handle 迁到 `Modal`。删重复指的是删重复，不是把所有
  东西塞进同一个模子。
- **D9 名字**：`CheckGroup`（不是 `CheckboxGroup`）；`Prompt`（不是 `InputDialog`）；
  `Modal`（控制器）；`Dialog`（纯组件）；`combo` 即 `ComboBox`。

## 波次表（严格串行；一次一个 agent；合并过门禁后才派下一个）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | kernel 原语：`CursorWindow` + `MarkSet`/`mark_prefix` + 单测 | `kernel/{cursor,mark,__init__}.py` `tests/test_cursor.py`（新） | — |
| W2 | widgets 归并重构：action/choice/textfield/rows/indicators + `Dialog`/`Confirm` + 测试归并 | `widgets/**` `tests/test_widgets_*.py` `tests/test_api_root.py` | W1 |
| W3 | interaction 层重组 + `Modal` + `Palette` 迁移 + `Prompt` | `interaction/**` 删 `chrome.py` `widgets/dialog.py` `tests/**` | W2 |
| W4 | demo 重建（modal 页/多选/掩码/ComboBox 展示）+ 文档对位 + 门面重钉 + golden 重录 | `demo/**` `docs/**` `tools/apidoc.py` `tests/golden/**` | W3 |

## Git / worktree 协议（沿用 spec-team SKILL）

- worktree 根在仓库外：`C:\Users\shifu\.worktrees\mocode-tui\<branch>`；分支名依次
  `arch1-kernel` / `arch2-widgets` / `arch3-modal` / `arch4-demo`，**每波从合并时刻的最新
  main 切出**（lead 负责创建；agent 绝不操作主检出 `C:\Users\shifu\Desktop\mocode-tui`
  与其他 worktree）。
- 全程不 push、不打 tag、不 bump 版本。分支保留，worktree 由 lead 收尾清理。

## 收尾（lead）

终验全门禁 + demo 三入口抽验 → 汇总报告（做了什么 / 取舍 / 遗留 / 待指令事项）。
不发版、不 push。
