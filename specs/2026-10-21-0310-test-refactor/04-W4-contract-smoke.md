# W4 · 契约 / smoke / invariants + 终验（lead 执行）

> 前置 W1–W3 已合并；写入范围 `tests/test_api.py`、`tests/test_packaging.py`、
> `tests/test_smoke.py`、`tests/test_invariants.py`，以及旧 meta 测试的删除。

## 目标

收口“非行为测试”：只保留最少的公开面契约、打包一致性、demo smoke、全组件渲染不变量。
删除文档/README/demo IA/golden 的 pytest 镜像。然后跑完整终验。

## 工单

### T1 删除 meta 测试

```bash
git rm tests/test_docs_claims.py tests/test_readme_examples.py \
       tests/test_demo_model.py tests/test_demo_topics.py tests/test_demo_protocol.py \
       tests/test_golden_frames.py tests/test_api_root.py tests/test_render_invariants.py
```

（`tests/golden/**` 与 `tools/golden.py` 保留；CI 继续跑。）

### T2 `tests/test_api.py`（简化版）

只测结构，不 pin 名单：

1. 每个 facade（`motui`、`motui.kernel`、`motui.keys`、`motui.widgets`、`motui.interaction`、
   `motui.app`、`motui.testing`）的 `__all__` 无私有名、每个名字 `hasattr` 可解析。
2. 根 `__all__` 的每个名字都能在某个层 `__all__` 中找到（根是层的 curated 子集）。
3. `motui.testing.__all__` 仍是三名字（公开测试面稳定）。

不测：34/40/44 的精确数量、名字顺序、`Shed` 名单、`DOWN_LISTED` 路径表。

### T3 `tests/test_packaging.py`（2 个）

- 版本是 `X.Y.Z` 且 `motui.__version__` 与 `pyproject.toml` 一致（源码 checkout fallback 允许）。
- 分发元数据：名称 `motui`、MIT license、sdist 排除 `specs`（从 `pyproject.toml` 读，不硬编码版本号）。

### T4 `tests/test_smoke.py`（2 个）

- `python -m motui --pages`（用 `main()`/`script` 的公开入口，不 subprocess 或 subprocess 都行）遍历全部
  topics 不抛异常，输出非空、每个 topic 至少一行。
- `render_topic(topic)` 对 `TOPICS` 每个 topic 返回非空字符串且以 topic header 开头（不检查内容/布局）。

不测：58 的数量、section 顺序、topic 模板、组件覆盖、旧模型消失。

### T5 `tests/test_invariants.py`（1–3 个）

保留并合并旧 `test_render_invariants.py`：

- 组件矩阵：所有公开 widget 类 + `Text`/`Markdown`，每个一个 factory；至少覆盖 `widgets.__all__` 里的
  所有 `Component`（显式完整性断言：缺 factory 就失败）。
- 宽度矩阵：`(0, 1, 2, 3, 7, 20, 80)`。
- 一个参数化测试或一个循环测试，断言三性质：
  1. 幂等：`render(w)` 两次相等；
  2. 有界：每行 `Line.width <= w` 且 `visible_width(text) <= w`；
  3. 无漂移：中间渲染别的宽度后，再 `render(w)` 仍等于第一次。
- 不用 281 个独立 case；用 1 个函数 + 循环（失败信息带组件名/宽度）。

### T6 终验（lead）

1. 全量 `pytest -q -p no:cacheprovider`：0 failed，记录总数（目标 600–850）。
2. `python tools/golden.py --check`：58 topics match。
3. `python tools/framebench.py`：exit 0，render-hash `f872...`。
4. `python -m motui < /dev/null` / `--pages`：exit 0。
5. `python -c "import motui, motui.kernel, motui.keys, motui.widgets, motui.interaction"`：无环。
6. `git diff --stat <base>...HEAD`：只动 `tests/**`、`specs/<group>/**`。
7. `grep -R "\._[a-z]" tests --include=*.py`：仅允许 `__dunder__`。
8. `grep -R "sleep(" tests --include=*.py`：0。
9. `find tests -name "test_*.py"`：与目标目录一致；旧文件全删。
10. 汇总报告：数量对比、删除清单、保留清单、遗留风险。

## 禁触

`src/**`、`tools/**`、`tests/golden/**`、`tests/testing/**`、`pyproject.toml`、`CHANGELOG.md`、`docs/**`。

## 交接

在 `specs/<group>/handoff/W4-lead.md` 写终验事实（数字、命令、diff）。
