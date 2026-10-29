# W7c · Docs / ADR / README

> 分支 `w2.1.2-w7c-docs`；起点 main @ `c692c0b`。
> 写入范围：`docs/**`、`README.md`。不改代码、不改测试、不改版本号。
> 与 W7a/W7b/W7d 并行（目录不相交）。

## 目标

把文档从 2.1.0 的构造/状态/样式语言更新到 2.1.2 契约；新增四个 ADR；
README/WIDGETS 的所有示例改新写法；`CONTRACT.md` 的公开面数字与门禁命令
更新。`CHANGELOG`/`MIGRATION`/版本号留给 W8。

## 前置上下文

- 必读：`ref/interfaces.md` §1–§10、`ref/repo-map.md`、本工单。
- 基线：`docs/CONTRACT.md`、`docs/WIDGETS.md`、`docs/ARCHITECTURE.md`、
  `docs/adr/ADR-001..026.md`、`README.md`。
- 已知新契约（举例，不完整）：
  - 构造：`Table(rows, headers=...)`、`Tree(nodes)`、`TreeNode(open=...)`、
    `Tabs(items)`、`MenuBar(items)`、`NavList(items)`、`RadioGroup(options)`、
    `CheckboxGroup(options)`、`Dialog(body, title=..., buttons=...)`、
    `Collapsible(body, title=...)`、`Canvas(*, width=...)`、
    `PixelCanvas(*, width=..., palette=None)`、`ProgressBar(value, maximum=...)`。
  - 状态：`index`/`selected`/`marked`/`value`/`checked`/`open`/`text`。
  - 动词：`activate/toggle/select/move/advance/take`；`on_action` 九名字。
  - 结果：`Table.take()` 行对象、`Select.take()` value、`Tree.take()` 节点、
    `Tabs/MenuBar/NavList.take()` 标签、`Slider` 无 take。
  - 样式：`SurfaceStyles.control/accent/danger/inactive`；
    `ControlStyles.overlay()`；`ButtonKind`；Dialog raised；字段底板。
  - 组合/绘制：`Line.overlay`/`Surface.overlay`、`Stack`/`Align`、
    `Drawing`（resize/fit/surface/render）。

## 工单（按序执行，每项一个 commit）

### T1 CONTRACT.md

- 更新 §5 组件协议：`keymap` 描述符、`ResultWidget`/`ActionWidget`/
  `CursorWidget` 的契约、`take` sentinel、`index` 可赋值。
- 更新 §8：能力/hook、`on_action` 九名字、state/verb/result 表、
  `Stack`/`Align`/`Drawing` 的加入。
- 新增一节“组件语义契约”（可放 §8 后）：构造规则、状态名、动词、结果、
  样式 overlay、键位。用表，不要长段。
- §11 公开面：`motui.widgets` 现在是 47 名（含 `ButtonKind`）；总行数 244；
  用 `uv run python tools/api.py --check` 的真实输出核对。
- 保留 2.1 的 kernel/terminal/app 条款，只改受影响的段落。

### T2 WIDGETS.md

- 更新所有表格行的构造签名与结果：
  `RadioGroup/CheckboxGroup(options)`、`Task`…、`Table(rows, headers=...)`、
  `Tree(nodes)`/`TreeNode(open=)`、`Tabs/MenuBar/NavList(items)`、
  `Dialog(body, ...)`、`Collapsible(body, ...)`、`ProgressBar(value)`、
  `Button(kind=)`、`ButtonSpec(kind=)`。
- 更新示例代码：`Table(headers, rows)` → `Table(rows, headers=...)`；
  `PixelCanvas(20, 8, palette=...)` → `PixelCanvas(width=20, height=8, palette=...)`；
  `Dialog("Confirm", Text(...), [...])` → `Dialog(Text(...), title="Confirm", buttons=[...])`。
- 新增 `Stack`/`Align`/`ButtonKind` 的短示例；`Drawing.resize/fit` 的说明。
- 删除过时的 `.fraction =` 示例，改 `.value =`。

### T3 ARCHITECTURE.md / README.md

- ARCHITECTURE：加一小节“Composition and drawing”：`Line.overlay` 透明
  规则、`Stack` 命中、`Align` 尺寸、`Drawing` 纯 render。
- README：更新构造示例（同 T2）、组件表里的 `take` 返回、`ButtonKind`；
  不要改安装/启动说明。
- 用 `rg` 搜旧名：`root_nodes|expanded|is_open|\.labels|commit=|danger=True|fraction =|Canvas\([0-9]|PixelCanvas\([0-9]|Table\(headers|Dialog\(title|Collapsible\(title`，逐个改。

### T4 ADR 027–030

按现有 ADR 格式（标题、状态、日期、上下文、决定、后果）新增：

- `ADR-027.md`：组合与透明（`Line.overlay`/`Surface.overlay`、`Stack`、
  `Align`、交互优先命中；为什么空白透明、宽字符整字替换）。
- `ADR-028.md`：绘制生命周期（`Drawing`：显式 resize/fit、surface 缓存、
  render 只裁剪；为什么不做 measure/render 两阶段）。
- `ADR-029.md`：组件状态/动词/结果契约（七个状态名、六个动词、take 规则、
  只有 activate/toggle 写 pending、on_action 九名字）。
- `ADR-030.md`：控件样式（通用 surface + `ControlStyles.overlay`，澄清
  2.0 的 no-recipe 规则；ButtonKind 四态；Dialog raised；flat 映射）。
- 更新 `docs/adr/README.md` 的索引（如存在列表）。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（docs 不改代码）。
2. `uv run python tools/api.py --check` 244 names match。
3. `uv run python tools/semantic.py --check` 9/9。
4. `rg` 旧名检查：上述模式在 `docs/`/`README.md` 无匹配（历史 ADR 和
   `docs/MIGRATION.md` 的旧表除外；MIGRATION 由 W8 改）。
5. 所有代码块是有效 Python（人工检查，不要求执行）。

## 禁触清单

`src/`、`tests/`、`tools/`、`pyproject.toml`、`CHANGELOG.md`、
`docs/MIGRATION.md`、`docs/releases/`、`uv.lock`。`handoff/W7c-<agent>.md`
是唯一例外。

## 交接包

写 `handoff/W7c-<agent>.md`：改了哪些章节、新增 4 个 ADR、剩余旧名
（若有）、api 行数、未决问题（给 W8 的 MIGRATION/CHANGELOG 提示）。
