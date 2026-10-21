# W6 docs 交接包
> 分支 `refactor/1.2-w6-docs` / 起点 `60615d6`（W5b merge 后的 main）/ 2026-10-21
> 范围：只改文档；未动代码、测试、golden、pyproject。

## A. 改动文件

- `README.md` — Quickstart 改为 17 行 `App` 版本（`on_start` / `add` /
  `focus` / `bind` / `run`），删除手写 `FocusManager` + `Pointer` +
  `read_event` 循环；重写 mental-model、features、components、interactions、
  shell、styling、keys、demo 计数。
- `docs/DESIGN.md` — 层图改为 `core -> widgets -> app`；删除 Host seam，
  改述为「app 是唯一 composition root」；driver lifecycle 改为 App 默认循环 +
  TUI 低层；缓存改为 revision-only；新增 Widget/Styles、ScrollState/
  ScrollView bar、Table wrap 三节；Hit 改为 `chain` 派生；坐标、frame、
  selection/focus、value semantics 同步。
- `docs/CONTRACT.md` — 坐标/Hit、driver lifecycle、documents/docks、styles、
  components、focus/overlays、layering、caching、naming charter 全部按 1.2.0
  重写；`read_event` 明确为纯读取，`TUI.add` 返回 id，`dock` 接组件，
  capability protocol 不再作为 facade 导出。
- `docs/COMPONENTS.md` — 所有公共组件签名用 `inspect.signature` 重新核对；
  新增「Global conventions」（Widget + `theme`/`styles`，`Component` 只需
  `render`）；删除 Delegate；更新 ScrollView/Table/Select/MultiSelect/
  Input/Editor/Dialog/ButtonSpec/Padding；控制器路径改 `motui.app.*`，
  主题/keymap 导入改 `motui.core.*`。
- `CONTRIBUTING.md` — 依赖图与层职责改为三层；invariant 5/6 改为 1.2.0 与
  1.2.x additive；添加组件步骤改为 Widget/Styles/revision；版本策略写明
  当前 1.2.0。
- `CHANGELOG.md` — 只清理 1.2.0 段里的旧命名空间路径
  （`motui.interaction` -> `motui.app`，`motui.kernel` -> `motui.core`，
  `interaction/` -> `app/`）；1.1.x 及更早小节未动。

## B. 清理的旧概念

- `motui.kernel` / `motui.keys` / `motui.interaction` / `motui.commands`
  在面向当前版本的文档中已无正向引用（仅剩「不存在」的说明）。
- `Host`、`QueryInput`、`FilterList`、`OptionLike`、`make_input` /
  `make_autocomplete` 全部从设计/契约中删除。
- `BlockState` / `seal` / `OPEN` / `SEALED` / sealed cache 改为
  `Revisioned.revision()` 非 None 才缓存。
- `Delegate` 从组件目录删除。
- `style/hover_style/focus_style/disabled_style/ground_style/label_style/...`
  与构造器 `focused=` 删除，统一为 `theme=` + `styles: Styles`。
- `Select(multi=, marked=)`：单选留在 `Select`，多选改为 `MultiSelect`，
  `CheckboxGroup` 基于 `MultiSelect`。
- `ScrollView(scrollbar=)` 改为 `bar=`，并说明 thumb 拖动 / track 翻页 /
  wheel。
- `read_event` 吸收 wheel/page/focus 的旧行为删除；`App.dispatch` 承担默认
  路由。
- `TUI.dock(Viewport(...))` 改为 `dock(component)`；`TUI.add` 返回 id、
  `get/remove` 返回 Component。
- `Table` 的省略号默认改为 `wrap=True`，保留 `wrap=False` 旧行为。

## C. 仍存在但属于历史/明确否定说明的旧引用

- `CHANGELOG.md` 的 1.1.x 及更早小节保留当时的 `motui.kernel` 等真实历史。
- `CHANGELOG.md` 1.2.0 的 Breaking/Added 段保留「1.x 名称已删除」的否定句。
- `CONTRIBUTING.md` invariant 5 列出被删除的 `RowBands`、`BlockState`、
  `Delegate`、`Host` 等，作为「不设兼容层」的例证。
- `docs/DESIGN.md` 明确写「No Host seam」「there is no scroll_keys」。
- `docs/CONTRACT.md` 明确写「There is no motui.kernel/... namespace」。
- `docs/releases/1.1.*.md` 未触碰。

## D. 验证

- `uv run pytest -q -p no:cacheprovider` -> **890 passed**。
- `uv run python tools/golden.py --check` -> **57 topics match**（未重录）。
- `uv run python -m motui < /dev/null` -> exit 0。
- `uv run python -m motui --pages` -> exit 0。
- README Quickstart、interactions、shell 三段代码在 headless App 上实测通过：
  quickstart 输出 `hello, Ada`，shell 输出 `ready` + `you: hello`，
  `mount(Scrollbar)` + `open_modal` 正常。
- `git status` 仅 6 个文档文件 + 本 handoff；无代码/测试/golden/pyproject
  变化。

## E. 未做/留给 lead

- 未 merge、未 push、未 tag、未改 `pyproject.toml` 版本。
- 未重录 golden；文档改动不改变任何渲染帧。
- W6 工单中的版本收尾（pyproject / release notes / tag）不在本 worker 范围。
