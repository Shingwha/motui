# Spec choice-architecture · W2 widgets 归并重构（波次 W2）

> 分支 `arch2-widgets`；前置：W1（已合并，`kernel/cursor.py` 与 `kernel/mark.py` 可用）；
> 深读：`00-overview.md`（红线、删除清单、D1–D6、D9）、`docs/DESIGN.md` 的「naming charter」
> 与「deliberately out of scope」两节、`docs/COMPONENTS.md` 的组件目录两表。
> **最高约束：已存在组件的渲染输出除本单逐条列明的变化外，一个字节都不许动；demo 与
> `motui/chrome.py` 本波禁触（它们的重做在 W3/W4）。**

## 目标

把 raw widget 层收成 8 个族文件（删 13 个碎文件），`Select` 收成一个基类表达
`Autocomplete`/`Radio`/`CheckGroup` 三个变体，新增 `Dialog`/`Confirm` 纯组件；
测试按同一对应关系归并；公开门面（widgets `__all__`）与 `docs/API.md` 同步。

## 现状（全部已核实，直接照做）

- `widgets/choice.py`：`Option` · `Select`（游标/窗口/描述列/`chosen`）· 旧 `Confirm`（**删**）。
- `widgets/radio.py`：`Radio`（clamped 游标、选中即写 `chosen`、`(•)` 标记、label 可直接是值）。
- `widgets/autocomplete.py`：`Autocomplete(Select)`，覆写 `_rows()` 为过滤结果。
- `widgets/input.py` `widgets/editor.py` `widgets/field.py`：`Input` / `Editor` 均为 `_TextField` 子类，
  `_TextField` 持 `TextBuffer`、焦点/悬停渲染、行缓存。
- `widgets/button.py` `checkbox.py` `link.py`：三个动作原语，各自解析 hover/focus 样式。
- `widgets/statusline.py` `shortcutbar.py`、`decor.py` 的 `Notice`。
- `widgets/progress.py` `spinner.py` `slider.py`。
- 菜单窗口算术已抽到 `kernel/cursor.py`（W1）：`CursorWindow(index, count, cap, center)`。

## 工单（按序执行，每项一到两个 commit；每步之间跑 `uv run pytest -q`）

### T1 `widgets/action.py`：`Button` · `Checkbox` · `Link` 合并

- 新文件合并三源文件；**公共 API 与渲染逐字节不变**（签名、默认值、`chosen` 语义、
  `hint`、`cursor_shape` 列为空等，全部照旧）。
- 三处重复的「已解析样式 + focused/hover 合并」逻辑提成一个模块级私有助手
  （如 `_band(base, focused, hover, focus_style, hover_style)`），三个类共用；
  docstring 保留原有契约文字（可压掉重复段）。
- 删 `button.py` / `checkbox.py` / `link.py`；`widgets/__init__.py` 改 import。
- 测试：`tests/test_widgets_action.py` 只改 import 来源，断言不动。

### T2 `widgets/choice.py`：`Select` 基类 + 三个变体（含旧 `Confirm` 之死）

**`Select` 新签名**（保留现在全部参数，新增四个）：

```python
Select(
    options: Sequence[Option] = (), *,
    title: str = "", max_rows: int | None = 8,
    wrap: bool = True,          # 菜单语义：环绕（False 钳制，数据视图）
    marker: str = MARKER,       # 光标行前缀
    commit: bool = False,       # False：只有 activate 写 chosen；True：move/click/activate 都写
    multi: bool = False,        # True：Toggle 语义（双态标记），chosen 携带被标记项列表
    marked: Iterable[int] = (), # multi 的初始标记行（data-row 序号）
    window: bool = False,       # True：max_rows 语义从「顶挂」换成「居中」(转交 CursorWindow(center=True))
    # …以下照旧：focused / label_style / selected_style / description_style /
    #   title_style / theme
)
```

- **窗口算术改调 `CursorWindow`**（顶挂默认；`window=True` 时居中），删掉 `_visible_range`
  的手写体。行为与现在**逐字节等价**（W1 已把两套算术逐条钉进测试）。
- **`commit=True`**：`move`/`click` 一旦让选中行变化，就把该行写进 `chosen`（`Option`）；
  `activate` 照旧。`commit=False` 时现有行为不动（`move` 清 `chosen`）。
- **`multi=True`**：`marked` 是公开的 `MarkSet` 属性；`chosen` 变为
  `list[object]`（被标记项按行序的**值**；`Option.value` 为 `None` 时取 label 本身）或 `None`；
  `toggle()` 翻转光标行标记、重算 `chosen` 并返回是否有变化；`move`/`click` 不写 `chosen`；
  `activate()` 等价于 `toggle()`（Toggle 语义，D1）。渲染：标记行在 label 前插
  `mark_prefix`（`kernel/mark.py`，`"[x] "`/`"[ ] "`，三列），光标行仍带 marker + 高亮。
- **`Autocomplete`** 不动语义，只跟随基类签名（它是 `_rows()` 覆写，窗口经基类走 `CursorWindow`）。
- **`Radio` 变体**（同名保留，`widgets/__init__.py` 导出不变）：

  ```python
  Radio(labels, *, index=0, label_style=None, selected_style=None,
        hover_style=None, focus_style=None, theme=None, focused=False)
  ```

  语义 = `Select` 之上：`wrap=False, commit=True, marker="(•)"`；label 为 `str` 时值取 label，
  为 `Option` 时值取 `option.value`（现有两态支持保留）；`move` 钳制、点选即写 `chosen`、
  `activate` 返回 True 并把当前选择写入（有项时）。渲染保持现有 `(•)` 行与
  `selected_style`（默认 `accent`）、`focus_style`（默认 `cursor`）的现行字节。
- **`CheckGroup`（新）**：

  ```python
  CheckGroup(labels, *, marked=(), index=0, label_style=None,
             selected_style=None, hover_style=None, focus_style=None,
             theme=None, focused=False)
  ```

  `multi=True, wrap=False, commit=False` 的 `Select` 预置；标记行前缀 `mark_prefix`；
  `chosen` = 被标记值列表（无标记为 `None`）。
- **旧 `Confirm` 的删除延后到 T4 同一个 commit**（新 `Dialog`/`confirm_dialog` 落地时一起删，
  中间任何 commit 不许出现「demo 引用已删名字」的断档）。
- 删 `widgets/radio.py`；同步 `widgets/__init__.py`、`tests/test_api_root.py` 的 widgets 名单。
- 测试：`tests/test_widgets_choice.py` 吸收 `tests/test_widgets_forms.py` 里的 Radio 用例，
  删 `test_widgets_radio` 相关旧文件（若与 forms 重叠则并进去）；新增 `CheckGroup` 与
  `commit` 两态、`window=True` 居中的行为断言（**按行为加，别逐方法铺**）。
  `tests/test_widgets_forms.py` 保留 Slider 等其余用例。

### T3 `widgets/textfield.py`：`Input` · `Editor` 合并 + `mask`

- 三个源文件（`field.py` 的 `_TextField`、`input.py`、`editor.py`）合成一个模块；
  `Input` / `Editor` 公共 API 与渲染**逐字节不变**；`_TextField` 保持私有名。
- **新增 `mask` 参数**（`Input` 与 `Editor` 都加，默认 `""` = 不掩码）：非空时，行渲染把每个字符
  替换为 `mask` 的首字符（`•` 一类，按 `visible_width` 计一列；`mask` 里的宽字符按自身宽度
  重复填满原单元格），**光标所在单元格保持可见**（block cursor 照常盖在该字符上）；
  caret 几何（`cursor_position`、`click`）以掩码后宽度计。`text` 属性仍是明文；
  undo/redo/选区/粘贴全部照旧；`mask` 是构造参数（不做动态 setter）。
  揭示/掩码切换属于宿主用 `text` 自绘——**不做**，写进 docstring 的「deliberately not」一句。
- 删 `field.py` / `input.py` / `editor.py`；`widgets/__init__.py` 与全仓 import 同步
  （含 `interaction/search.py`、`widgets/palette.py` 的 `from .input import Input` 改为
  `from .textfield import Input`；**这两个文件只在 import 行动**）。
- 测试：`tests/test_widgets_editing.py` 只改 import；mask 断言 2–3 条（渲染掩码、光标可见、
  `click` 几何）加在同一文件。

### T4 `widgets/dialog.py`：`Dialog` + `confirm_dialog`（纯组件，无 driver）

**同一个 commit 里删旧 `Confirm` 并把它在 demo 的用法迁到新名字**（见 T6 的最小迁移说明），
demo 的 `script.py` 回放锚点若因此移动，同 commit 修。

模块只 import kernel（`Line/Segment/Style`、`Themed`、`Text`、`visible_width`）与
`widgets/action.py` 的 `Button`。**不 import app/screen/frame**。

```python
@dataclass(frozen=True)
class ButtonSpec:
    label: str
    value: object = None
    style: Style | None = None        # 基础带
    hover_style: Style | None = None
    focus_style: Style | None = None
    danger: bool = False              # True 时基础带 = theme.error，危险按钮

class Dialog(Themed):
    def __init__(
        self, title: str, body: Component, buttons: Sequence[ButtonSpec | tuple | str],
        *, danger: bool = False, width: int | None = None,
        align: str = "center",                  # 按钮行对齐：center | right
        border: tuple[str, str, str, str, str, str] | None = None,
        border_style: Style | None = None,      # 默认 theme.border；danger 时 theme.error
        title_style: Style | None = None,       # 默认 theme.heading
        shade: bool = True,                     # box 行末补空格成实心矩形
        theme: Theme | None = None,
    ) -> None: ...

    # 状态与协议
    index: int                      # 按钮游标（clamp 赋值）
    focused: Button | None          # 当前聚焦按钮
    chosen: object | None           # 一次性结果：host 读一次后置 None
    def handle(self, event: Key) -> bool
    def click(self, row: int, col: int) -> bool
    def render(self, width: int) -> list[Line]
    def revision(self) -> object    # 行缓存的快照（按钮游标/聚焦/body 的行身份）
```

**按钮归一化**：`str` → `ButtonSpec(label)`；`tuple` → `(label, value)` 或
`(label, value, style)`；`ButtonSpec` 原样。内部为每个 spec 造一个 `Button`
（`theme` 透传，`style`/`hover_style`/`focus_style` 解析同 `Button` 的既有约定），
游标与 `focused` 只驱动这些 `Button` 实例的 `focused` 属性。

**默认焦点规则（D3）**：`danger=True` 时默认聚焦**最后一个非危险按钮**（通常是取消）；
否则聚焦第一个。`Escape`：写 `chosen=None` 并返回 True（取消）。`Enter`：把聚焦按钮的
value 写进 `chosen`（危险按钮也允许——键盘规则是不默认聚焦，不是禁用）并返回 True。
`tab` / `shift+tab`（事件名 `s-tab`）/ `left` / `right`：在按钮间移动游标（**clamp 不环绕**，
两个按钮的对话框里就是左右换位），返回 True。`Dialog.handle` 只认这些键；其余一律 False
（body 是宿主的事，见 W3 的 `Modal` 里 body 优先路由）。

- **渲染构成**（全部可覆盖，D5）：宽度 = 参数 `width` 或默认（`render(width)` 的入参 `width`
  按 `min(72, max(24, width * 3 // 5))` 取盒宽，再 `min(盒宽, 入参)` 钳制，保证永不超过入参）；
  顶边 `┌─ title ───┐`（标题嵌进边框、两端各留一空格；标题无则纯边框；超宽则省略号）；
  正文每行 `fit(内宽)` 后两头补空格（`shade=True` 时右端补到实宽）；按钮行把每个
  `Button` 的 `Line` 用空格拼接后整体在 `align` 下居中/右对齐；底边 `└─…─┘`。
  边框字符用 `border` 参数（默认 `(┌, ┬?…)` 见下）。
- **`border` 参数形态**：六字符元组 `("┌", "┐", "└", "┘", "─", "│")`（默认值即此），
  沿用 `Panel` 的单线框语汇。
- **`Confirm`（新，薄包装）**：

  ```python
  def confirm_dialog(
      message: str, *, danger: bool = False,
      confirm_text: str = "Yes", cancel_text: str = "No",
      theme: Theme | None = None,
  ) -> Dialog
  ```

  返回 `Dialog(title="", body=Text(message), buttons=[ButtonSpec(confirm_text, True),
  ButtonSpec(cancel_text, False, danger_side…)], danger=danger, theme=theme)`：
  危险时**取消按钮**不加 danger 色、确认按钮用 `danger=True` 的 error 带；
  明文默认沿用旧 `Confirm` 的 `"Yes"`/`"No"`（文字高度可定制是硬要求）。
- `widgets/__init__.py` 导出 `ButtonSpec` `Dialog` `confirm_dialog`（widgets 层名字，
  不进根门面）；`tests/test_widgets_dialog.py`（新，纯渲染 + 键盘语义：默认焦点两态、
  Esc/Enter 写值、方向键换位、标题嵌入与超宽省略、`shade` 关闭时行末无填充、
  自定义边框字符与样式生效）。**不写重复的 happy-path 铺陈。**

### T5 `widgets/rows.py` + `widgets/indicators.py`：两个小合并

- `rows.py`：`StatusLine`（原 statusline.py）+ `ShortcutBar`（原 shortcutbar.py）+
  `Notice`（从 decor.py 迁出，`__all__` 与 import 同步）。三者渲染逐字节不变。
- `indicators.py`：`ProgressBar`（原 progress.py）+ `Slider`（原 slider.py）+
  `Spinner`（原 spinner.py）。渲染逐字节不变。
- `decor.py` 只留 `Panel` · `Divider` · `Collapsible`；删对应旧文件。
- 测试：`tests/test_widgets_statusline.py` 并入 `rows` 的族文件（可改名
  `tests/test_widgets_rows.py`）；`tests/test_widgets_forms.py` 的 Slider 与
  action 页的 Progress/Spinner 断言按新 import 归位；**只改 import 与文件归属，
  断言内容不重写**。非交互控件不需要新增测试。

### T6 门面与文档同步（本波收尾 commit）

- `src/motui/widgets/__init__.py`：新 import 面；`__all__` 收敛为
  `Autocomplete Button ButtonSpec Checkbox CheckGroup Collapsible Column Confirm
  Dialog Diff Divider Editor Input Link List Markdown Notice Option Padding  Palette
  Panel ProgressBar Radio Row Select ShortcutBar Slider Spacer Spinner StatusLine
  Table Tabs Text Tree TreeNode confirm_dialog`（`Palette` 仍在这，W3 才迁走；
  顺序按文件里的常量/类/函数分组习惯排列）。
- `tests/test_api_root.py`：`LAYER_ALLS["motui.widgets"]` 与 `DOWN_LISTED["motui.widgets"]`
  重钉（`CheckGroup/Dialog/ButtonSpec/confirm_dialog` 进 LAYER_ALLS 或 DOWN_LISTED 按
  其出生地）；`SHED` 的 42 与 root 31 两个计数若因本波而变，**改计数时在 commit message
  里说明原因**。根门面本波不动（`Confirm` 不在根）。
- `tools/apidoc.py --write` 重生成 `docs/API.md`（同 commit）。
- demo 引用：`src/motui/demo/pages/choice.py` 与 `script.py` 里的 `Confirm` 用法，
  本波只做**最小迁移**（改成 `from motui.widgets.dialog import confirm_dialog` +
  一个不含 driver 的 `Dialog` 展示），行为等价、不重建页面——W4 再重做演示。
  迁移后 `golden.py --update` 重录并按红线解释每一页变化（若确实变了）。
- `docs/COMPONENTS.md` 的两张组件目录表里涉及本波名字的行**就地更新**（路径与签名），
  全篇重写留给 W4。

## 验收（完成前自测，报告给真实结论）

1. `uv run pytest -q` 全绿（贴 passed/skipped；基线 1422/1，本波净增用例数要能对上）
2. `uv run python tools/golden.py --check`：11 页（或重录后的新基线）全等；
   若重录，`git show --stat` 证明 golden 与代码同 commit
3. `uv run python tools/apidoc.py --check` → matches（170 或更新后的条目数）
4. `uv run python tools/framebench.py`：render-hash 若变，必须在 commit message 里逐条解释
   （理论上 W2 除 demo 最小迁移外不应变）
5. `uv run python -m motui < /dev/null`、`uv run python -m motui --pages` 均 exit 0
6. 全仓 `grep -rn "from .input import\|from .editor import\|from .field import\|widgets.radio\|widgets.statusline\|widgets.shortcutbar\|widgets.progress\|widgets.spinner\|widgets.slider\|widgets.button\|widgets.checkbox\|widgets.link"` 零命中

## 禁触清单

`src/motui/kernel/**`（W1 产物只读）、`src/motui/interaction/**`（除 T3 里两处 import 行）、
`src/motui/app.py`、`src/motui/chrome.py`、`src/motui/__init__.py`（根门面 W4 才动）、
`src/motui/demo/**`（除 T6 的最小迁移）、`docs/API.md` 之外的 docs（除 COMPONENTS.md 的
两表就地更新）、`tools/**`（除 apidoc `--write` 的产物）、`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令与输出）/
偏差与取舍 / 未决问题。阻塞即停，不越界自救。
