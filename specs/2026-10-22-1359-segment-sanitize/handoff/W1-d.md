# Handoff · W1 Segment 门净化（worker D / 分支 ss-w1-segment-door）

> 2026-10-22。基线 main `19df592`；本波 4 commits（T1 `b49d46a` → T2 `18fef63` →
> T3 `20bca4f` → handoff）。写入范围：`src/motui/core/lines.py`、
> `tests/core/test_lines.py`、`docs/DESIGN.md` + 本文件，零越界。

## A · 门禁与哨兵（前后对比）

| 门禁 | 开工基线 | 波末 | 结论 |
|---|---|---|---|
| `uv run pytest -q` | 909 passed | **913 passed**（+4 新增，既有零修改） | 绿 |
| `uv run python tools/golden.py --check` | 57 topics match | **57 topics match**（未重录） | 绿 |
| `render-hash` | `a82f7968…a4f379` | **逐字同串** `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379` | 绿 |
| `idle-long`（哨兵） | 0.6 ms/frame | **0.6 ms/frame**（安静窗口判据 ≤ 0.7 成立） | 不回退 |
| `text-open`（哨兵） | 0.1 ms/frame | **0.1 ms/frame** | 不回退 |
| stream-single / scroll / scroll-long / table-open | 0.8 / 0.5 / 0.7 / 0.1 | 0.8 / 0.4–0.5 / 0.7 / 0.1 | 带内 |
| stream-split | 4.5（开工单次） | 4.9 / 4.7（两次隔离跑） | 见 B·快路径实测 |
| stream-paragraph | 0.6 | 0.7–0.8 | 带内 |
| replay | 364 ms | 358–366 ms | 带内 |
| 端到端 §2.2 原脚本 | `assert injected in output` | **断言反向成立**：`HeadlessScreen.output`（97 bytes）不含 `\x1b[?1000l` / `\x1b[?1006l` / `\x1b]52;` / `\x1b]0;`，尾部只剩 ansi.py 合法字节（RESET、光标移动、EL、同步对） | 绿 |
| `git diff main --stat` | — | 仅 DESIGN.md / lines.py / test_lines.py（+handoff） | 合 |

## B · 交接要点

### 净化函数最终形态（lines.py）

```python
_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")


def _cells_only(text: str) -> str:
    if "\t" in text:
        text = text.replace("\t", " ")  # the repo's tab rule: one tab, one space
    if _CONTROL_RE.search(text) is None:
        return text  # the fast path: the same string, nothing allocated
    return _CONTROL_RE.sub("", text)
```

`Segment.__post_init__`：`text` 过 `_cells_only`；`link is not None` 时同门，
**净化后为空串置 `None`**（空 OSC 8 目标无意义）。`_width` 是惰性缓存且净化发生在
任何度量之前，宽度自动一致；`with_style()` 重建自动过门，幂等。显式集不用
`str.isprintable()`（保住 ZWJ/组合标记/肤色 emoji，已冒烟验证）。`text.py`
`_normalize_tabs` / `wrap_line` / `slice_line` 的既有归一未动（同规则，幂等冗余）。

### 快路径实测（构造开销）

- 微基准（200k×5 次取最小，同进程含裸对照）：
  裸 frozen+slots dataclass（无门）**269 ns**；`Segment` 干净文本（快路径）
  **700 ns**（门开销 ≈ **+430 ns** = `__post_init__` 调用 + `\t` 成员测试 + 正则
  search，零分配）；含 tab **716 ns**（+16 ns，一次 replace 分配）；含控制符
  （慢路径 sub）**1134 ns**。
- 真实场景 A/B（进程内交错 4 轮，`_cells_only` 补丁为恒等模拟无门）：
  stream-split 有门中位 **4.75** vs 无门 **4.64 ms/frame**——门在该热路径的真实
  成本 ≈ **+0.1 ms/frame（~2%）**，与运行间噪声重叠；即波末 stream-split 4.7–4.9
  对基线 4.5 的差主要是噪声 + 这 ~0.1 ms，属漂移带内，两个具名哨兵不动。

### T0 审计结论：零命中

1. 静态：`tests/golden/` 58 个文件逐字节扫描——非 ESC 控制字节 **0**（仅文本文件
   自身的 CRLF 行尾），tab **0**，ESC **0**（fixtures 是纯文本可视快照，非字节流）。
2. 动态：临时探针挂在 `_segment_bytes` 入口（打印 text/link 中的 \t 或 C0/DEL/C1，
   用后 `git checkout` 还原、未提交），跑全量渲染路径——pytest 909 条 **0 命中**、
   golden 57 topics **0 命中**、framebench 全场景含 replay **0 命中**。
   **无任何"字节合法变化"内容，无 golden 重录问题。**

### 与安全文档/工单的偏差清单

1. **5.1"保留 \t"** → 已被 lead 推翻，按 S3 归一为一个空格执行（照办，非偏差）。
2. **工单 T2/安全文档 §6 的示例断言与 T1 机制自相矛盾，按拍板表执行**：
   - `Segment("a\x1b[?1000lb").text == "ab"` 与 `line.text == "ab"`：`_CONTROL_RE`
     只删控制字节本身，剩余可打印字符 `[?1000l` 成为**惰性 cells**（无法驱动终端，
     S6 口径"控制字符不再原样到达终端"），故实测 `"a[?1000lb"`。测试按机制断言。
   - "`.styled()` 字节不含 `\x1b`" 字面不可能：styled() 恒以 ansi.py 的 RESET
     （`\x1b[0m`）收尾。按门禁 4 的形式断言注入序列整体（`\x1b[?1000l` 等四个）
     不出现。
   - `link="\x1b]8;;evil" → link is None`：删 ESC 后剩 `"]8;;evil"` 非空，按 T1
     规则（空串才置 None）保留为已净化 payload。安全性不受影响：OSC 8 只能被
     BEL/ST（均含控制字节）提前终止，删净后 link 无法越界。None 案例用
     `link="\x1b\x07"`（净化后空串 → None）断言。
   - 若 lead 的本意是"整序列剥离"（连 `[?1000l` 可见残余也删），那是 SGR/序列解析
     组件（AnsiText）的领地，overview 已明确不做、不在本组——请 lead 知悉此口径。
3. 测试数：4 条（S7 预算内），幂等断言并入第 1 条。

### 冒烟与端到端补录

- §2.1 形态：`Line.from_text("OUT: \x1b[?1000l\x1b[?1006l").styled()` →
  `'OUT: [?1000l[?1006l\x1b[0m'`——注入 ESC 消失，残余为惰性可见字符 + 合法 RESET。
- emoji/组合序列零影响、`\r\n` 删除（`"a\r\nb" → "ab"`）、with_style 幂等均已断言。

## 未决问题

- 无阻塞。偏差 2 的"整序列剥离 vs 字符集删除"口径请 lead 在收尾时知悉/背书。
- CHANGELOG 由 lead 收尾统一写（契约句：rendered text is cells, never terminal
  commands; escapes are constructed only by ansi.py; a tab normalizes to one
  space at the Segment door）。
