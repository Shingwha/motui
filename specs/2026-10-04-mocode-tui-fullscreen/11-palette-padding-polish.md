# Spec W11 · 配色升级 · 带内 padding · working 上边框（波次 W11，重构单）
> ✅ 2026-10-04 已交付合并（wfs11-palette）；651 passed + 2 skipped；真彩色板 + 带内 padding + Divider label + working 上边框 + 去回合分割线。lead 追加小修：Markdown h3/h4 回归强调梯级（accent→accent+underline→muted→muted dim）。

## 背景（用户 2026-10-04 第五轮真机反馈 + pi 参照图，逐条定格）

1. **术语纠正**：用户要的是 **padding**（带内垂直内边距）——「和这个块背景一样的多的一行」；
   W9/W10 做的是块间空行（margin），保留，但**带背景的块要在带内上下各多一行同色行**。
2. **pi 的块之间没有分割线**——W10 agent 自行添加的每回合闭合 `Divider` 删除。
3. **输入框不要 `❮` 前缀**——`Input(prompt="")`，空闲只剩光标块，与 pi 一致（prompt API 保留）。
4. **Working 状态放到输入框的上边框线上**——一个简单的行内状态显示（`── ⠋ Working ───`），
   不再占独立行；后续可拓展为「边框状态」API（本轮做到 `Divider(label=...)` 可变属性，
   调用式/提供器式 API 登记为后续）。
5. **整体配色重新设计**——现配色太强（user 带纯蓝 #0000ee 等），要缓和、易读、清晰。
   **lead 裁决：调色板升级为真彩色（24-bit SGR `38;2;r;g;b`/`48;2;r;g;b`）**，取一套
   GitHub-dark/pi 风暗色。理由：16 色里唯一的蓝是纯蓝，无法「缓和」；用户环境 Win11 +
   Windows Terminal 完整支持真彩。总纲「16 色封顶」非目标**由本单修订**（lead 权限，理由如上）。

## 目标色板（真彩色，lead 定格；命名常量仍在 style.py，fg/bg 可为 "#rrggbb" 或 (r,g,b) 元组）

| 常量 | 新值 | 用途 |
|---|---|---|
| `BORDER` | `#3d444d` 青灰 | 分隔线、面板边框 |
| `ACCENT` | `#58a6ff` 柔蓝 | 提示/强调/working 标签 |
| `MUTED` | `#8b949e` 灰 | 次要文字（thinking 等） |
| `SUCCESS` | `#4bb563` 柔绿 | 成功/`+` 行/✓ |
| `ERROR` | `#e5534b` 柔红 | 错误/`-` 行 |
| `WARNING` | `#d29922` 琥珀 | 通知标题 |
| `CODE` | `#a5d6ff` 冰蓝 | 行内代码 |
| `Message.USER_BG` | `#1c2b3a` 石板蓝带 | user 消息色带 |
| `ToolBlock.TOOL_BG` | `#16281c` 深绿带 | 工具调用色带 |
| `ToolBlock.CODE_BG` | `#12181f` 深蓝黑带 | codemode 色带 |
| `Table` 首列默认 | `#bc8cff` 柔紫 | 首列默认样式 |

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `style.py` — 真彩色 + 新色板
- `Style.fg/bg` 类型放宽为 `str | tuple[int,int,int] | None`：str 仍查 `FG_CODES`（未知名 KeyError）；
  tuple 走 24-bit SGR（`38;2;r;g;b` / `48;2;...`）；`None` 不变。`prefix()`/`_build_prefix()`
  分支处理；`merge()`/相等/哈希天然支持（frozen dataclass + tuple 可哈希）。
- 语义常量按上表换值。`RESET`/`FG_CODES` 不变。
- `tests/test_style.py`：rgb prefix 精确字节（fg/bg/混合命名色+属性）；merge 语义；
  缓存行为；旧命名色用例保持。

### T2 带内 padding（components/message.py + tools.py）
- `Message` 仅 **user 角色**：色带上下各加 1 行**纯 USER_BG 行**（无 prompt、无内容，
  通栏同色）；assistant/thinking 不加（无背景，块间空行即是分隔）。
- `ToolBlock`/`EditBlock`：整块上下各加 1 行纯带色行（跟 tone 走）。
- 行结构其余不变；`render(0/1)` 等窄宽不炸（窄宽时 padding 行仍出，内容行 fit）。
- `tests/test_components_message.py`/`test_components_tools.py`：补 padding 行数与样式断言
  （首行/末行 = 纯 band）；原有结构断言适配。

### T3 `Divider(label=...)`（components/chrome.py）
- 新参数 `label: str = ""`（可变属性）+ `label_style: Style = NONE`。
- label 非空：渲染 `char×2 + " " + label + " " + char×fill`，通栏 width；label 超宽
  （width-4 放不下）走 `ellipsize_tail`；空 label = 原纯分隔线行为。
- `tests/test_components_chrome.py`：空 label 不变；带 label 的形状与样式；超宽 ellipsize；
  可变 label 生效。

### T4 `examples/pi_demo.py` 收口
- 删每回合闭合 `Divider`（块间只剩空行；banner 的更新通知分隔线保留——pi 本来就有）。
- `Input(prompt="")`；`_anchor` 的 col 计算随 cursor_position 自动正确（无 prompt 偏移）；
  input 起始行公式保持 `height - 2 - input_rows`（working 已不占行，尾区四件套）。
- 固定尾区改四件套：`footer-top`（`Divider(style=BORDER, label=...)`）→ `input` →
  `footer-bottom`（纯 Divider）→ `footer-status`；working 时 `footer-top.label = f"{frame} Working"`
  （label_style=ACCENT），tick 里 `divider.label` 更新 + invalidate；`_WorkSlot` 改为操作
  footer-top 的 label（引用计数保留）。
- banner 的黄色/洋红改为 WARNING/柔紫（`Style(("#bc8cff"))`）；其余默认走新色板。
- W10 的 IME 锚定、后台 turn、`_Nothing` 空地台逻辑删除（working 不占行了，`_WorkSlot`
  只管 footer-top label）。

### T5 文档同步
- `README.md`：组件表 Divider 行补 label；tool tone 描述改柔色。
- `docs/COMPONENTS.md`：色板说明（真彩色 + 语义常量表）、Divider label、带内 padding 行为。
- `docs/DESIGN.md`：「16 色封顶」表述修订为真彩色（含理由：Win 现代终端/ConPTY 透传；
  命名 16 色仍可用，真彩是超集）。

### T6 门禁
- `uv run pytest` 全绿（贴尾部，N ≥ 623）；`python examples/pi_demo.py < /dev/null; echo exit=$?`
  exit 0，贴输出（确认：无闭合分割线、块间均一空行、带内 padding 行同色、输入框无❮）。

## 验收
1. pytest 全绿（贴尾部原文）。
2. piped demo exit 0 + 输出节选贴图级描述（上述四项目测点）。
3. `git diff --stat main..HEAD`：`src/mocode_tui/style.py`、`components/{message,tools,chrome}.py`、
  `tests/test_{style,components_message,components_tools,components_chrome}.py`、
  `examples/pi_demo.py`、`README.md`、`docs/{COMPONENTS,DESIGN}.md`。
4. SGR 抽检：`uv run python -c` 渲染 user 带/工具块各一帧，断言含 `48;2;28;43;58`、`48;2;22;40;28`。

## 禁触
其余一切文件（含 specs/、tests 未列项、pyproject）；不 merge/push/checkout main；不改 spec
（总纲非目标修订由 lead 在同一 commit 前置完成）。

## 诚实出口
- 窄宽（width<4）时带内 padding 行保留但内容行 fit——若测试发现某组合歧义，以「padding 行恒出、
  内容行永不超宽」为准并登记。
- `Divider.label` 与 char 宽度≥2 的字符组合出现对齐歧义时，以 `fit` 收尾为准。

## 最终报告格式
工单状态表（T1-T6：commit hash+message+结论）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
