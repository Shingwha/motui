# Spec demo-structure · W4 notes 页、协议测试重写与文档（波次 W4）

> ✅ 已合并 2026-10-17 @ `demo4-closeout`（tip `eae0ec4`）→ main `ddd9029`；1483p/1s，11 页全等。
> 分支 `demo4-closeout`；前置：W3；深读：`00-overview.md`（D6）、
> `tests/test_demo_protocol.py`、`README.md` 的 demo 段、`docs/COMPONENTS.md` 的
> demo/dispatch 段。
> **最高约束：本波是收尾——不再引入任何行为变化；测试重写只许覆盖"新结构下的同一批
> 行为"，不许因为重写而减少覆盖。**

## 目标

`notes` 页上线（12 页）；`test_demo_protocol.py` 按新结构重写；README/COMPONENTS 的
demo 段对位；golden 定稿。

## 工单

### T1 `pages/notes.py`：怎么读这个 demo

- 内容 = README 的 demo 段 + COMPONENTS 里"如何组装 app"的要点，用 `Markdown`
  渲染（顺带是多段落 Markdown 的展台）；讲清：rail/键盘/鼠标/选择复制/12 页各是什么、
  每页的 TRY 行怎么读、`--pages` 与 piped 回放两种无头用法。
- 注册为第 11 条（`streaming` 之后），`Page.hints` 给 `("q", "quit")` 之类最小集。
- README 的 demo 段末尾加一句：完整读法在 demo 内的 `notes` 页。

### T2 `test_demo_protocol.py` 重写

- 按新 12 页结构与符号锚（W3 助手）重写：页面清单、每页一个代表性的交互断言
  （翻页/换肤/对话框/标记/过滤/搜索/Combo 下拉/复制 toast 等，**沿用旧断言覆盖的行为集**，
  一条不多一条不少）；旧文件里因页面消失而失效的断言删除并在报告里列出。
- 该文件顶部 docstring 更新为新结构说明。

### T3 文档对位

- `README.md`：demo 段（页面清单、快捷键、12 页说明）与 `--pages` 输出对位；
  quickstart 不动。
- `docs/COMPONENTS.md`：涉及 demo 的两处——「Adding a component」类条目里
  "exhibit in the demo"的提法保持；若有页面名清单（grep `streaming`/`chrome` 等词）
  同步为新页名。
- `CHANGELOG.md`：`## Unreleased` 的 Changed 段加一条 demo 重构说明（一句：
  页面重分类为组件族 + 展台语法收进 kit + Action 协议）。

### T4 golden 定稿

- `tools/golden.py --update` 全量重录（12 页，含新 `notes`）；commit message 逐页解释
  （相对 W3 后基线的差异：新增 notes、rail 行序、页名）。
- `framebench` 复核 + demo 三入口（真实终端手测由 lead 收尾）。

## 验收

1. `uv run pytest -q` 全绿（贴 passed/skipped，并列出重写后该文件的用例数与旧数对比）
2. `uv run python tools/golden.py --check` → 12 页全等
3. `uv run python tools/framebench.py` → hash 登记
4. demo 两入口 exit 0；`--pages` 含 `notes`
5. README 的页面清单与 `--pages` 实际输出一致（贴对照）

## 禁触清单

`src/motui/{kernel,keys,widgets,interaction,app.py,testing.py}`、`demo/{kit,page,session,script,shell,assets}.py`
（只读）、`demo/pages/**` 除 `notes.py`(新) 与文档性改字、`tools/**` 除 golden `--update`、
`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
