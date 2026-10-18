# Spec demo-presentation · 总纲（demo 呈现规范化：分组 rail、统一页面模板、散文归 notes）

> 操作启动日 **2026-10-18**（组内 slug `demo-presentation`）。
> 基线：`main` @ `e30f2bf`。**门禁基线（lead 已实测）**：`uv run pytest -q` =
> **1504 passed / 1 skipped**；`tools/golden.py --check` = 11 页全等；
> `tools/framebench.py` render-hash = `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`；
> demo 两入口 exit 0。版本**不 bump**。
>
> **✅ 全组合并（2026-10-18 @ main）**。合并记录：spec `f9bd818` → W1 `208e0bb`（`pres1-grammar`）→
> W2 `376156d`（`pres2-polish`）→ lead 清理 `Section.draft` 死字段。门禁终态：
> `pytest` **1507 passed / 1 skipped**，golden **11 页**全等，`render-hash` 与基线**逐字符一致**，
> 两入口 exit 0，脚本化交互（rail 分组点击、overview 表格点行、Tabs 展位）走通。
> 覆盖 **45/45**（`Tabs` 补上 `layout` 展位；`ShortcutBar`/`NavList` 为 demo 自身 chrome）。
> 决策登记：rail 分组标签大写由调用方拼写（`NavList` 不改写标签）、组行占渲染行但
> `active` 只数可选条目、caption 一律状态枚举式、签名速查 50 行（含 8 个从未有 API 行的
> 补全条目）入 notes、`Section.width` 记录但未启用（会挡住 flat pick scan，W2 未使用）。

**纯呈现重构，不加页面、不改覆盖**（lead 对账：44 个实质组件/控制器全部有展位；
唯二"缺席"的 `ShortcutBar`/`NavList` 是 demo 自身 chrome）。按主流组件库的呈现规范
（Storybook/MUI/AntD/Carbon/Primer/Polaris/shadcn + FTXUI/ratatui/Textual/tview 调研）：

- 索引页 = 分组目录 + 每项一句描述（MUI/AntD 形态）；
- 页面模板 = 标题+一句描述 → default → variants → states → 组合 → 参考放最后；
  每例 ≤1 行说明；散文归独立页；
- rail = 文档站 sidebar 的终端对应物，**用组标题行分组**（不嵌套）。

## 目标骨架（所有组件页同构）

```
── forms ─────────────────────────────────────────────  ← 页规则：页名 + 一句描述
 ── input ──                                             ← section 规则：组件名
   [ 活组件 ]
   default · focused · masked                            ← caption：至多一行，状态枚举优先
 ── combo box ──
   [ 活组件 ]
   …
```

**规则**：

1. **删掉全部 `API ·` 行**与页内散文（TRY 段、自由段落）；签名与全文说明迁 `notes` 页。
2. **删掉页内 `play ▸` 行**（lead 拍板）：交互规则统一收进 `notes`；页底提示条保留
   每页键位（`Page.hints` 不变）。
3. **caption 至多一行**、优先状态枚举（`default · hover · focus`）、不折行为目标
   （允许超宽，但不加句号不铺陈）。
4. **三级分隔层次**：页规则 `── name ────`（`Divider` 现有形态）；section 规则
   ` ── label ──`（前导空格 + 短尾线，视觉上从属于页）；caption 是 dim `Text`。
5. overview 索引页改为 **`Table` 三列**（页面 · 组 · 一句描述），点行即打开该页
   （Table 的 `activate`/`chosen` 语义），替换现在的 Select 索引。
6. rail 分组（三组，顺序即总纲）：
   **foundations** = overview/text/layout · **components** = actions/forms/views/modals ·
   **shell** = shell/themes/streaming/notes。

## 决策登记（拍板）

- **D1 页数不变**：11 页、族划分不变；本组只改呈现。
- **D2 rail 分组用 `NavList.groups`**（库层唯一改动）：`groups=((0, "foundations"),
  (3, "components"), (7, "shell"))`——插入位置 + 标签；组行**不可点、不可选、
  hover 不标记**，`active`/`select`/`click` 只数可选条目；组行样式 `group_style`
  （默认 `theme.muted`）、字形默认 `label.upper()`。
- **D3 kit 语法收敛到 `Section`**：`demo/kit.py` 的 `Exhibit` 改吃
  `Section(spec: str, *blocks, focus=None, caption="", width=None)`，组 = spec 段
  （如 `"input -- an empty one and a filled one"`）+ blocks + 可选单行 caption + 可登记
  focus 目标；`build()` 产出统一的 `PageBody`（页规则 + 组规则 + 组件 + caption 行）。
  **旧 `api=`/`try_line`/自由段落通道删除**；`header`/`try_line`/`api_note` 三个旧 helper
  从 `page.py` 删除（kit 是唯一入口）。
- **D4 caption 位置**：紧随该组的组件行之后、dim；分组之间用 section 规则隔开
  （` ── spec ──`，spec 超长时 `fit`）。
- **D5 签名速查进 notes**：`notes.py` 新增"签名速查"一节（代码围栏内按族列全部
  签名，一段 ` ``` ` 渲染；内容从各页收编，一处维护）；"怎么玩"一节全文保留
  （tab/方向键/enter/鼠标/拖选/复制/`c-n c-p`/`c-f`/`c-g`）。
- **D6 提示条**：`Page.hints` 机制不变（W4 收尾时可微调文案）。
- **D7 不动**：`Session` 路由、`Slot`/`Action`/`Pick` 机制、`script.py` 锚机制、
  库的其他部分（除 `NavList.groups`）。

## 波次表（严格串行；两波）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | `NavList.groups`（库+测试）+ kit 新语法（`Section`）+ 11 页**机械改版**（去 API/散文行，`Section` 化，captions 暂用旧信息压缩）+ rail 分组 + overview Table 索引 + golden 11 页重录 | `widgets/navlist.py` `tests/**` `demo/{kit,page,registry,shell}.py` `demo/pages/**` | — |
| W2 | 内容精修（captions 收敛成状态枚举、阅读序 default→variants→states）+ `notes` 手册与签名速查 + 协议测试跟改 + README/COMPONENTS 的 demo 段 + golden 定稿 | `demo/pages/**` `tests/test_demo_protocol.py` `README.md` `docs/COMPONENTS.md` `CHANGELOG.md` `tests/golden/**` | W1 |

## 红线（两波适用）

1. **覆盖不许缩水**：44 个组件/控制器的展位一个不少（W1 机械改版逐页核对，报告里列对账表）。
2. **不新增冗余测试**：`NavList.groups` 的用例并入 `tests/test_widgets_navlist.py`
   （组行不可选/跳选/渲染 3–4 条）；demo 行为由 golden/replay 覆盖。
3. golden 重录逐页解释、同 commit；framebench hash 变了逐条解释。
4. 库层只许 `widgets/navlist.py`；`kernel/` 不动。
5. agent 不 merge / 不 push / 不 checkout main；spec 归 lead。
