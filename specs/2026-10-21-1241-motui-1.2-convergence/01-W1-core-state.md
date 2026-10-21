# W1 · 核心状态收敛（ScrollState / Cursor / 删除意外抽象）

> 分支 `refactor/1.2-core-state`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w1-core-state`
> 前置：无；写入范围见下；波末必须全量绿。

## 目标

在不改变公共包路径、不改变控件构造器的前提下，把“滚动状态”和“游标步进”各收敛成一份实现，并删除已经没有产品消费者的意外抽象。行为红线：除 `ScrollState.thumb` 统一后可能改变的 bar thumb 长度、以及删除 `Delegate` 导致的 demo 主题移除之外，golden 帧不得变化。

## 前置上下文

- 必读顺序：`specs/2026-10-21-1241-motui-1.2-convergence/ref/repo-map.md` → `ref/interfaces.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
```

Windows/Git Bash 若 `uv` 不可用，用 `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` 等等价命令，并在 handoff 写明。
- 稳定区（已验收，勿重读）：`docs/DESIGN.md`、`docs/CONTRACT.md` 的架构叙述；本波不改文档。
- 已知约束：
  - 当前 `Scrollbar` 与 `ScrollView` 有两套 thumb 公式；统一后 `ScrollView` 的 thumb 可能从 1 格变 2 格（8/40 比例），允许因此重录 golden，但只允许这一类视觉差异。
  - `Delegate` 只被 demo `components_layout.py` 和测试使用；删除时同步删除 `components--delegate` topic/golden。
  - `BlockState.SEALED` 没有生产调用者；删除时把缓存规则改成“有非 None revision 才缓存”。
  - 不允许改包路径、公共控件构造器参数、`read_event` 行为（这些是 W2-W4）。

## 工单（按序执行，每项一个 commit）

### T1 · ScrollState + Scrollable

- 新增 `src/motui/kernel/scroll.py`，实现 `ScrollState`、`Scrollable`（签名见 `ref/interfaces.md` 第 1 节）。
- `Viewport`：
  - 用 `ScrollState(stick_to_bottom=True)` 持有 `offset/content_height/viewport_height`；
  - 保留 `offset`、`at_bottom`、`scroll_up/down/to/to_bottom`、`layout` 的现有语义；
  - `layout()` 把 `total_rows` / body 高度写入 state，clamp 并贴底；`ScreenLayout.offset/total_rows` 从 state 取；
  - 实现 `scroll_state`、`scroll_to`、`scroll_by`。
- `ScrollView`：
  - 用 `ScrollState` 持有 offset/content/viewport；保留 `offset`、`total_rows`、`viewport_height`、`scroll_to/up/down/reveal`、`handle` 的现有语义；
  - `render()` 更新 state 后 clamp；`_thumb_span` 改为调用 `state.thumb(height)`，删除本地公式；
  - 本波不实现 bar 的鼠标输入（W5b）。
- `Scrollbar` / `Pane`：
  - `Pane` 增加 `scroll_state` property，委托 `viewport.scroll_state`；
  - `Scrollbar._thumb_of` 改为构造/读取 `ScrollState` 并调用 `thumb`；删除本地公式；
  - `Scrollbar` 的构造参数与 `pane=` 绑定保持不变（W5b 再泛化为 `Scrollable`）。
- 允许改：`src/motui/kernel/scroll.py`(新)、`src/motui/kernel/viewport.py`、`src/motui/kernel/frame.py`（仅 Pane.scroll_state）、`src/motui/widgets/scroll.py`、`src/motui/interaction/scrollbar.py`、`src/motui/app.py`（仅滚动 facade 的委托）、`src/motui/kernel/__init__.py`、对应 tests。
- 验证：`uv run pytest -q -p no:cacheprovider`；`uv run python tools/golden.py --check`（若失败，只允许 thumb 长度变化，`--update` 后逐帧解释）。

### T2 · Cursor 统一

- 在 `src/motui/kernel/cursor.py` 提供公开的 `Cursor`（签名见 `ref/interfaces.md`）。允许内部复用/改造 `CursorWindow`，但公共面只保留 `Cursor`。
- 迁移 `List`、`Select`、`Table`、`Tree`、`NavList`、`Tabs`、`MenuBar` 的：
  - disabled 跳过步进；
  - clamp / wrap；
  - home/end；
  - 窗口范围计算（List 的 centering、Select 的 top-stick、strip 的 top-stick）。
- 保留每个控件原有的 wrap 策略：
  - List/Table/Tree/NavList：不 wrap，clamp；
  - Select/Autocomplete/ContextMenu：默认 wrap；
  - Tabs/MenuBar：不 wrap。
- 保留 pending result / mark / hover 等控件自有状态，不塞进 `Cursor`。
- 允许改：`src/motui/kernel/cursor.py`、`src/motui/widgets/{list,choice,table,tree,navlist,tabs,menubar,strip,autocomplete,combobox,form}.py`、`src/motui/kernel/__init__.py`、对应 tests。
- 验证：全量 pytest + golden 不变（游标行为必须逐字节保持）。

### T3 · 删除意外抽象与兼容残留

- 删除 `src/motui/widgets/delegate.py` 与 `Delegate` 的所有导出/引用；删除 `components--delegate` demo topic、registry 条目、golden 文件、测试。
- 删除 `BlockState`、`Block.seal()`、`Block.state`；缓存规则改为：
  - `Block.rows(width)` 只在组件实现 `revision()` 且返回非 `None` 时缓存；
  - 否则每次 re-render；
  - `Block.render(width)` 保持 uncached。
- 更新 `testing.snapshot`：去掉 `[id | state]` 的 state 段，改为 `[id]` 或 `[id | top]` / `[id | bottom]`（pin 保留）。这是测试辅助输出，允许更新对应测试。
- 删除 `DEFAULT_HEADER_STYLE`（`widgets/table.py`）和 `COLORBGBG` 兼容分支（`kernel/theme.py`）。
- 删除对应测试/文档引用；不要留下 alias 或 `__getattr__` 桥。
- 允许改：`src/motui/kernel/block.py`、`src/motui/kernel/theme.py`、`src/motui/widgets/{__init__,table,delegate}.py`、`src/motui/testing.py`、`src/motui/demo/{registry,topics/components_layout}.py`、`tests/**`、`tests/golden/topics/components--delegate.txt`（删除）。
- 验证：全量 pytest + golden check（delegate 帧删除后应通过）。

### T4 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 上述五条门禁全绿；报告贴真实用例数/失败项。
2. `rg "CursorWindow|_thumb_span|_thumb_of" src` 只剩一份实现路径（Cursor 内部复用可以保留 `CursorWindow` 名字，但不得有第二套窗口/thumb 公式）。
3. `rg "Delegate|BlockState|DEFAULT_HEADER_STYLE|COLORBGBG" src tests docs` 无残留（specs 除外）。
4. `ScrollView` 和 `Scrollbar` 的 thumb 都由 `ScrollState.thumb` 产生。
5. golden 变化只允许：ScrollView thumb 长度、delegate topic 删除；其余逐字节不变。

## 禁触清单

- `pyproject.toml`、`CHANGELOG.md`、`README.md`、`docs/**`（W6 统一改）。
- `src/motui/__init__.py` 的 root 名单（W6）。
- 包路径重命名（W2）。
- 控件构造器参数/`Styles`（W3）。
- `read_event` 行为（W4）。
- `Table` 换行（W5a）。
- `ScrollView` bar 鼠标输入（W5b）。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W1-w1-core-state.md`，按 SKILL.md 的 Handoff 协议（A 自动事实 / B 只存在脑子里的东西 / C 指针），60-80 行。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 /
偏差与取舍（摘要，详情进 handoff B 节）/
交接校验（本波没有前置 handoff，写“无”）/
探索审计（handoff 之外读了哪些文件、为什么）/ 未决问题
