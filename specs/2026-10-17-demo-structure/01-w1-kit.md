# Spec demo-structure · W1 kit 落地（波次 W1）

> ✅ 已合并 2026-10-17 @ `demo1-kit`（tip `54aa390`）→ main `035d783`；1472p/1s，hash 未动。
> 分支 `demo1-kit`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`
> （红线、kit 契约、D2/D3）。
> **最高约束：本波只新增 `kit.py`/`assets.py` 并迁移 `overview`、`text` 两页；
> 其余 10 个页面文件一行不动；golden 与既有断言必须全绿（可见字节只许在
> `overview`/`text` 覆盖的页面上变化——若变了，逐页解释）。**

## 目标

把 demo 的展台语法收进 `demo/kit.py`，并在两页真实用例上验证；建立 `assets.py`
承接 `content.py` 的主题与素材（`content.py` 本波暂留，W2 删除）。

## 背景（锚点，全部已核实）

| 事实 | 位置 |
|---|---|
| 现状骨架：`header` / `try_line` / `section` / `api_note` 四个函数 | `demo/page.py` |
| 现状 pick 读取：`session._read_picks`（含 `BY_NAME` 翻页、`THEME_INDEX` 换肤两个特例）、`session._report(text)` → `body.note(text)` | `demo/session.py:363-388` |
| `PageBody`：blocks / focus / tick / note / enter / leave / modal | `demo/page.py:19` |
| `FocusRing(targets)`：构造即聚焦第一个 target；`handle` 里 `enter` → `activate()` | `interaction/focus.py:45` |
| `Modal.chosen` / `is_open`；`Palette(tui, commands, …)` | `interaction/{modal,palette}.py` |
| 主题变体与素材 | `demo/content.py`（THEMES / fixture_text / blocks_of） |

## 工单（按序执行，每项一个 commit）

### T1 `demo/assets.py`：主题与素材（新文件，纯搬运）

- `content.py` 的 `THEMES`、`FIXTURE`、`FENCE_CHARS`、`fixture_text()`、`blocks_of()`
  原样迁入 `assets.py`（docstring 保留）；`content.py` **本波不动**（W2 才删），
  两文件并存期间 `import` 谁都以行为不变为准。

### T2 `demo/kit.py`：`Action` · `Pick` · `Slot` · `Exhibit` · `Echo`

按总纲「kit 契约」实现，另加：

- `Echo`：自更新的回显行小部件（`Text` 包装，`echo.set(text)`；页面不再手写
  `echo.text = f"…{text.removeprefix('chosen: ')}"`）。
- `Exhibit` 的 `build()` 返回 `PageBody`：`focus=FocusRing([slot.component for slot in 登记且 .focus 过的])`、
  `note=…`（接收 `Pick` 的自有格式化，或裸 `Action.label`）、`tick=…`、`modal=…`。
- `Exhibit`/kit 的 pick 解析（供 session 调用）：
  `resolve_picks(report) -> bool` 语义——扫 `blocks`（页面自持组件列表，无需下钻），
  每个有 `chosen is not None` 的组件读一次、清空，规约成 `Pick(src, action, value)`：
  `Action` → `action.run(session)`；`Option` → 其 `value`（可再是 `Action`）；裸值 → 播报。
  `multi` 选择（`chosen` 是列表）与 `Radio`（label/值）都按此规约处理，**不新加组件子类**。
- **测试**：`tests/test_demo_kit.py`（新）——按行为写：一个 `Action` 被读一次并执行、
  裸值只播报、`resolve_picks` 读后清空、`Echo` 的格式化、`Exhibit.build` 的 ring 顺序。
  4–6 条，不铺方法。

### T3 `overview` 迁 kit（验证 Action 翻页）

- `overview.py` 重写为 kit 形态：索引 `Select` 的每行载荷改成
  `Action(page.name, page.description, lambda s, p=page: s.show(p))`；
  页眉/TRY/正文段落走 `Exhibit`；index 页的说明文字里"eleven labels"改成按
  `len(session.pages)` 计算（或去掉具体数字）。
- `session.py` 本波只加**最小**适配：`_read_picks` 改为优先调 kit 的解析
  （若页面 body 带 kit 解析器），失败回退旧路径；`_report` 接受 `Pick | str`。
  **不得**在本波删旧特例（W3 才拆）。
- 行为验收：`uv run python -m motui --pages` 的 overview 页照旧可玩（replay 走
  rail 点击 + `c-n`），`test_demo_protocol.py` 里 overview 索引点击翻页的断言不红。

### T4 `text` 迁 kit + Spacer 展位

- `content.py` 页（`pages/content.py`）改名 `pages/text.py`（`git mv`，保历史），
  内容迁 kit 形态，页面名 "text"、标题与文案同步；加一个 `Spacer` 展位（layout 家族
  在 text 页只露 Spacer 建行距的用法，一句 api_note）。
- registry：`Page("content", …)` → `Page("text", …)`；`overview` 页对它的引用
  （clicks/replay）同步。
- golden：`content.txt` → `text.txt`（`--update` 同 commit，逐页解释改名与文案变化）；
  `test_demo_protocol.py` 只做跟随改名的最小修补。

## 验收（完成前自测，报告真实结论）

1. `uv run pytest -q` 全绿（贴 passed/skipped；新增 `test_demo_kit.py` 用例数）
2. `uv run python tools/golden.py --check` → 12 页（改名后 12 页）全等
3. `uv run python tools/framebench.py` → render-hash 与基线一致（text/overview 的
   可见字节变化会移动它——若移动，在 commit message 里逐条解释并登记新值）
4. `uv run python -m motui < /dev/null` 与 `--pages` exit 0
5. 全仓 grep：`pages/content` 零命中（`import` 全部走 `pages.text`）

## 禁触清单

`src/motui/demo/pages/` 除 `overview.py`、`text.py`(由 content.py 改名) 外**一行不动**；
`src/motui/{kernel,keys,widgets,interaction,app.py,testing.py}`、
`demo/session.py`（除 T3 的最小适配）、`demo/page.py`、`demo/shell.py`、`demo/script.py`、
`README.md`、`docs/**`、`tools/**`、`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令与输出）/
偏差与取舍 / 未决问题。阻塞即停，不越界自救。
