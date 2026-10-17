# Spec demo-structure · W2 页面迁移与重分类（波次 W2）

> ✅ 已合并 2026-10-17 @ `demo2-pages`（tip `272c9f2`）→ main `c656e2a`；1472p/1s，10 页重录。
> 分支 `demo2-pages`；前置：W1（kit 已落地并验证）；深读：`00-overview.md`
> （页面映射表、D1/D2/D3/D5）、`demo/kit.py`（W1 交付的真实 API）。
> **最高约束：页面内容按映射表搬迁重分类；页面级路由胶水（chrome 的 `Trigger`、
> input 的 `_ComboHost`、modal 的 `Trigger`、styles 的特例）全部改走 kit 的 Action/Slot；
> 库本体零改动。**

## 目标

9 个页面迁移到 kit 形态并完成重分类，registry 收敛为 10 页 + 每页 hints；
删除 `content.py`（素材已入 `assets.py`）。

## 工单（按序执行，每项一个 commit）

### T1 `layout` 与 `actions`

- `pages/layout.py`：按现内容迁 kit；从 feedback 页收 **StatusLine** 展位；
  Notice 展位去留照旧（Notice 属 decor，`layout` 页保留一个三档展位即可）。
- `pages/action.py` → `pages/actions.py`（`git mv`）：收 **Checkbox**（原 choice 页）
  与 **Slider**（本页原有）同页，三段各自 api_note；`Slider` 的 `activate` 播报走
  kit（值是数字，用 `spoken`/note 格式化，不要新子类）。

### T2 `forms`（input + choice 并合）

- 新 `pages/forms.py`：吸收 `pages/input.py` 全部展位（Input、Editor（含点击落光标）、
  ComboBox + 下拉 Modal、Autocomplete）与 `pages/choice.py` 主体（Select 窗口、
  Radio、CheckGroup、`Select(commit=True)`）；Checkbox 让位给 actions 页（删除该展位）。
- ComboBox 的 `_ComboHost` 胶水改走 kit：`Slot` + `Action`（打开/关闭下拉的动作），
  下拉的 `Modal` 由页面在 `build()` 里登记 `modal`；**不改组件**。
- 页的 hint 项（如 `("c-o", "pane")` 之外的表单键）写进 `registry.py` 的 `Page.hints`。

### T3 `views`

- `pages/data.py` → `pages/views.py`（`git mv`）：内容（Table/List/Tree、space 标记、
  `c-t` 过滤、`sort_by` 选择器）迁 kit；`sort:`/`filter` 的载荷升为 `Action`。
- `c-t` 的树过滤维持现状（session 通用键，W3 再改为观察者形态）；本页的
  `space` 标记行为保持。

### T4 `modals` 与 `shell`

- `pages/modal.py` → `pages/modals.py`：`Trigger` 子类删除——三个触发按钮改由 kit 的
  `Action` 表达（打开哪个对话框是数据）；Palette 展位从 chrome 页迁入；
  `leave` 的 detach 走 `Exhibit` 的 modal 登记。
- `pages/chrome.py` → `pages/shell.py`：吸收 feedback 的 **Toasts/Tooltip** 展位与
  session 的 **Find/selection** 说明；保留 panes/Scrollbar/Stats/探针；Palette 移出。
  `enter/leave` 的开合 pane 行为保留（它们是页面 hook，不是路由胶水）。

### T5 `themes` 与收口

- `pages/styles.py` → `pages/themes.py`：选择器载荷升 `Action`（`run` 里
  `session.set_theme(i)`），**session 的 `THEME_INDEX` 特例本波不删**（W3），
  但页面不再依赖它；色板/属性表照旧。
- `registry.py`：`PAGES` 收敛为 10 条（顺序：overview, text, layout, actions, forms,
  views, modals, shell, themes, streaming）；每页 `hints` 填入；页数注释同步。
- `pages/feedback.py`、`pages/input.py`、`pages/choice.py`、`pages/data.py`、
  `pages/modal.py`、`pages/chrome.py`、`pages/styles.py`、`pages/action.py`、
  `demo/content.py` **删除**（内容已全部落位；全仓 grep 零残留）。
- `streaming.py` 的 import 改 `assets`（其余不动）。
- golden：**12 页全量重录**（页面重分类 + 页名变化），同 commit 逐页解释；
  `test_demo_protocol.py` 做跟随改名与锚点重定位的最小修补（整体重写留 W4）。

## 验收

1. `uv run pytest -q` 全绿（贴 passed/skipped）
2. `uv run python tools/golden.py --check` → 新 11 页（`notes` 未建）全等
3. `uv run python tools/framebench.py` → hash 变化逐条解释并登记新值
4. demo 两入口 exit 0；`--pages` 页面清单 = 新 10 页名（`notes` 除外）
5. grep 零残留：`pages.{content,input,choice,data,modal,chrome,styles,action}\b`、
   `demo.content`

## 禁触清单

`src/motui/{kernel,keys,widgets,interaction,app.py,testing.py}`、`demo/kit.py`（只读，
若确需扩展 API 在报告里提出、由 lead 裁决）、`demo/page.py`、`demo/session.py`
（除最小改名适配）、`demo/script.py`（同上）、`demo/assets.py`、`README.md`、`docs/**`、
`tests/golden/**` 除 `--update` 产物、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论 / 偏差与取舍 / 未决问题。
