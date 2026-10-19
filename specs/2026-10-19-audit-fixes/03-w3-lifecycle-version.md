# Spec audit-fixes · W3：生命周期与版本面（D3；F3/F6/F7/F8）
> ⏳ 待执行；前置：无；深读：`00-overview.md`（D3）。
> 主题：把"构造时挂上、就该能卸下"的约定补完整，消掉两处冗余/失效缺陷。

## 目标

1. **F3**：`Palette` 获得 `detach()`，与八个兄弟对齐（EveryHandle 约定）。
2. **F6**：`Find.detach()` 后真正 inert——卸载的 Find 不再吃键盘。
3. **F7**：gesture 的复制路径只经 `set_selection` facade invalidate 一次，删掉冗余直调。
4. **F8**：`__version__` 兜底对齐发行版，并有测试钉住。

## 工单（按序；每项完成跑 `uv run pytest -q -p no:cacheprovider`；本波不 commit）

### T1 `interaction/palette.py`：`detach()`（F3）

- 加 `detach()`：委托 `self._modal.detach()`（Modal 的 detach 已注销 overlay 并置 inert，
  与 Pointer/Toasts/Tooltip/Stats/Scrollbar/SelectionGesture/Find 的形状一致）。
- 幂等：重复调用安全（Modal.detach 已幂等——确认后沿用，别造第二种语义）。
- docstring：类 docstring 的挂载/卸载段补一句（构造即挂、`detach()` 卸）。
- 测试：构造 Palette → `detach()` → 断言 frame overlay 注销（照 Modal/Toasts 现有测试的
  断言形状写）→ 再 `detach()` 不炸；`close()` 与 `detach()` 语义不同（隐藏 vs 卸载）各测一条。

### T2 `interaction/find.py`：detach 后 inert（F6）

- `__slots__` 加 `_detached`；`detach()` 置位；`handle()` 入口处 `if self._detached: return False`
  （与 Pointer/Toasts/Modal/Stats 一致）。`close()` 的语义不变（关闭 ≠ 卸载）。
- 测试：挂载 → `detach()` → 任意键 `handle` 恒 `False`；未卸载时行为不变（回归）。

### T3 `interaction/gesture.py`：删冗余 invalidate（F7）

- `:572` 附近的 `self._tui.invalidate()` 删掉，只保留紧随的 `set_selection(...)`——
  `app.py:856` 的 `set_selection` 自身会 invalidate（先读代码确认这条链，再删）。
- 验证 repaint 次数不增不减：一次完整 drag+release = 恰好一次 invalidate（用现有测试的
  计数形状，或临时探针计数后转成断言）。
- 若发现 `set_selection` 只在"选择真的变了"时 invalidate 而原直调是 unconditional——
  停下报告，把差异写清楚再决定（不许静默改变 repaint 语义）。

### T4 `src/motui/__init__.py`：版本兜底（F8）

- `:82` 的 `"1.1.0"` → `"1.1.6"`，与 `pyproject.toml:7` 和发行版一致；docstring（:75-78）
  承诺"falls back to the number of the release it is cut from"由此成立。
- 测试钉住：在打包相关测试文件里加一条——从 `__init__.py` **源文**正则提取兜底字面量，
  与 `pyproject.toml` 的 `version` 比对相等（不 import、不依赖安装状态，source checkout 也跑得到）。

### T5 全量回归

`uv run pytest -q -p no:cacheprovider` 贴总数（基线 1539/1 + 本波新增）。

## 验收

1. pytest：贴总数/失败数/新增条数
2. Palette：detach 注销 overlay、幂等、close/detach 语义分清（贴测试名与输出）
3. Find：detach 后 handle 恒 False（贴测试名与输出）
4. gesture：一次 drag+release = 一次 invalidate（贴计数证据）
5. 版本兜底测试存在且 source checkout 下可跑（贴输出）
6. `uv run python -m motui < /dev/null` exit 0

## 禁触清单

- 只改：`src/motui/interaction/{palette,find,gesture}.py`、`src/motui/__init__.py`、
  对应测试文件（先 `ls tests/`，只碰测这三个 tier 与打包/版本的文件）。
- 禁触：`kernel/`、`widgets/`、`app.py`（除读取外）、`docs/`、golden、`CHANGELOG.md`、`specs/`。
- 不 commit / 不建分支 / 不 push。

## 报告格式（最终消息，中文）

工单状态表（T1–T5）/ 每个修复的测试名与断言 / gesture repaint 计数证据（改前 vs 改后）/
版本测试的提取方式 / 自测真实输出 / 偏差与未决。
