# Spec choice-architecture · W3 交互层重组 + Modal（波次 W3）

> ✅ 已合并 2026-10-17 @ `arch3-modal`（tip `c852d52`）→ main `1fa1406`；1463p/1s，hash 未动。
> 分支 `arch3-modal`；前置：W2（已合并：新 widgets 族文件、`Dialog`、`CheckGroup` 在位）；
> 深读：`00-overview.md`（红线、D2–D5、D8）、`docs/COMPONENTS.md` 的「The dispatch order」
> 一节（第 522 行起）与 `docs/DESIGN.md` 的层结构图。
> **最高约束：`Toasts` / `Tooltip` / `Stats` / `Scrollbar` / `Find` 的公开行为逐字节保持；
> `Palette` 的公开构造签名保持（`Palette(commands, *, theme=None, max_rows=8)`，实例属性
> `input` / `list` / `chosen` / `is_open` / `open()` / `close()` / `handle()` / `render()`），
> 但内部的打开/路由改由 `Modal` 承载——这是本波要消灭的重复。**

## 目标

1. 顶层 `chrome.py` 拆掉：`Scrollbar` → `interaction/scrollbar.py`；`Toasts`/`Tooltip`/`Stats`
   → `interaction/overlays.py`。`interaction/` 自此是「策略层住全部控制器」的完整一极。
2. `interaction/modal.py`：`Modal` —— 遮罩 + 定位（居中/锚定）+ 统一事件路由 + 点框外关闭。
   `Palette` 迁到 `interaction/palette.py` 并改由 `Modal` 承载；`Dialog` 获得 driver 侧的搭档。
3. `widgets/dialog.py` 加 `Prompt`（Dialog + Input body）。
4. `interaction/search.py` → `interaction/find.py`（纯改名，内容不动；`Find` 是"搜索层"不是
   "模态"，D8，不迁 Modal）。

## 工单（按序执行，每项一个 commit；每步之间跑 `uv run pytest -q`）

### T1 `interaction/modal.py`：`Modal`

模块 import：`..app.TUI`、`..kernel.frame` 的 `Rect`/`splice_row`、`..kernel.lines` 的
`Line`/`overlay`、`..kernel.style` 的 `NONE`/`Style`、`..kernel.theme` 的 `Theme`/`DEFAULT_THEME`、
`..kernel.viewport.ScreenLayout`、`..kernel.events` 的 `Key`/`Paste`/`MouseEvent`。
面板类型用结构化鸭子（任何有 `render(width)` 与 `click(row, col)` 的组件），
**不 import `widgets.dialog`**——依赖方向天然合法（interaction 在 widgets 之上），
但不引入无谓的耦合，`Dialog`/`Prompt`/`_PalettePanel` 都能填进这个口。

```python
class Modal:
    """A centered (or anchored) panel over the frame: the blocking layer.

    ``tui`` is the driver whose frame the overlay registers on (at
    construction, the ``Toasts`` lifecycle); ``dialog`` the pure component
    painted in the box (``Dialog``, ``Prompt``, any ``Component`` with a
    ``handle`` for the keyboard); ``anchor=(y, x)`` pins the panel's
    top-left cell (clamped into the frame) instead of centering it -- the
    ComboBox / context-menu door.  ``dismiss_on_click_outside`` (default
    ``True``) consumes a press outside the panel and closes with ``None``.

    ``chosen`` is the panel's result, read once by the host and reset to
    ``None``: the value of the button the user took, or ``None`` for
    ``escape`` / a click outside / ``close()``.  A closed modal paints
    nothing and consumes nothing (``is_open``), so a host may keep one
    mounted for the session and route it unconditionally.
    """

    __slots__ = (...)

    def __init__(self, tui, dialog, *, anchor=None, scrim=True,
                 scrim_style=None, dismiss_on_click_outside=True,
                 theme=None) -> None: ...
    is_open: bool                      # property
    chosen: object | None
    def open(self) -> None             # reset chosen, register if needed, invalidate
    def close(self, value: object = None) -> None   # set chosen, drop the panel
    def handle(self, event: Key | Paste) -> bool
    def paint(self, frame) -> ScreenLayout
    def detach(self) -> None           # unregister the overlay (idempotent, 身份注销)
```

**语义钉死（写进 docstring 并在测试里断言）**：

- **绘制**：`frame.rect` 为空或未打开 → 原样返回 layout；否则先把**全屏每一行**过一遍
  `Line(overlay(scrim_style, row.segments))`（`scrim_style` 默认
  `Style(dim=True)`：颜色保留、权重降下，D4），再把面板的行按 `Rect` 用 `splice_row`
  写入（行超框裁剪）。面板尺寸 = `dialog.render(frame.rect.width)` 的
  `max(line.width)`/行数，再与 `frame.rect` 钳制；居中时
  `x = rect.x + max(0, (rect.width - w) // 2)`、`y = rect.y + max(0, (rect.height - h) // 2)`；
  锚定时 `(y, x)` 先钳制到 `[rect.y, rect.bottom - h] × [rect.x, rect.right - w]`。
  `scrim=False` 时跳过遮罩。
- **事件**（`handle` 契约与库内一致：消费返回 True）：
  1. 未打开 → False。
  2. `MouseEvent` 且 `kind == "press"` 且 `name == "left"`：坐标在面板矩形内 → 交给
     `dialog.click(row, col)`（面板内坐标）；由 `dialog.chosen` 是否被写出来决定关闭
     （写出来 → `close(value)`）；坐标在外 → `dismiss_on_click_outside` 时
     `close()`（写 `chosen=None`）并消费，否则消费且不动。**无论哪种，事件都被消费**
     （模态的语义：背景不吃任何点击）。
  3. `Key`：**先给 body**——`dialog.body` 若有 `handle`，`body.handle(event)` 为 True 时
     消费（输入框的编辑键/回车由 body 决定职责；`Input` 不认 enter 就会落回下一层）；
     再把事件给 `dialog.handle(event)`；两者都消费不了时：`escape` 兜底取消（若 dialog
     自己没消费）、其余键**一律消费并丢弃**（模态下宿主与开发者快捷键失联，`c-c` 的
     退出由宿主自己在链上先处理——见迁移后的 demo 顺序）。
  4. `Paste`：给 `body.handle`（如果它认），否则消费丢弃。
- 关闭后（`is_open=False`）`paint` 原样返回 layout（注册可留，零字节）；`open()` 重置
  `dialog.chosen`/`dialog` 的游标吗——**不重置**：重置是 dialog 自己 `open()` 或宿主重建
  的事，`Modal.open` 只负责 `chosen=None`、注册（若从未注册）、`tui.invalidate()`。
- `detach()`：从 frame 注销（身份、幂等：不在注册表里就不动）；与 `Toasts.detach` 同构。
- `set_theme` 不做（重建比换肤简单，写进 docstring）。

### T2 `interaction/palette.py`：`Palette` 迁入并改用 `Modal`

- 文件搬到 `interaction/palette.py`；**公开签名、属性与行为保持**（`input`/`list` 组合、
  打开即重置、过滤跟随 query、`chosen` 读一次、`Escape` 关而无选、`enter` 取当前高亮）。
- 内部：组合 **一个 `Dialog` 不行**（Palette 是"查询行 + 列表"不是"标题+按钮"），
  组合一个**自定义的宿主组件**：一个私有 `_PalettePanel`（`Component`）持 `Input` +
  `Autocomplete`，`render(width)` 是两者的行叠加，`handle(event)` 是现在的 handle 主体
  （up/down/enter/escape + 其余给 input）；`Modal(tui, panel, anchor=底部锚点)`。
  这个 panel 是 `interaction/palette.py` 的私有件——**不要**放回 widgets 层（它只有
  Palette 一个消费者）。
- 外观保持现状：`Palette.render(width)` 仍是那几行的组合（现在从 panel 渲染转发）；
  行样式/主题来源不变，golden 不应因此移动（Palette 不在 demo 的常驻画面里，
  chrome 页的模态只在脚本路径打开——**重跑 golden 校验，若动则解释**）。
- `Modal` 的注册意味着构造即上 overlay；**旧行为是 Palette 不上 overlay（渲染在页面里）**。
  本组无兼容包袱，直接换掉：**`Palette(tui, commands, *, theme=None, max_rows=8)`**——
  `tui` 升为第一个位置参数（它本来就需要 driver 才能做遮罩/点击外部/失效重绘），
  内部持一个 `Modal`（锚定面板），`open()`/`close()` 就是 `modal.open()`/
  `modal.close()` 的转发（`is_open` 转发 `modal.is_open`），`handle(event)` 转发
  `modal.handle(event)`，`render(width)` 仍返回面板的行（给宿主仍可嵌在文档里）。
  `chosen` 是面板的语义：`enter` 取中时是命令的 `value`，`Escape`/点框外是 `None`。
  **没有双态、没有 `tui=None` 的退化**——`Palette` 自此就是一个模态控制器。
- 删 `widgets/palette.py`、`interaction/search.py`（改名 `find.py` 在 T3）。
- 测试：`tests/test_widgets_palette.py` → 改名 `tests/test_palette.py`，构造全部改带
  `tui`（`headless_tui` 先例），断言里「嵌入渲染」的旧口径改成「`render(width)` 是面板行」
  并新增 3–5 条模态路径断言（打开时遮罩绘制、点框外关闭 `chosen=None`、打开期间
  非面板按键被消费、`escape` 关闭）。

### T3 顶层 `chrome.py` 拆分 + `search.py` 改名

- `interaction/scrollbar.py` ← `Scrollbar` 及其私有助手（`_thumb_of` 等）。
- `interaction/overlays.py` ← `Toasts` · `Tooltip` · `Stats` 及其私有助手
  （`_Toast`/`_stack`/`_band_row`/`EXPIRY_TICK`/角落常量）。
- `interaction/search.py` → `interaction/find.py`（`git mv` 保历史），内容除模块 docstring
  里指向 `widgets.palette` 的引用更新外不动。
- 删 `src/motui/chrome.py`。
- `interaction/__init__.py`：`__all__ = ["Find", "FocusRing", "Modal", "Palette", "Pointer",
  "Scrollbar", "SelectionGesture", "Stats", "Toasts", "Tooltip", "copy_on_select"]`
  （按常量/类/函数分组排序）；docstring 改写为「策略层：焦点、指针、手势、搜索、模态、
  浮层、滚动条」。
- `src/motui/__init__.py`：`from .chrome import …` 改 `from .interaction import …`；
  根 `__all__` 名字集合**不变**（仍是 31 个，顺序按新来源重排即可——测试钉的是名字集合
  与排序规则，见 `tests/test_api_root.py`）。
- 测试改名：`tests/test_chrome.py` → 拆/并为 `tests/test_overlays.py`（Toasts/Tooltip/Stats）
  + `tests/test_scrollbar.py`（Scrollbar）；`tests/test_search.py` → `tests/test_find.py`。
  **只改文件归属与 import，断言内容不重写**；`test_frame.py`/`test_app.py` 等对
  `motui.chrome` 的引用改到新路径。
- `tools/apidoc.py` 的 `FACADES`：删 `"motui.chrome"`，加 `"motui.interaction.modal"`、
  `"motui.interaction.overlays"`、`"motui.interaction.palette"`、`"motui.interaction.scrollbar"`
  （按字母序放进现有元组）；`--write` 重生成 `docs/API.md`。
- `tests/test_api_root.py`：`LAYER_ALLS`/`DOWN_LISTED` 的 `motui.chrome` 条目删除，
  `motui.interaction*` 条目重钉（含 `Modal`/`Palette` 的落户）。

### T4 `widgets/dialog.py` 加 `Prompt`

```python
def prompt_dialog(
    title: str, *, placeholder: str = "", mask: str = "",
    confirm_text: str = "OK", cancel_text: str = "Cancel",
    style: Style | None = None, danger: bool = False, theme: Theme | None = None,
) -> Dialog
```

`Dialog(title=title, body=Input(placeholder=placeholder, mask=mask, theme=theme),
buttons=[ButtonSpec(confirm_text, "ok"), ButtonSpec(cancel_text, None, …)], danger=danger)`。
`Input` 不认 `enter`（它的 keymap 里 enter 未绑定）——`Modal` 的 body-first 路由因此把
Enter 落到 dialog 的按钮激活上，这正是要的行为；写进 docstring 与 1–2 条测试。
（`Prompt` 不做「取值」：`chosen == "ok"` 时宿主读 `dialog.body.text`，docstring 写明。）

## 验收（完成前自测，报告给真实结论）

1. `uv run pytest -q` 全绿（贴 passed/skipped）
2. `uv run python tools/golden.py --check`（若 Palette 迁移动了画面：`--update` 同 commit 重录 +
   commit message 逐页解释）
3. `uv run python tools/apidoc.py --check` → matches（条目数与上波不同，属预期）
4. `uv run python -m motui < /dev/null`、`--pages` 均 exit 0
5. `grep -rn "motui.chrome\|from .chrome import\|from ..chrome import" src tests tools docs/API.md`
   零命中（`docs/DESIGN.md`/`docs/COMPONENTS.md` 的引用本波就地更新路径，
   全篇重写仍留 W4）
6. `uv run python tools/framebench.py` render-hash 与上波一致（Palette 不动常驻画面）

## 禁触清单

`src/motui/kernel/**`、`src/motui/widgets/**`（除 `widgets/dialog.py` 加 `Prompt`、
`widgets/__init__.py` 删 Palette 导出这两处）、`src/motui/app.py`、`src/motui/keys/**`、
`src/motui/demo/**`（W4 才动）、`docs/*.md` 除 API.md 产物与两处路径引用、`tools/**`
除 apidoc 的 FACADES、`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令与输出）/
偏差与取舍 / 未决问题。阻塞即停，不越界自救。
