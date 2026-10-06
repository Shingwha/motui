# Spec showcase-redesign · W3 组件展品 B（波次 W3）
> 分支 `sr3-exhibits-b`；前置：**W2 已合并**；深读：`00-overview.md`（设计定稿 B/C/E 节、决策 D7）、
> `ref/capabilities.md`（第 2、4 节：壳与工程性的展示面）。
> **最高约束：`styles` 的主题选择器必须走 `activate()`/`chosen`（不许新加"点击回调"式旁路）；
> `keys` 与 `features` 拆分后各司其职。**

## 目标

`styles`（主题选择器）、`keys`（三张 keymap 表）、`features`（壳的工程性）三页按展品语法重做，
`chat` 页套用语法；把 `features` 拆成 `keys` + `features` 两页（页表 → **11** 页）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| styles 页现状 | `examples/showcase/styles.py`（色卡 + 属性，无主题切换） |
| features 页现状（能力表 + 三张 keymap 表） | `examples/showcase/features.py:28-63` |
| `THEMES` 三个变体 | `examples/showcase/content.py:19-29` |
| `/theme` 命令（循环 + 重建壳与页） | `session.py:313-323` |
| chat 页现状 | `examples/showcase/chat.py` |
| `PageBody.note` 反馈通道（W2 落地） | `examples/showcase/page.py` |

## 工单（按序执行，每项一个 commit）

### T1 `styles` 页：主题选择器

- `try_line("点一个主题名（或 ↑↓ + enter）：整个壳与这一页立刻换肤")`。
- 新增 `Select([Option(name) for name, _ in THEMES])`（label = 主题名），ring = `FocusRing([picker])`；
  宿主在激活后读 `chosen` → **`Showcase.set_theme(index)`**（新方法：设 `theme_index` 并重建 footer
  与当前页——把 `cmd_theme` 的主体抽出来复用，`/theme` 改为"循环到下一个"调用它）。
- 保留色卡与样式属性样本；`api_note`：`Theme` 用 `dataclasses.replace` 派生、
  `Style` 的属性合并（`merge`）各一行。
- 验证：headless 探针激活第 2 个主题 → `session.theme is THEMES[1][1]`，且 dump/渲染的 accent 字节变化（贴输出）。

### T2 `keys` 页（从 features 拆出）

- 新页 `keys`：`header("keys & keymaps", …)` → `try_line("读表；把下面那行复制进你的宿主，就完成一次重绑")`
  → 三张 keymap 表（Input / Editor / Composer，数据源仍是 `DEFAULT_INPUT_KEYMAP` / `DEFAULT_EDITOR_KEYMAP` /
  `COMPOSER_KEYMAP`）→ `api_note`：`field.keymap = {**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}` 与
  "删掉条目 = 键回到宿主"两行。
- 提示/说明里必须包含本组新增的键位事实：`c-n`/`c-p` 翻展品、`tab` 是控件焦点、`c-o` 是窗格。
- 验证：`--pages` dump 的 `/keys` 页含三张表与两行 `api_note` 原文（贴出）。

### T3 `features` 页：从"文字描述"改成"可做的动作"

- 保留能力表但把 "how to see it" 改写成**动作**（如 `press /split, then c-o`、`drag across these rows`、
  `click the tab strip above`），并新增一组"无终端三条命令"（`< /dev/null` piped 回放、`--pages` dump、
  `pytest`/`framebench` 的用途一句话）。`api_note`：`tui.split("vertical", ratios=(2,1))`、`SelectionGesture(tui, on_end=…)`。
- **本页不挂 ring**（没有可聚焦目标）：保持 `focus=None`，但把选择手势与分屏的 TRY 写在 `try_line` 里。
- 验证：dump 的 `/features` 页含新表与 `TRY ▸` 行（贴出）。

### T4 `chat` 页套用语法

- `header` 不变体例；`try_line("在下面输入框里打一句话回车：这一页会用流式回复你")`；
  四段样张各一行 `api_note`（`Message(role, text)`、`ToolBlock(...)`、`EditBlock(...)`、`StatusLine`）。
- 保留"每次打开其他页都会清空 transcript"的既有说明。
- 验证：dump 的 `/chat` 页含 `TRY ▸` 与四行 `API ·`（贴出）。

### T5 registry 与文档

- `registry.PAGES`：新增 `keys`（位置在 `styles` 之后、`features` 之前），描述更新；
  **总页数变 11**（`overview text structure lists fields feedback styles keys features streaming chat`）。
- `README.md` 的 `## The demo` 段同步页表与新键位；`features`/`keys` 两行分开写。
- `script.py`：加一步切到 `/keys` 或 `/features` 的访问（保证 piped 回放覆盖两页）。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **一字不变** `948 passed, 1 skipped`。
2. `demo.py < /dev/null` → exit 0，dump 含 `keys` 表片段；`--pages` → exit 0、**11** 个页头（贴清单）。
3. 主题探针（T1）真实输出：激活前后 `session.theme` 与渲染 accent 差异。
4. `framebench` hash 逐字符一致；`test_readme_examples.py` 6 passed；`src/` 零 diff。
5. 真机项（点主题名换肤的观感）**无法执行** → "lead 终验项"，由探针替代。

## 禁触清单

- `src/`（任何文件）
- `examples/showcase/components.py`（W2 已定稿的四页 + W1 的 text 页）、`session.py` 的 ring/反馈通道
  （W2 定稿；本波只允许新增 `set_theme` 与命令复用）
- `examples/showcase/markdown` 相关（W5 的 streaming 页）
- `specs/`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + 页头清单）/ 主题探针输出 /
偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞：**停下上报，不越界自救**。
