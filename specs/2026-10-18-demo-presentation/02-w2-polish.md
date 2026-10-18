# Spec demo-presentation · W2 精修与手册（波次 W2）

> 分支 `pres2-polish`；前置：W1（语法/骨架/机械改版已合并）；深读：`00-overview.md`
> （骨架、D3–D5）、W1 报告里的"被删 API 行清单"。
> **最高约束：呈现只减不增——本波之后每页的散文行数应 ≤ section 数（每节一行 caption），
> 签名只活在 notes；交互行为与展位集合不变。**

## 工单

### T1 captions 精修（11 页）

- 逐页把 caption 收敛成**状态枚举优先**（`default · hover · focus · disabled`）；
  读序按业界共识（default → variants → states → 组合）重排 section；
  没有 caption 更清楚的 section 果断留空。
- 页面 blurb（页规则后的那句）统一 ≤1 行、事实性（是什么，不写"试试看"）。
- 报告里给一张"每页 section 数 / caption 数 / 行数（改前 → 改后）"的对照表。

### T2 `notes` 升级为完整手册

- 结构：① 怎么玩（tab/方向键/enter/鼠标/拖选复制/`c-n c-p`/`c-f`/`c-g`/`--pages`/piped——
  全文一次说清）② 页面导览（三组 + 每页一句）③ **签名速查**（W1 清单收编：
  按族列全部构造签名，` ``` ` 代码块渲染）④ 提示条/交互模型的说明。
- README 的 demo 段与它的页清单同步（W1 机械改版后若有出入）。

### T3 收尾

- `tests/test_demo_protocol.py`：按定稿页面与 rail 分组跟改（W1 已最小修的部分复核）。
- `docs/COMPONENTS.md` 的 demo 段与 `CHANGELOG.md` 的 `## Unreleased` → Changed
  加一条（demo 呈现规范化：分组 rail、统一页面模板、散文归 notes）。
- `tools/golden.py --update` 定稿 11 页（逐页解释相对 W1 的差异）。
- `tools/framebench.py` hash 登记/解释。

## 验收

1. `uv run pytest -q` 全绿
2. `uv run python tools/golden.py --check` → 11 页全等
3. `uv run python tools/framebench.py` → 登记
4. demo 两入口 exit 0；`--pages` 逐页人工可读（贴 overview/forms/notes 三页的 dump 节选）
5. `grep -rn "API ·\|TRY ▸\|play ▸" src/motui/demo` → 零命中

## 禁触清单

`src/motui/**` 全部只读（`widgets/` 含 `navlist.py`）、`demo/{kit,page,session,script,shell,assets}.py`
只读（除 T3 允许的最小对字）、`tools/**` 除 golden `--update`、`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 对照表（per page 行数）/ 偏差与取舍 / 未决问题。
