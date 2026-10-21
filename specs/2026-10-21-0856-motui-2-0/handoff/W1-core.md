# W1 交接包（core value layer + legacy bridge）

> 分支 `motui-2/w1-core` / 起点 `ac281ad` / 2026-10-21

## A. 自动事实

### 用例数（`pytest --collect-only` 实测）

| 目录 | 基线 | 现在 |
|---|---|---|
| `tests/kernel` | 219 | 291 |
| `tests/keys` | 55 | 55 |
| `tests/widgets` | 324 | 324 |
| `tests/app` | 49 | 49 |
| `tests/interaction` | 161 | 161 |
| 根级（api/packaging/invariants/smoke） | 16 | 16 |
| **合计** | **824** | **896** |

`tests/kernel` 的 +72 全部是 T5 新增的契约测试：`test_theme_contract.py`
（12 个 token 类 × 3 个结构契约 + Theme/构造函数/band 语义）、`test_glyphs.py`
新增宽度/Emoji/边框用例、`test_style.py` 新增 Color 四种模式用例；`test_theme.py`
重写时保留原 8 个行为断言并补了 2 个 legacy 默认/兼容属性断言。**没有删除基线用例。**

### 终验命令与真实输出

```text
uv run pytest -q -p no:cacheprovider
896 passed in 10.61s

uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
render-hash  : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1

uv run python -m motui < /dev/null
exit 0，输出 70 行，与基线逐字节相同

uv run python -m motui --pages > /tmp/pages.txt
exit 0，4130 行，与基线逐字节相同
```

### Commit 清单

| commit | 内容 |
|---|---|
| `5d0c8d9` | `style: add Color with an ansi fallback beside the truecolor value` |
| `e69e408` | `theme: add the 2.0 role groups, palettes and legacy bridge` |
| `f483a1b` | `glyphs: add the Border styles and the Glyphs vocabulary` |
| `5ab6ae1` | `tests: map the old flat Theme constructions onto the role groups` |
| `3853c4b` | `tests: pin the 2.0 token, glyph and Color contracts` |

### 变更范围 / 禁触审计

`git diff --name-only ac281ad..HEAD` 共 21 个文件：

- 源：`kernel/{style,theme,glyphs}.py`、`demo/assets.py`、`demo/topics/styling.py`。
- 测试：`tests/{app,interaction,kernel,widgets}` 下的 16 个文件（T4 机械构造点 + T5 契约测试）。

零 diff：`src/motui/widgets/`（仅测试目录下的 widget 测试改名）、
`src/motui/interaction/`、`src/motui/app.py`、`src/motui/keys/`、`tests/golden/`、
`tools/`、`docs/`、`pyproject.toml`、`uv.lock`。未运行 `golden.py --update`，
未 merge/push/tag。

## B. 只有存在于脑子里的东西

### Color 的精确降级路径

`Color(value, ansi=None)` 是 frozen/slots 值；`ansi` 在 `__post_init__` 里对
`FG_CODES` 校验，非键即 `ValueError`。`Style.fg/bg` 接受 `Color | str | tuple | None`。

| 模式 | Color(value=RGB) | Color(value=裸名字) |
|---|---|---|
| truecolor（`Style.prefix()`） | `38;2;r;g;b` / `48;2;r;g;b`，忽略 `ansi` | 用裸名字的 base code |
| 256 | 对 `value` 量化成 `38;5;N` / `48;5;N`，忽略 `ansi` | 保留 base code |
| 16 | **优先 `ansi`**；没有才量化 | 保留 base code |
| none | 丢弃颜色，属性保留 | 同左 |

关键点：`ansi` 只在 16 色模式生效，256/truecolor 都按 `value`；`Style.prefix()`
的实例缓存没有改动（Color hashable）；旧 `Style(fg="#...")`/tuple/名字路径逐字节不变。

### legacy 默认值与兼容属性

- 10 个 role group 的**字段默认值**严格等于 `interfaces.md` §3.1 的 1.x 值；
  `DEFAULT_THEME = Theme()`。
- 兼容属性严格按 §3.4 一一映射（`dim -> text.faint`、`accent -> content.accent`、
  `hover -> surfaces.hover`、`ground_active -> rows.active`、`error -> status.danger` …）。
- `headings` 返回 `content.headings`；`heading` 返回 `content.headings[1]`。
- `notice_levels` 每次访问从 `status.warning`/`status.danger` 现算一个
  `MappingProxyType`（旧前缀 `WARNING: ` / `ERROR: `），仍然只读；没有沿用旧
  `_tables` 缓存字段（Theme 现在是 slots，派生表无状态）。
- `Themed.pick(explicit, fallback)` 新增；`_pick(explicit, field)` 保留并委托给
  `pick`，继续服务未迁移组件（`widgets/` 里 30+ 处字符串 field 读取）。

### `RowStyles.band` 的精确语义

```text
disabled > hovered > (active ? (focused ? active : inactive)) > selected > marked > base
```

- `active=True, focused=False` 落到 `inactive` 并**停止**：即使同时 `selected`/`marked`
  也不会继续往下选。
- `hovered` 压过 `active`（指针比键盘位置更即时）；`disabled` 压过一切。
- `ControlStyles.band`：`disabled > active > focused > hovered > base`，`active`
  压过 `focused`，与既有控件行为一致。
- 两者都无副作用（契约测试里显式断言重复调用与对象不变）。

### Palette / Theme 构造

- `Palette()` 的默认值取 `DARK_PALETTE` 的值，所以 `Palette() == DARK_PALETTE`；
  `LIGHT_PALETTE` 覆盖全部 18 个字段。这样满足“所有 token 字段都有默认值”的契约。
- `Theme.from_palette` 按 §3.2 派生；`dark()/light()` 分别用两个 shipped palette；
  `flat()` = 暗色 + `surfaces.* = NONE` + 文档列出的 rows/overlays 覆盖。
- `from_palette` 的 `text.inverse` 在 Palette 里没有对应字段（它是页面底色），
  由 `_inverse_for` 判定：`palette == LIGHT_PALETTE` 时 `#ffffff`，否则 `#0d1117`。
  自定义 palette 得到暗色答案。
- `auto(env)`：`TERM_BACKGROUND` 的 light/white/dark/black 优先；否则读
  `COLORFGBG` 的最后一个数字槽（7 或 ≥9 视为亮底，其余暗底）；未知回退 dark。
  规范里写作 `COLORBGBG`，实现同时接受 `COLORFGBG`（优先）和 `COLORBGBG`
  （别名），只读传入的 mapping，不碰全局。

### 机械改写清单

只改构造，不改断言与组件逻辑：

| 文件 | 旧 | 新 |
|---|---|---|
| `demo/assets.py` | `accent=`, `heading=`, `selection=`, `ground_active=`, `hover=` | `content`/`text`/`rows`/`surfaces` group 覆盖 |
| `demo/topics/styling.py` | `replace(DEFAULT_THEME, accent=...)` | `replace(DEFAULT_THEME, content=replace(...))` |
| `tests/app/test_selection_overlay.py` | `selection=` | `text.selection` |
| `tests/interaction/test_find.py`、`test_text.py`、`test_markdown.py`、`test_menubar.py` | `hover=` | `surfaces.hover` |
| `tests/interaction/test_overlays.py` | `Theme(toast=...)` | `Theme(overlays=replace(Theme().overlays, toast=...))` |
| `tests/interaction/test_scrollbar.py` | `Theme(scrollbar=..., scrollbar_thumb=...)` | `Theme(chrome=replace(Theme().chrome, ...))` |
| `tests/widgets/test_action.py`、`test_indicators.py`、`test_editing.py` | 混合旧字段 | 对应 group 覆盖 |
| `tests/widgets/test_containers.py` | `border=` | `borders.base` |
| `tests/widgets/test_syntax.py` | `warning=` | `status.warning` |
| `tests/kernel/test_theme.py` | 旧扁平构造 | 重写为 2.0 group 构造 + 兼容属性断言 |

`heading=x` 的映射落地为
`headings=(x.merge(Style(underline=True)), *(x,) * 5)`，而不是字面的 `(x, ...)`：
旧 `headings` 就是“h1 加下划线、其余同色”，只有这样才能保持 golden 逐字节一致。

### 契约测试落点

- `tests/kernel/test_theme_contract.py`：12 个 token dataclass 都断言
  `frozen`/`slots`/每个字段 `kw_only`/每个字段有默认值/无参可构造/拒绝位置参数；
  另测 `Theme()`/`DEFAULT_THEME`、dark/light/flat/from_palette、auto 矩阵、
  两个 band 的完整优先级、replace 不可变性。
- `tests/kernel/test_glyphs.py`：每个单字形字段 `wcswidth == 1`；bullets/spinner
  成员各 1 列；pair 3 列；默认 Glyphs 不含 Emoji 展示字符（拒绝集
  `ℹ ✔ ✖ ☐ ☑ ⚠ ❗ ❌ ✅` 等）；六种 Border 的全部 14 个 mark 都是 1 列。
- `tests/kernel/test_style.py`：`Color` 在 truecolor/256/16/none 下的精确 SGR、
  ansi 校验、frozen/hash/merge。

### 偏差、取舍与已知风险

1. **T2/T3 的中间态不绿**：T2 验收命令 `pytest tests/kernel/test_theme.py` 在 T4
   机械改写前必然失败（旧 `Theme(heading=...)` 构造），demo import 也会在 T4 前
   因 `assets.py` 的旧构造失败。T2 当时用“排除 test_theme 的 kernel 子集 + 手工
   冒烟”验证；T4 后全绿。这是工单顺序的固有限制，不是遗留缺陷。
2. **Palette 默认值**：§2 对多数字段只写 `...`；选择暗色值使 `Palette()` 自洽，
   并满足 T5 “所有字段有默认值”。若 W3 希望 `Palette()` 代表别的基线，只需改
   `Palette` 默认值，`DARK_PALETTE` 可继续显式构造。
3. **`COLORFGBG` vs `COLORBGBG`**：规范写的是后者（疑似笔误）；实现优先标准名
   `COLORFGBG`，同时接受 `COLORBGBG`。
4. **`Border.none()`**：14 个字段都是空格，保留布局占位；若 W3 希望它塌缩为零宽，
   需要在组件侧约定，当前值本身不塌缩。
5. **`notice_levels`** 每次访问重建 mapping（旧实现是构造期缓存）。调用点都是
   初始化期读取，无性能影响；只读语义保持。
6. **demo 的 `api_line` 字符串与 `interaction/` 的 docstring** 仍写着旧
   `Theme(accent, ...)`/`Theme(scrollbar=...)`。它们不是构造点；改 demo 字符串会
   改变 `--pages` 输出（当前要求与基线逐字节相同），`interaction/` 是禁触区。
   留给 W3/W4 随文档迁移一起改。
7. **根导出**：`Palette`/`Glyphs`/`Border` 尚未从 `motui`/`motui.kernel` 根导出；
   W1 的写入范围只到三个 kernel 模块，W4 工单明确“公开 facade 只新增
   `Palette`/`Glyphs`/`Border`”，由 W4 落地。
8. **Theme 现在 `slots=True, kw_only=True`**：仓内所有构造都是关键字；外部若有
   位置构造会 TypeError（2.0 的预期收紧）。
9. **用例数 896 ≠ 824**：824 是基线契约，72 个新契约测试使其增加；验收时应看
   “基线用例仍全绿 + golden/hash 不变”，而不是总数等于 824。

## C. 指针

- spec：`specs/2026-10-21-0856-motui-2-0/01-W1-core.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §1–§4、§6
- 源：`src/motui/kernel/style.py`（Color）、`kernel/theme.py`（groups/Palette/Theme/
  Themed/兼容属性）、`kernel/glyphs.py`（Border/Glyphs/GLYPHS）
- 契约测试：`tests/kernel/test_theme_contract.py`、`test_theme.py`、`test_glyphs.py`、
  `test_style.py`
- 视觉门禁：`uv run python tools/golden.py --check`、`uv run python tools/framebench.py`
- 基线：起点 `ac281ad`；W1 HEAD `3853c4b`；render-hash
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`
