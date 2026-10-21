# motui 2.0 — Ink & Signal design system

> 启动：2026-10-21 08:56（UTC+8）

## 目标

把视觉默认值和主题 API 一次性重建为可长期扩展的设计系统：

- **Palette → Theme role groups → component defaults** 三层；
- 暗/亮/扁平三套主题，`Theme.dark()/light()/flat()/auto()/from_palette()`；
- 单一 `Glyphs` bundle + `Border` 值对象；
- `Color` 带 16 色锚点，`Style` 接受 `Color`；
- 统一游标/状态/度量/结构字形；
- 2.0 之后只做加法：加字段、加组、加预设，不改名、不删字段、不改变字段含义。

## 非目标

- 不做 `Metrics`/间距 token（2.x 加法）。
- 不做 `Glyphs.ascii()` 预设（2.x 加法）。
- 不扩展 Syntax token 到 function/type/operator（2.x 加法）。
- 不做 per-component theme recipe（如 `theme.button`）；通用角色 + 构造参数覆盖。
- 不改渲染算法、布局算法、事件模型、Host 协议。

## 基线（2026-10-21 08:56）

| 门禁 | 基线 |
|---|---|
| `uv run pytest -q -p no:cacheprovider` | `824 passed`（W1 后 **896 passed**：824 基线 + 72 契约测试） |
| `uv run python tools/golden.py --check` | `58 topics match` |
| `uv run python tools/framebench.py` | `render-hash f872187a…d6e1` |
| `uv run python -m motui < /dev/null` | exit 0 |
| `uv run python -m motui --pages` | exit 0，4130 行 |

## 迁移策略（关键）

2.0 的 API 变化覆盖所有组件。为了每波门禁全绿，采用**临时 legacy 默认值**：

1. **W1** 新增完整新值层，同时：
   - 新 `Theme` 的字段默认值 = 旧视觉值；
   - `DEFAULT_THEME = Theme()`，因此 W1/W2 的输出与 1.x 逐字节一致；
   - 在 `Theme` 上提供**临时兼容属性**（`accent`/`muted`/`border`/…），让尚未迁移的组件继续工作。
2. **W2** 各组件族迁移到新 role groups；因为 legacy 默认值等价，输出不变。
3. **W3** 把 `Theme` 字段默认值切换为 Ink & Signal 暗色，迁移 `Glyphs` 并重录全部 golden。
4. **W4** 删除兼容属性、旧 `style.py` 常量、旧 `glyphs.py` 常量和旧逐组件字形参数。

**兼容属性是临时脚手架，W4 必须删除。** 任何波次都不得把兼容属性当作最终 API 写入文档。

## 波次表

| 波 | 内容 | 写入范围 | 依赖 |
|---|---|---|---|
| W1 | `Color`、`Style`、`ColorPalette`、style groups、`Theme`、`Glyphs`、`Border`、legacy 兼容层 | `kernel/{style,theme,glyphs}.py`、相关 kernel 测试、旧 Theme 构造的测试/演示 | 无 |
| W2a | 控件与表单族迁移 theme groups | `widgets/{action,choice,textfield,form,combobox,autocomplete,dialog}.py` + 对应测试 | W1 |
| W2b | 列表与导航族迁移 theme groups | `widgets/{list,tree,navlist,tabs,menubar,strip,rows,scroll,collapsible}.py` + 对应测试 | W1 |
| W2c | 数据与内容族迁移 theme groups | `widgets/{table,decor,diff,indicators,syntax}.py`、`widgets/markdown/*.py` + 对应测试 | W1 |
| W2d | interaction/app/chrome 迁移 theme groups | `interaction/{find,modal,overlays,palette,scrollbar}.py`、`kernel/chrome.py`、`app.py` + 对应测试 | W1 |
| W3 | 切换默认主题与 Glyphs，重录 golden，更新视觉测试 | 全部 widget/interaction 的 glyph 参数、`kernel/theme.py` 默认值、tests/golden | W2a-d |
| W4a | 删除兼容层/RowBands/旧常量，终验与 golden | `src/`、`tests/`、`demo/`、`tests/golden` | W3 |
| W4b | 文档/版本 2.0（不 tag/push/发版） | `docs/`、README/CONTRIBUTING/CHANGELOG、pyproject/uv.lock | W3 |

W2a–d 文件级不相交，可并行；W1 必须先合并；W3 在全部 W2 合并后开始。

## 全局不变量

1. W1/W2 的 `pytest`、golden、render-hash 必须与基线一致（零视觉变化）。
2. W3 的视觉变化必须只来自新默认主题/字形；golden 重录需解释每个 topic 的变化类别。
3. W4 后 `Theme` 不再有旧字段兼容属性，`style.py` 不再有语义色常量，`glyphs.py` 不再有旧常量。
4. 所有 token dataclass：`frozen=True, slots=True, kw_only=True`，每个字段有默认值。
5. 依赖方向不变；`kernel` 不 import `widgets`/`interaction`。
6. 公开 facade 的 `__all__` 变化只允许：新增 `CommandPalette`、`ColorPalette`、`Glyphs`、`Border`；删除旧 token/裸 `Palette` 时不保留别名。
7. 不修改 `tests/golden` 以外的生成物；不手改 golden。

## 共享文件所有者

| 文件 | 所有者 |
|---|---|
| `src/motui/kernel/style.py` | W1 |
| `src/motui/kernel/theme.py` | W1（W3 只改默认值） |
| `src/motui/kernel/glyphs.py` | W1 |
| `src/motui/kernel/chrome.py` | W2d |
| `src/motui/app.py` | W2d |
| `widgets/bands.py` | 不修改，W4 删除 |
| `tests/golden/topics/*` | W3 |
| `docs/*`、`README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml` | W4 |

## 门禁

每波：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
```

W1/W2：`render-hash` 必须等于 `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
W3：允许 hash 变化，但必须在 handoff 记录新 baseline；W3 之后所有波次 hash 稳定。

## 接口索引

- `ref/interfaces.md`：完整 API、默认值、兼容映射、字形映射。
- `ref/repo-map.md`：仓库地图与 `uv` worktree 命令。

## Final naming（2026-10-21）

- 命令面板：`CommandPalette`（根 + `motui.interaction.CommandPalette`，模块
  `interaction/command_palette.py`）。
- 主题色创作层：`ColorPalette`（根 + `motui.kernel.ColorPalette`）。
- **不再有裸 `Palette`**；根 facade 37 名。
- 版本保持 `2.0.0`，但**不 tag、不 push、不发版**；用户还要进行一轮重构。

## 状态

- ✅ W1 合并：Color/Style、ColorPalette、10 个 role groups、Theme/Glyphs/Border、legacy bridge。
- ✅ W2a-d 合并：组件族迁移 role groups；897 passed / 58 goldens / hash 不变。
- ✅ W3 合并：Ink & Signal 暗色默认、Glyphs/Border 接线；897 passed / 58 goldens /
  hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。
- 🚧 W4a/W4b：代码清理 + 文档/版本；命名已改为 CommandPalette + ColorPalette；
  待两个分支完成后合并终验。
