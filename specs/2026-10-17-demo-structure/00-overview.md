# Spec demo-structure · 总纲（demo 的重分类、展台语法与 action 协议）

> 操作启动日 **2026-10-17**（组内 slug `demo-structure`）。
> 基线：`main` @ `1f5aa00`。**门禁基线（lead 已实测）**：`uv run pytest -q` =
> **1466 passed / 1 skipped**；`tools/golden.py --check` = 12 页全等；
> `tools/framebench.py` render-hash = `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`；
> demo 两入口 exit 0。版本**不 bump**。

本组只动 `src/motui/demo/**` 与它的门禁（golden 12 页、`tests/test_demo_protocol.py`）
及 README/COMPONENTS 里的 demo 段：**12 页重分为 10 页、每页骨架收进 `demo/kit.py`、
页面专属的路由胶水从 session 收回到页面（Action 协议）、replay 脚本改符号锚**。
库本体（`kernel/` `keys/` `widgets/` `interaction/` `app.py` `testing.py`）**一行不动**。

## 红线（每波适用）

1. **不新增冗余测试**：`test_demo_protocol.py` 按新结构**重写而非叠加**；页面行为由
   golden + demo 回放覆盖的部分不再手写断言。
2. **golden 重录必须逐页解释**（commit message）；重录与改动同 commit。
3. 每个 commit 独立过门禁（`pytest` + `golden --check` + `framebench` + demo 两入口）。
4. 写入范围外零 diff；禁触清单逐波写明；越界即停。
5. agent 不 merge / 不 push / 不 checkout main / 不碰主检出与其他 worktree；spec 归 lead。
6. 文件级对应关系沿用「one source module, one test file」；demo 的测试就是
   `test_demo_protocol.py`。

## 目标结构

```
src/motui/demo/
├── kit.py            ★新  Exhibit · Slot · Action · Echo · Pick（展台语法与动作协议）
├── page.py                 Page · PageBody（+ Page.hints）
├── assets.py         ★新  主题变体（原 content.py 的 THEMES）+ Markdown 素材读取/切块
├── fixture.md              原样
├── pages/
│   ├── overview.py         索引（改走 Action）
│   ├── text.py       ★新  Text · Markdown · Diff · Spacer        （原 content）
│   ├── layout.py          Row Column Padding Panel Divider Collapsible StatusLine
│   ├── actions.py    ←改名 Button Link Checkbox Slider
│   ├── forms.py      ★新  Input Editor ComboBox Autocomplete Select Radio CheckGroup
│   ├── views.py      ←改名 Table List Tree                        （原 data）
│   ├── modals.py     ←改名 Dialog Modal Palette Prompt             （原 modal）
│   ├── shell.py      ←改名 panes Scrollbar Toasts Tooltip Stats Find selection 探针（原 chrome）
│   ├── themes.py     ←改名 主题选择器 + 色板                        （原 styles）
│   ├── streaming.py       原样（import 改 assets）
│   └── notes.py      ★新  怎么读这个 demo（README 的 demo 段搬进来）
├── registry.py            PAGES 10 条 + 每页 hints
├── script.py              replay：符号锚
├── shell.py               原样（除 hints 数据源）
├── session.py             瘦身：零页面特例
└── __init__.py            原样
```

**页面映射（拍板）**

| 新页 | 内容 | 来源 | 变化 |
|---|---|---|---|
| overview | 索引 | 原样 | 索引行改 `Action(session.show)` |
| text | Text Markdown Diff Spacer | 原 `content` | 改名 + 加 Spacer 展位 |
| layout | Row Column Padding Panel Divider Collapsible **StatusLine** | 原 `layout` + feedback 的 StatusLine | 收 StatusLine |
| actions | Button Link **Checkbox** **Slider** | 原 `action` + choice/action 的 Checkbox、Slider | 收两个动作件 |
| forms | Input Editor ComboBox Autocomplete **Select Radio CheckGroup** | 原 `input` + `choice` 的主体 | 两页并合 |
| views | Table List Tree | 原 `data` | 改名 |
| modals | Dialog Modal **Palette Prompt** | 原 `modal` + chrome 的 Palette | 收 Palette |
| shell | panes Scrollbar **Toasts Tooltip Stats Find** selection 探针 | 原 `chrome` + feedback 的 Toasts/Tooltip + session 的 Find/selection | 收浮层与框架机制 |
| themes | 主题选择器 + 色板 | 原 `styles` | 改名 |
| notes | demo 读法 | README/COMPONENTS 的 demo 段 | 新增 |

`input` / `choice` / `data` / `content` / `styles` 五个旧页名从 registry 移除；
`Page.hints` 每页自带（底部提示条随页切换）。

## kit 契约（拍板，执行时不得再改形状）

### `Action` —— 动作协议（session 零特例的关键）

```python
@dataclass(frozen=True)
class Action:
    """A pick that says what it does: the demo's one action vocabulary.

    A page hands an ``Action`` to a component as the *payload* of the row
    it belongs to (an ``Option``'s value, a ``Radio`` label, a
    ``Markdown`` ``todo:`` payload...).  The session reads the pick and
    runs it with itself: ``run(session)``.  ``id`` is the row's identity
    in the inventory (the old payload string); ``label`` the text a report
    prints; ``run`` the effect, or ``None`` for a pick that only reports
    itself.

    The demo's routing is therefore data: a page that wants a row to open
    another page writes ``Action(repr(page.name), page.name,
    lambda s: s.show(page))`` and the session needs no knowledge of it.
    """

    id: str
    label: str
    run: Callable[["Session"], None] | None = None
```

- `Pick`（kit 内的值）：`source`（扫出这个 pick 的组件）、`action`（`Action | None`）、
  `value`（原始 chosen）。旧字符串载荷（`"sort:2"` 等）统一升为 `Action`；
  `Radio` 的 label 值、`Select` 的 `Option.value` 可以是 `Action` 或裸 `str`，
  裸值只播报。
- **部件不必换类**：`Button`/`Checkbox`/`Slider`（chosen 是 `True`/新状态/数值）与
  带 value 的部件都能被 kit 解析——`Exhibit` 提供 `spoken(component, fmt)` 一类的
  绑定（实现细节归 W1，行为见验收）。

### `Slot` —— 一个展位

```python
@dataclass
class Slot:
    """One exhibit's component and what its pick means."""
    component: Component
    action: Action | None = None      # fallback when the component carries none
    note: str = ""                    # a one-line report prefix ("shipped", ...)
    def focus(self) -> Slot           # 登记进页面的 FocusRing
    def hint(self, text: str) -> Slot # component.hint = text（Tooltip 协议）
```

### `Exhibit` —— 一页的展台（页面骨架的唯一实现）

```python
class Exhibit:
    def __init__(self, session, *, title: str, blurb: str, try_text: str, echo_label: str) -> None
    def section(self, label: str) -> None                    # 分隔规则
    def show(self, component, *, note=None, action=None, hint=None, api: str = "") -> Slot
    def text(self, text: str) -> Component                   # 一段灰色说明（dim）
    def watch(self, fn) -> None                              # 每轮 pick 解析后调（tick 的页面用）
    def build(self) -> PageBody                              # 收口：ring/note/tick/modal
    blocks: list[Component]                                  # 组装顺序
```

- `show()` 依次追加 `component`、可选 `api_note`，把 `note`/`action`/`hint` 记进 `Slot`，
  返回 `Slot` 供 `.focus()` 串联；`page(session)` 的结尾一律 `return exhibit.build()`。
- **pick 读取**由 kit 提供（`Exhibit.resolve_picks(report)` 之类）：扫 `blocks` 中所有
  带 `chosen` 的组件（含 Container 下钻不需要——页面直接持有组件），非 `None` 即读一次并清空；
  `Action` → `action.run(session)`（`run is None` 只播报）；裸值 → 播报。
- **`report`（session 侧）改成结构化**：`session.report(pick)` 显示 toast，
  并调用页面 `note(Pick)`（不再是拼好的字符串；页面自己格式化）。旧
  `"chosen: 'x'"` 字符串约定随之消失。
- `Exhibit` 还负责：`Enter` 的通用键绑定（`enter` → 聚焦部件的 `activate`，由
  ring 现有路由担任，kit 不重复）、以及 `modal` 的登记（页面把打开的 `Modal` 交给
  `exhibit.modal = m` / `build()` 转发）。

### `Page.hints`

`Page(name, description, build, hints=())`：hints 是 `(key, label)` 元组，随页切换
重建底部提示条（`session.show` 时；全局键 `c-n/c-p`、`tab`、`q` 由 session 追加）。

## 波次表（严格串行；每波一个 agent）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | `kit.py` 落地 + `overview` 与 `text` 两页迁 kit（新旧并存，其余页不动） | `demo/kit.py`(新) `demo/pages/{overview,text}.py` `demo/assets.py`(新) `demo/registry.py` | — |
| W2 | 9 页迁移 + 重分类：`text/layout/actions/forms/views/modals/shell/themes` 就位，删旧页名，registry 10 条 + hints | `demo/pages/**` `demo/registry.py` `tests/golden/pages/*.txt` | W1 |
| W3 | session 瘦身（零页面特例）+ `script.py` 符号锚 + 每页 hints 生效 | `demo/session.py` `demo/script.py` `demo/shell.py` | W2 |
| W4 | `notes` 页 + `test_demo_protocol.py` 重写 + README/COMPONENTS 的 demo 段 + golden 定稿 | `demo/pages/notes.py`(新) `tests/test_demo_protocol.py` `README.md` `docs/COMPONENTS.md` `tests/golden/**` | W3 |

> 说明：W1 保持 golden 与旧断言全绿（新页只在 kit 落地处引入，旧页原样）。
> W2 起 golden 允许重录（页面重分类必然搬字节），但 `test_demo_protocol.py` 的**整体重写**
> 留到 W4——W2/W3 对该文件只做「跟随改名的最小修补」（import、页面名、锚点），
> 每次修补在报告里列出改了什么、为什么不能延后。

## 决策登记（拍板）

- **D1 页面 = 组件族**，10 页见上表；Checkbox 与 Slider 归 `actions`，StatusLine 归
  `layout`，Palette 归 `modals`，Toasts/Tooltip/Find/selection 归 `shell`。
- **D2 展台语法只住 kit**：`header`/`try_line`/`section`/`api_note` 四个旧函数从
  `page.py` 移除，由 `Exhibit` 接管（页面不再手拼 `[header(...), try_line(...), …]`）。
- **D3 Action 是数据不是类层次**：不做 `ActionButton` 之类子类；页面给载荷、kit 跑动作。
- **D4 session 零页面特例**：`BY_NAME` 翻页、`THEME_INDEX` 换肤、`_cycle_tree_filter`、
  `_mark_cursor_row` 的树过滤与标记改由页面的 Action/`watch` 承担；`space` 标记键
  与 `c-t` 槽位由 session 保留为**通用**键（有 `toggle()`/观察者的页面才响应）。
- **D5 提示条随页**：`Page.hints` 数据源；session 不再持有唯一一份 `HINT_ITEMS`。
- **D6 sponsor 文档落 demo**：`notes` 页内容来自 README/COMPONENTS 的 demo 段（搬入后
  原文保留一句指向）。
- **D7 不动库**：本组任何改动不许落进 `src/motui/{kernel,keys,widgets,interaction}`、
  `app.py`、`testing.py`；`chrome.py` 已不存在（历史）。
