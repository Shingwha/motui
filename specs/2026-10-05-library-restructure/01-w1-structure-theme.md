> ✅ 2026-10-05 @ 分支 lib-w1 — 已合并 main

# Spec W1 · 结构迁移 + Theme(波次 W1)

> 分支 `lib-w1-structure`;前置:无(从 main 建);深读:总纲 00-overview.md、`docs/DESIGN.md`、`docs/COMPONENTS.md`、`src/mocode_tui/` 全部源码。

## 目标

**最高约束:对外渲染行为零变化。** 把内核迁入 `core/`、组件迁入 `widgets/`,新增 Theme 主题系统并贯通所有组件默认值,重建 root `__init__.py`,全部测试改 import。纯移动 + 默认值来源改造,不改任何渲染逻辑;demo 管道输出必须与 `ref/w1-demo-dump.txt` 字节级一致。

## 工单(按序执行,每项一个 commit)

### T1 内核迁入 `core/`

- `git mv` 以下文件到 `src/mocode_tui/core/`:`style.py text.py lines.py ansi.py block.py screen.py viewport.py painter.py app.py testing.py`。
- 新建 `core/__init__.py`:re-export 上述模块的全部现有公共符号(即现 root `__init__.py` 中来自这些模块的名字)。
- 修正包内相对 import(`from .style import` → `from .style import` 同级不变;组件与 keys 对内核的引用改为 `from ..core.style import` 形式)。`keys/` 包本波**不动**(它不 import 组件,若 import 内核则一并修正)。
- `src/mocode_tui/__init__.py` 重写:从 `.core` 与 `.components`(本波仍存在)re-export,保持现有 `__all__` 54 个名字一个不少、一个不多。
- 验证:`uv run pytest -q` 绿;`uv run python examples/pi_demo.py < /dev/null` 与基线 diff 为空。

### T2 组件迁入 `widgets/`

- `git mv src/mocode_tui/components src/mocode_tui/widgets`;`widgets/__init__.py` 保持原 `components/__init__.py` 的 re-export 内容(import 路径修正)。
- **删除**旧 `components/` 目录的一切残留;root `__init__.py` 改从 `.widgets` 导入。
- tests/ 中 `from mocode_tui.components...` 全部改为 `from mocode_tui.widgets...`;文件名 `test_components_*.py` 改为 `test_widgets_*.py`(`git mv`,内容仅改 import)。
- `examples/pi_demo.py` 若 import 了组件子模块路径则同步修正(它只应从包根导入,检查确认)。
- 验证:同上两条门禁。

### T3 Theme 主题系统

在 `core/style.py`(或新文件 `core/theme.py`,二选一,保持 style.py 单一职责则选后者)实现:

```python
@dataclass(frozen=True)
class Theme:
    # 语义色(现 style.py 常量)
    dim: Style = DIM; muted: Style = MUTED; accent: Style = ACCENT
    success: Style = SUCCESS; error: Style = ERROR; warning: Style = WARNING
    border: Style = BORDER; code: Style = CODE
    cursor: Style = CURSOR; selection: Style = SELECTION
    # 组件色带(现 components/message.py、tools.py、table.py 的模块常量)
    user_bg: Style = ...        # 原 USER_BG #1c2b3a
    tool_bg: Style = ...        # 原 TOOL_BG #16281c
    code_bg: Style = ...        # 原 CODE_BG #12181f
    table_border: Style = ...   # 原 TABLE_BORDER(无色)
    first_column: Style = ...   # Table 首列 #bc8cff
    # Markdown heading 阶梯(现 markdown.py 私有 _HEADING_STYLES)
    heading1..heading6 或 headings: tuple[Style, ...]

DEFAULT_THEME = Theme()
```

- 每个组件构造签名统一改造:所有 `style` 类参数默认值从模块常量改为 `None`,新增 `theme: Theme | None = None` 关键字参数;渲染时解析:`显式 style 参数 > theme 字段 > DEFAULT_THEME 字段`。theme 存于实例,渲染期生效。
- 组件模块内不再定义颜色常量;`USER_BG/TOOL_BG/CODE_BG/TABLE_BORDER` 删除,唯一来源是 Theme。
- Markdown 的 `_HEADING_STYLES`、`_TITLE_TONES`、`_NOTICE_LEVELS` 收编进 Theme(私有结构如何映射由实现者定,保证默认值渲染不变)。
- root `__init__.py` 增加导出 `Theme`、`DEFAULT_THEME`;语义常量(NONE/DIM/…)保持导出不变。
- **红线**:默认值必须逐项等于现状,渲染字节级不变。写完先跑 demo diff,有任何差异就是默认值抄错了,逐个核对。
- 新增 `tests/test_theme.py`:DEFAULT_THEME 字段值、组件 theme 注入生效、显式 style 优先于 theme、`dataclasses.replace` 自定义链路。
- 验证:全量测试绿 + demo diff 为空。

### T4 文档与杂项

- `docs/DESIGN.md`、`docs/COMPONENTS.md` 中的模块路径引用(`mocode_tui.style` → `mocode_tui.core.style`、`components.` → `widgets.`)全部更新;组件表中的色带常量出处改为 Theme 字段。**不新增**内容章节(W7 统一重写)。
- README.md 的组件表与 import 示例同步改路径;结构重写留给 W7。
- 删除 `keys/__init__.py` 注释中"transitional seams kept until R6"一类已过期表述若因迁移被触碰(不触碰则不动)。

## 验收(完成前自测,报告给真实结论)

1. `uv run pytest -q` 全绿,贴输出(用例数应 ≥ 203,新增 test_theme)。
2. `uv run python examples/pi_demo.py < /dev/null | diff - specs/2026-10-05-library-restructure/ref/w1-demo-dump.txt` 无输出(exit 0 且 diff 为空)。
3. `grep -r "mocode_tui.components" src tests examples docs README.md` 零命中。
4. `grep -rn "USER_BG\|TOOL_BG\|CODE_BG\|TABLE_BORDER" src/` 只出现在 Theme 定义处(常量名本身也应消失,字段名是小写)。
5. `uv run python -c "import mocode_tui; print(len(mocode_tui.__all__))"` 正常执行;`Theme`、`DEFAULT_THEME` 在 `__all__` 中。

## 禁触清单

- `keys/` 包内部实现(仅允许改 import 路径)、`pyproject.toml`、`uv.lock`、`specs/` 全部。
- 不改任何渲染/排版/解码逻辑;发现疑似 bug 记录进报告「未决问题」,不顺手修。

## 最终报告格式

工单状态表 / commit 清单(hash+message)/ 三条门禁的真实输出结论 / Theme 字段与旧常量的对照表 / 偏差与取舍 / 未决问题。
