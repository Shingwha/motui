# W3b 交接包（TextBuffer.value 缓存 · M6）
> 分支 `fp-w3b-value-cache` / 起点 cbca819（main 含 W1 `789da41`；与 W2 并行，文件级不相交）/ 2026-10-22

## A. 自动事实

`git diff main --stat`：恰好 2 个写入范围文件——`src/motui/widgets/textbuf.py`
（+30 −3）、`tests/widgets/test_editing.py`（+39）；禁触清单零 diff，工作树干净。

落地内容（语义零变化）：

- `TextBuffer.__slots__` 增 `_value_cache: str | None` + `_value_version: int | None`
  （构造均 `None`）；`value` 属性：version 命中返回缓存 **同一 str 对象**，否则 join、
  存、返回。编辑方法零改动（它们已经 bump version，缓存自然置脏）。
- P8 措辞落两处 docstring：`value`（"缓存键 version；直接改 `lines` 不 bump version，
  `value` 不跟随"）与类 docstring 的 `lines` 句（`lines` 是 slot，无常驻属性 docstring，
  类文档是其描述位）。`lines` 未改成 property（P8 红线）。

开工复核（工单点名项，全部通过，无阻塞）：

- `grep -rn "\.lines\[" src/motui`：命中全部在 `textbuf.py` 自身（写点内就地改，逐一
  后跟 `_changed()` → version+1）与 `markdown/blocks.py:323,334`——后者 `self.lines`
  属 `_BlockScan`（:273/:305）自己的 `list[str]` 参数，与 TextBuffer 无关（P8 复核成立）。
- TextBuffer 消费文件（app/focus.py、widgets/menubar.py、indicators.py、textfield.py、
  tabs.py、strip.py、core/block.py）对 `.lines` 的引用全部是 `core.lines`（Line/Segment
  类型）import，**无一处**访问 `TextBuffer.lines`——motui 内部无外部就地改动/整体赋值。
- `set_text`（textbuf.py:578）**无条件** `_changed(structural=True)`；`clear`（:559）有
  变化才 bump（空 buffer 上 clear 是 no-op 早退、不 bump——内容未变，缓存仍正确，非 bug）。

基线与验收命令真实结果（本机）：

| 门禁 | 开工基线 | 波末 |
|---|---|---|
| `uv run pytest tests/widgets -q` | 322 passed | **326 passed**（+4 新增） |
| `uv run pytest -q` | 897 passed | **901 passed**，0 failed |
| `uv run python tools/golden.py --check` | — | **golden: 57 topics match** |
| `render-hash` | — | `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（逐字） |

framebench 全 9 行（波末实跑）：stream-single 0.9 / stream-split 4.7 / scroll 0.4 /
scroll-long 1.4 / text-open 0.1 / table-open 0.1 / stream-paragraph 0.6 / replay 367 ms /
render-hash 逐字红线值——本波不触渲染路径，符合 overview 预期（W3b 不做 bench 行，
以单测断言缓存命中）。

## B. 只存在于脑子里的东西

- **缓存键的保证边界**：version 单调且每个 motui 内部写点都 bump，所以 motui 内
  version 相等 ⟹ value 相等；唯一缺口是**外部**直接改公开的 `lines` 不 bump（P8 已
  写进 docstring）。宿主若这么干，`value` 不跟随——既有事实，不是本波引入。
- **同一性承诺的范围**：两次读之间无写 → 同一 str 对象；任何写（含 `set_text` 同文
  重设、undo/redo）→ version 变 → 重 join，返回相等但**可能不同一**的新串。语义红线
  是"同样调用序列返回同样字符串"（相等），满足。
- **空串可缓存**：命中判定是 `cached is not None`（非真值判断），空 buffer 的 `""`
  正常进缓存、正常命中。
- **测试落点**：`tests/widgets/test_editing.py` 末尾新节 `# -- the value cache --`
  （:453 起）4 条，直接构造 `TextBuffer(..., keymap=DEFAULT_EDITOR_KEYMAP)`（经
  `motui.widgets.textbuf` 导入；`motui.widgets` 门面不导出 TextBuffer，无需改 `__init__`）。
  对象同一性断言即"第二次读不再 join"的直测。
- 与 W2/W3a 零耦合：本波不新增公共 API、不改任何签名，合并顺序无关（W2 → W3b 只是
  组内排序惯例）；lead 收尾 `CHANGELOG.md` 可提一句 value 每键读从 O(全文) 变 O(1) 命中。

## C. 指针

- `textbuf.py:142-143` slots / `:189-193` 构造初始化 / `:208-225` `value` 缓存 /
  `:230` `version` 属性（未动）/ `:544` clear（:559 bump）/ `:561` set_text（:578 bump）。
- `tests/widgets/test_editing.py:453` 起新增 4 条。
- commit：`4eb8cba`（T1 value 按 version 缓存）→ `6311d1c`（T2 测试 ×4）→ 本 commit（handoff）。
- 既有测试零修改：322 条 widgets 既有用例全绿，`tests/core/**`、`tests/app/**` 零 diff。
