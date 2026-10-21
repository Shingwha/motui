# W3 交接包（visual and glyph switch）

> 分支 `motui-2/w3-visual` / 起点 `47e3566`（main，W1 + W2a-d 已合并） / 2026-10-21
> 源码/测试/golden 8 个 commit；本文件为最后一个 commit。

## A. 自动事实

### 用例数与门禁真实输出

```text
uv run pytest -q -p no:cacheprovider
897 passed in 10.80s

uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
stream-single:     1.8 ms/frame
stream-split :    12.7 ms/frame
scroll       :     1.1 ms/notch
scroll-long  :     5.1 ms/notch
text-open    :     0.2 ms/frame
table-open   :     0.2 ms/frame
stream-paragraph:     1.6 ms/frame
replay       :   688 ms total
render-hash  : a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379

uv run python -m motui < /dev/null
exit 0，70 行

uv run python -m motui --pages > /tmp/pages.txt
exit 0，4130 行（行数与基线相同；内容按本波视觉计划变化）
```

基线（开工前同一 worktree 实测）：896 passed、golden 58、hash
`f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。

**新 render-hash**：`a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。
897 = 基线 896 + `tests/widgets/test_rows.py` 的 Notice level 参数表新增
`success` 一行；没有删除或跳过基线用例。

### Commit 清单

| commit | 内容 |
|---|---|
| `26a7741` | `theme: ship the Ink & Signal dark theme as the defaults` |
| `5c6adc2` | `widgets: draw the controls and forms from the Glyphs vocabulary` |
| `c5d7d49` | `widgets: draw the list and navigation families from the Glyphs vocabulary` |
| `c09b036` | `widgets: read Borders, glyphs and the syntax group in the data family` |
| `7305bcc` | `interaction: thread the Glyphs vocabulary through find, palette and chrome` |
| `c3dfb7c` | `demo: show the Glyphs vocabulary and the 2.0 role groups` |
| `d2c2a19` | `tests: pin the dark visuals, Glyphs signatures and Border frames` |
| `ac6dc99` | `golden: re-record the 58 topics on the Ink & Signal visual` |
| 本文件所在 commit | `specs: hand off the W3 visual switch` |

### 变更范围 / 禁触审计

`git diff --name-only 47e3566..HEAD` 共 75 个文件（不含本交接包）：

- 根层：`kernel/theme.py`。
- 组件：`widgets/` 下 26 个源文件（含 `markdown/` 4 个、`strip.py`）。
- interaction：`find.py`、`palette.py`、`scrollbar.py`。
- demo：`assets.py` + 7 个 topic。
- 测试：13 个测试文件。
- golden：26 个 topic 文件（58 个全部经 `--update` 重录，另 32 个字节未变）。

零 diff：`kernel/` 其余文件（含 `glyphs.py`、`style.py`、`host.py`）、
`keys/`、`app.py`、`interaction/{focus,gesture,modal,overlays,pointer}.py`、
`widgets/bands.py`、`docs/`、`pyproject.toml`、`uv.lock`、`tools/`、
`tests/golden/README.md`。未 merge/push/tag；golden 只由
`tools/golden.py --update` 写出，没有手改。

## B. 只有存在于脑子里的东西

### T1 默认主题

- 10 个 group 的**字段默认值**现在逐字段等于
  `Theme.from_palette(DARK_PALETTE)`（§3.2），因此
  `Theme() == Theme.dark() == DEFAULT_THEME`。字段默认值直接用
  `DARK_PALETTE.*` 引用（Palette 是 frozen 值），计算型 token 用与
  `from_palette` 相同的表达式，避免两处漂移。
- `Theme.flat()` 原来依赖 `SurfaceStyles()` 的 legacy 默认（全 `NONE`）；
  默认改为暗色后显式传 `base/raised/hover/active/selected=NONE`，否则
  flat 不再是 flat。`flat.text == Theme.dark().text` 仍成立。
- `kernel/theme.py` 不再导入旧 `style.py` 语义常量；旧常量本身保留（W4 删）。
- demo `assets.py` 的三个 THEMES 都补了 `rows.inactive`（与各自的
  `rows.active` 同色），修复 W2b 指出的“自定义主题下 unfocused List 退回
  legacy DIM 背景缺失”问题。
- demo `topics/styling.py` 的 token 表改成 group 路径
  （`content.accent`、`text.faint`、`rows.active`、`chrome.scrollbar` …），
  glyph 表改成 `Glyphs` 字段（`prompt`、`cursor`、`check_on` …），
  `api_line` 改成 2.0 构造。

### T2 构造签名（删除旧逐字形参数）

新增统一参数 `glyphs: Glyphs = GLYPHS`（keyword-only）。删除的旧参数：

| 组件 | 删除 | 现在读取 |
|---|---|---|
| `Checkbox` | `mark_pair` | `glyphs.check_on/off` |
| `Select` | `marker`, `mark_pair` | `glyphs.cursor`, `glyphs.check_*` |
| `RadioGroup` | `empty`, `filled` | `glyphs.radio_on/off` |
| `CheckboxGroup` | `mark_pair` | `glyphs.check_on/off` |
| `List` | `marker`, `more_up`, `more_down`, `mark_pair` | `glyphs.cursor`, `glyphs.more_*`, `glyphs.check_*` |
| `Tree` | `expanded`, `collapsed` | `glyphs.fold_open/closed` |
| `Collapsible` | 模块常量 `OPEN_MARK`/`CLOSED_MARK` | `seat(glyphs.fold_*)` |
| `NavList` | `bar` | `glyphs.rail`（`bar_space` 仍是布局覆盖） |
| `Tabs` / `MenuBar` | `divider` | `glyphs.vertical_rule`，组件自己加两侧空格 |
| `ShortcutBar` | `separator` | `glyphs.separator` |
| `Markdown` | `task_marks` | `glyphs.check_on/off`（`RenderContext.glyphs`） |
| `Diff` | 无旧参数 | `glyphs.diff_add/remove/context` |
| `Table` | `mark_pair` | `glyphs.check_on/off`；新增 `grid: Border \| None` |
| `Dialog` | 旧的 6 元组 `border` | `border: Border \| None` |
| `Panel` | 无旧参数 | 新增 `border: Border \| None`，默认 `glyphs.box` |
| `ProgressBar` / `Slider` / `Spinner` | 无旧参数 | `glyphs.bar_*` / `slider_*` / `spinner` |
| `ScrollView` | 无旧参数 | `glyphs.bar_full/empty` |
| `Scrollbar` | 默认值不再取旧常量 | `track=None -> glyphs.bar_empty`、`thumb=None -> glyphs.bar_full` |

实例内容覆盖按工单保留：`Divider(char=)`、`Input(prompt=)`、
`Scrollbar(track=/thumb=)`。`Input(prompt=...)` 仍可传 `""`；`None` 现在
表示“用 `seat(glyphs.prompt)`”。

`Autocomplete` / `ComboBox` / `ContextMenu` / `prompt_dialog` /
`confirm_dialog` 都透传 `glyphs=`；`Find` / `Palette` 通过 Host 的
`make_input` / `make_autocomplete` 的 `**kwargs` 传给子组件，
**Host 协议本身没有改动**。

### T4 视觉收口（逐条）

- Select description：`text.faint -> text.muted`。
- Divider label：`label_style is None` 时从 `NONE` 改为 `text.muted`。
- Table header：`text.base -> text.muted`。
- List/Tree unfocused cursor：W2b 已走 `rows.inactive`；本波默认主题把它
  变成 `DARK_PALETTE.surface_inactive`（背景带），不再依赖 legacy DIM。
- Notice：删除 `WARNING: `/`ERROR: ` 文本前缀，改为
  `seat(glyph)`：info `i`、success `✓`、warn `!`、error `×`；未知 level
  降级为 info；info 用 `text.base`，其余用 `status.*`；文本本身仍是
  `NONE`。新增 `success` level。
- Markdown：task 用 `check_off/check_on`（`[ ]`/`[x]`）；bullet 列表用
  `glyphs.bullets`（level 0 `•`，level 1+ 因 `_LIST_MAX_LEVEL=1` 取 `◦`；
  `▪` 在词汇表里但当前层级上限不会用到）；ordered list 保留 `N. `；
  quote 用 `glyphs.quote`。
- Input 默认 prompt = `seat(glyphs.prompt)` = `❯ `；Find prompt 同步为
  `find ❯ `；List/Select/Autocomplete/ContextMenu cursor = `→`。
- Slider：`[` + `glyphs.slider_track` 填充 + `glyphs.slider_thumb`（位置随
  `filled`，停在最后一格表示满值）+ `]` + `text.muted` 的数值。轨道预算
  公式（`width - len(suffix) - 2`）和 click 映射**没有改**。
- Scrollbar/ScrollView/Progress：统一 `glyphs.bar_empty`（`░`）/
  `glyphs.bar_full`（`█`）；Scrollbar 的 track/thumb 显式字符串覆盖仍在。
- Checkbox：mark 用 `content.accent`、label 用 `text.base`（显式
  `style=` 仍同时画两者）；hover/focus/disabled band 规则不变。
- Syntax：`_token_styles` 改读 `theme.syntax.*`；plain code 仍是
  `content.code`。

### Border 的落地位置

- `Panel`、`Dialog`、`Table` 的默认框线分别来自 `glyphs.box` / `glyphs.box`
  / `glyphs.grid`，都可显式传 `Border`（`square/rounded/heavy/double/ascii/none`）。
- Table 的规则行现在从 `Border` 取 `top_left/top_tee/top_right/top`、
  `middle_left/cross/middle_right/middle`、`bottom_left/bottom_tee/
  bottom_right/bottom`，单元格两侧取 `left/right`；列预算算法未改。
- Panel/Dialog/Table 的 memo/revision key 都包含 `Border`（frozen/hashable），
  换框线会重绘。

### 测试更新范围

- `tests/kernel/test_theme.py`、`test_theme_contract.py`：legacy 默认断言
  改为暗色断言；`Theme.dark() != Theme()` 改为相等；flat 的 surfaces 用显式
  `NONE` 构造。
- `test_invariants.py` 的 CASES 为新签名补了 `glyphs=`、`Border`、`char`、
  `prompt`、`grid` 等覆盖；矩阵完整性测试仍要求每个公开组件都有工厂。
- 组件测试：List cursor/自定义 glyph、Select/Radio/Checkbox 的 glyphs、
  Input/Find prompt、Notice glyph 前缀、Markdown bullets/tasks、Slider
  字形、ShortcutBar separator、NavList rail、Table hover（现在同时设置
  `rows.hover` 与 `surfaces.hover`）。
- 没有 test 被删除；没有断言被放宽成“只检查不抛异常”。

### 偏差、取舍与已知风险

1. **RadioGroup/CheckboxGroup 的 label 仍是 engaged-row accent**：
   §5 写 mark `content.accent`、label `text.base`，但 W2a 的收口问题只点名
   Checkbox；T4 也未列这两个组件。为保持 W2 行为并缩小本波风险，只拆了
   Checkbox。若 W4 要把 group 的 label 也切到 `text.base`，需重录相关
   golden（文本不变，SGR/hash 会变）。
2. **List counter 仍是 `text.faint`**（W2b 的映射），没有按 §5 改成
   `text.muted`；T4 未列，改它会改渲染字节。
3. **`bands.py` 仍读兼容属性**（`RowBands.from_theme`），Select/表单组仍走
   它；W4 删除兼容属性前必须迁移或删除该文件。
4. **Table hover 兼容桥仍在**：`rows.hover is NONE` 时回退
   `surfaces.hover`。暗色默认下 `rows.hover` 非 NONE，桥自然不触发；
   W4 删兼容层时一并删。
5. **`Theme.notice_levels` 兼容属性仍返回 `WARNING: `/`ERROR: `**；Notice
   已不再读它。W4 随兼容层删除。
6. **旧字形常量仍在**：`kernel/glyphs.py` 的 `CURSOR/MENU_CURSOR/.../
   TASK_DONE`、`kernel/style.py` 的语义常量、`widgets/indicators.py` 的
   `FILL/EMPTY/DEFAULT_FRAMES` 都保留；当前源码没有读取它们（`DEFAULT_FRAMES`
   仍是公开常量）。W4 清理。
7. **`collapsible.OPEN_MARK/CLOSED_MARK` 与 `dialog.BORDER` 已删除**：T2
   明确要求替换这两个模块内字形来源；它们不在 kernel 的保留清单里。
8. **`Find.PROMPT` 常量**改为 `find ❯ ` 且代码实际用
   `f"find {glyphs.prompt} "`；显式改 `glyphs.prompt` 会同时改变 Find 的
   提示。
9. **`Diff.glyphs` 是 property**：赋值会立即重建行（与 `before/after` 的
   setter 一致），避免只改 revision 不重建导致缓存命中旧行。
10. **MenuBar 分隔符的 padding 固定为一个空格**：旧 `divider=" │ "` 可以
    控制整段；现在只通过 `glyphs.vertical_rule` 换字形，两侧空格由组件加。
    T2 的规则如此；需要自定义 padding 的宿主可在 T4 后提出新 API。
11. **Tabs/MenuBar 的 span 表/click 映射没有改**；分隔符仍是 `" rule "`
    三列，所以列偏移与旧默认完全一致。
12. **golden 只有 26/58 个文件字节变化**：golden 是纯文本 dump，主题颜色
    只进 render-hash，不进 golden；变化全部来自字形/文案（见下）。
13. **framebench hash 改变**：主题 SGR 与全部字形改动都会进 hash，这是
    本波唯一允许改渲染字节的预期结果。

## C. 指针

- 工单：`specs/2026-10-21-0856-motui-2-0/03-W3-visual.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §3.2/§4/§5/§7
- 主题：`src/motui/kernel/theme.py`
- 字形/边框：`src/motui/kernel/glyphs.py`
- 组件入口：`src/motui/widgets/`（controls/forms、lists/nav、data/content）
- interaction：`src/motui/interaction/{find,palette,scrollbar}.py`
- 契约测试：`tests/kernel/test_theme.py`、`test_theme_contract.py`、
  `tests/test_invariants.py`
- 视觉门禁：`uv run python tools/golden.py --check`、
  `uv run python tools/framebench.py`
- 新 hash：`a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`
- 起点：`47e3566`；本波 HEAD：本文件所在 commit
