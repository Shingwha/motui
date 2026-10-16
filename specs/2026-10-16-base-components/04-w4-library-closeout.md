# Spec base-components · W4 库收口（波次 W4）
> ✅ 已合并 2026-10-16 @ `bc4-closeout`（tip `03bb662`）→ main `45c751c`；981 passed，root 64 名定稿。
> 分支 `bc4-closeout`；前置：W3。深读：`00-overview.md`（目标 1/3、全局不变量 5）。
> **最高约束：本波把「删完 chat、加完交互原语」之后的库面**定稿**——root/facade 导出、测试 pin、
> DESIGN/COMPONENTS/README 的库章节。**不加新能力，只把 W1–W3 的成果对齐文档与 pin。**

## 目标

1. root `__init__.py` 与各 facade 的 `__all__` 定稿（删 chat 名、加 `Pointer` / 新原语 / `Palette`）。
2. `tests/test_api_root.py` 重 pin；`test_theme.py` / `test_widgets_basics.py` 去 chat 引用。
3. `README.md` 的 **Quickstart / 集成 / 组件表 / Theme / 键位 / 驱动** 库章节按新面重写
   （demo 章节留给 W5）。
4. `docs/DESIGN.md`：hover 从「不做」改成「`Pointer` tier + 1003 开关」；命名表更新。
5. `docs/COMPONENTS.md`：交互表加 `hover` / `child_at`；组件目录删 chat、加新原语；补 dispatch order。
6. `tests/test_readme_examples.py` 覆盖新的 README 代码块。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| root 65 名与模块 docstring | `src/mocode_tui/__init__.py` |
| 各 facade `__all__` 与 pin | `tests/test_api_root.py`（`ROOT_ALL` / `LAYER_ALLS` / `DOWN_LISTED`） |
| README 代码块（被测试执行） | `README.md` 的 `## Quickstart` / 集成段 / Theme / keymap 段 |
| DESIGN 的 hover「不做」与命名表 | `docs/DESIGN.md`（Deliberately out of scope、命名 charter） |
| COMPONENTS 的交互表与组件目录 | `docs/COMPONENTS.md`（Interaction 段、widgets/chat 表） |
| `Themed` 解析规则 | `core/theme.py` |

## 工单（按序执行，每项一个 commit）

### T1 root `__init__.py` + facades：导出面定稿

- root 删：`Composer` / `Transcript` / `StreamHandle` / `Message` / `ToolBlock` / `EditBlock` /
  `SlashPalette`（W3 已从 chat 迁出；若 W3 已删则本波只对账）。
- root 加：`Pointer`（W2） / `Button` / `Checkbox` / `Link`（W2） / `Palette`（W3）；
  `StatusLine` 来源已改 `widgets`。
- `__all__` 按「常量 / 类+函数」分组、组内字典序（现有测试会校验顺序）。
- 模块 docstring 的「四层」叙述更新：`widgets` 段加新原语；顶层加 `pointer.py` tier；
  删除 chat 段。
- `widgets/__init__.py` / `core/__init__.py` 的 docstring 同步（core 补 `Hoverable`/`Container`/`descend`）。
- 验证：`python -c "import mocode_tui; print(len(mocode_tui.__all__))"`；贴最终数与全名清单。

### T2 `tests/test_api_root.py`：最终 pin

- 更新 `ROOT_ALL`（新清单）、`LAYER_ALLS`（`mocode_tui.widgets` 加 `Button Checkbox Link Palette
  StatusLine`；`mocode_tui.keys` 用 `EDITOR_SUBMIT_KEYMAP` 替 `COMPOSER_KEYMAP`；删 `mocode_tui.chat` 整条）、
  `DOWN_LISTED`（删 `mocode_tui.chat.composer`；`core` 段视导出加 `Hoverable` / `Container` / `descend`）。
- 更新硬编码数量注释与断言（`test_root_all_is_the_curated_surface` 的 `len(...) == N`）。
- 跑通 `test_every_pinned_name_resolves...`（root 的每个名字都能在某个 layer 找到同一对象）。

### T3 其它测试去 chat / 对齐行为

- `tests/test_theme.py`：删 `user_bg` / `tool_bg` / `code_bg` / `tones` / `title_tones` 断言，
  加 `hover` 断言。
- `tests/test_widgets_basics.py`：删/改引用 chat 的断言（grep 确认）。
- `tests/test_focus.py`：加「`click` 下钻容器」一条（若 W2 已加则对账）。
- 新增/确认：`tests/test_container_hit.py`（W1）、`tests/test_pointer.py`（W2）、
  `tests/test_widgets_action.py`（W2）、`tests/test_widgets_palette.py` / `test_widgets_statusline.py`（W3）
  都在且全绿。
- 验证：`uv run pytest -q` 全绿；贴完整数字。

### T4 `README.md`：库章节重写（demo 段不动，留给 W5）

- **Quickstart**：换成「基础组件 + `Pointer`/`FocusRing`」的最小 app（无 chat、无常驻输入框即可可验）。
  约束：≤ 30 行、只用 root 公开名、**headless 可执行可断言**（`test_readme_examples.py` 会跑），
  代码块下配一句「这段被 `tests/test_readme_examples.py` 执行」。
- **集成段**：旧「mocode」集成形状（`Transcript`/`Composer`）删除；换成
  「用 `Document` + `Editor` + `tui.add_band(viewport)` 自建外壳」的**文档配方**（W5 会在
  `docs/COMPONENTS.md` 写完整 recipe）——**不指向任何 demo 模式**（demo 只是画廊，无常驻输入框）。
- **组件表**：删 chat 段；widgets 表加 `Button` / `Checkbox` / `Link` / `Palette` / `StatusLine`；
  交互方法表加 `hover` / `hover_at` / `child_at`；`COMPOSER_KEYMAP` 改 `EDITOR_SUBMIT_KEYMAP`。
- **驱动 / 键位 / Theme** 段：同步签名与新名字；`TUI(hover=...)` 写进驱动一览。
- **Package layout**：删 `chat/`，加 `pointer.py` 与 `widgets/{button,checkbox,link,palette,statusline}.py`。
- **What lives where** 表：删 `mocode_tui.chat` 行；`mocode_tui.core` 行加交互协议。
- 其余段落（`The demo` 段、`docs` 链接列表）**留给 W5**；本波若改了 demo 段会与 W5 冲突。
- 验证：`tests/test_readme_examples.py` 全绿（贴数量）。

### T5 `docs/DESIGN.md`

- **命名 charter 表**：`COMPOSER_KEYMAP` → `EDITOR_SUBMIT_KEYMAP`；加
  `hover` / `hover_at` / `child_at` / `descend` / `Pointer` / `Palette` 行。
- **「Deliberately out of scope」**：删掉「no hover」条目，替换为
  「hover 是 `Pointer` tier + 可选 1003，默认关」并交叉引用 COMPONENTS。
- 新增/扩写一节 **「Hover 与指针」**：1002 vs 1003 的事实、为什么默认关、`Pointer` 的
  hover/点击/下钻契约、与 `gesture` 的分工、`descend` 的「上次 render 几何」先例。
- **四层结构图**：顶层加 `pointer.py`；层描述删 chat。
- **非 TTY / 坐标 / 驱动** 段：凡提 `Composer` 的地方改成通用说法。

### T6 `docs/COMPONENTS.md`

- **协议段**：`Component` 之后加 `Hoverable` / `Container` 的说明（与 `Clickable`/`Activable`/`Focusable` 并列）。
- **Interaction 表**：加 `hover(row, col) -> bool`（可选 `hover_at`）与 `child_at(row, col)` 两行；
  写清「容器下钻、叶子派发」「hover 需 `TUI(hover=True)`」。
- **组件目录**：删 chat 表；新增 `Button` / `Checkbox` / `Link` / `Palette` / `StatusLine` 条目
  （`__init__` 草图 + 能力）；`Focus` 段补 hover 与 `Pointer` 的 dispatch order 代码块。
- **build-your-own**：加一个「用 `Container.child_at` 让自定义容器可点」的小节（可选），
  与既有「custom chrome / overlay」并列。
- 验证：文档里的每个名字都能在源码 grep 到。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` 全绿（贴数字 + 与 W3 的差异原因）。
2. `python -c "import mocode_tui as m; print(len(m.__all__)); print(sorted(m.__all__))"`（贴全清单）。
3. `python -c "import mocode_tui.chat"` → `ModuleNotFoundError`。
4. `uv run pytest tests/test_readme_examples.py -q` → 全绿（贴数量；README 新代码块被真实执行）。
5. `git grep -n "Composer\|Transcript\|SlashPalette\|StreamHandle\|ToolBlock\|EditBlock\|Message(" -- README.md docs src tests` → 只剩合法说明（如历史 spec）或为空。
6. `uv run python tools/framebench.py` → hash 是否变化如实报告（W4 只动导出/文档，**不应**变化）。
7. 真机项：无（文档 + 导出）。

## 禁触清单

- `examples/**`（W5 的活；README 的 demo 段也不动）
- W1–W3 已定的实现行为（本波只对齐文档与 pin）
- `core/theme.py` 的字段（W3 已定稿）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + pytest 数）/
root 最终清单与数量 / README 代码块通过证据 / grep 残留学清单 /
framebench hash 结论 / 偏差与取舍 / 未决问题 / 真机手测：无。

遇到阻塞（README 代码块无法 headless 验证、pin 与实现不一致、facade 出现环导入）：
**停下上报，不越界自救**。
