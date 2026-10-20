# W4 交接包（lead）
> 分支 main / 起点 `966734d` / 2026-10-21

## A. 自动事实

### 用例数与耗时

| 目录 | 用例数 |
|---|---|
| `tests/kernel` | 219 |
| `tests/keys` | 55 |
| `tests/widgets` | 324 |
| `tests/app` | 49 |
| `tests/interaction` | 161 |
| 根级（api/packaging/invariants/smoke） | 16 |
| **合计** | **824**（改前 2190，−62%） |

- 全量：`824 passed in 3.53s`（改前 2190 passed / 2 skipped / 12.5s）
- 文件数：63 → 55 个测试文件，按层分 5 个目录 + 4 个根级契约文件。

### 终验命令与真实结果

```text
pytest -q -p no:cacheprovider                 824 passed, 0 skipped, 0 failed (3.53s)
python tools/golden.py --check                golden: 58 topics match
python tools/framebench.py                    exit 0, render-hash f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1
python -m motui --pages                        exit 0
python -m motui < /dev/null                    exit 0
import motui, motui.kernel, motui.keys, motui.widgets, motui.interaction   ok
```

### 静态审计

```text
grep -RIn "\.[_][a-z]" tests --include=*.py | grep -v "__"   0
grep -RIn "sleep(" tests --include=*.py                      0
grep -RIn "revision()" tests --include=*.py                  0
grep -RIn "_doubles" tests --include=*.py                    0
pytest.mark.skip / xfail / pytest.skip                      0
```

### 变更范围

- `src/**`、`tools/**`、`pyproject.toml`、`docs/**`：零 diff。
- `tests/**`：全部重排；旧 63 个平铺文件删除或替换为 55 个分层文件。
- `tests/testing/**`：W0 新增；W4 补 `document()` / `tick()` 两个共享 helper。
- `tests/golden/**`：只改 README 里“测试也断言 golden”的过期句子；基线文件未动。

## B. 只存在于脑子里的东西

### 删除判据的落地

- **文档镜像**：`test_docs_claims.py`、`test_readme_examples.py` 整文件删除。
- **demo IA/协议镜像**：`test_demo_model.py`、`test_demo_topics.py`、`test_demo_protocol.py` 整文件删除；
  改由 `tests/test_smoke.py` 跑两条真实入口 + 全 topic 渲染，不再 pin 58 个 topic 的模板/数量/组件覆盖。
- **golden 双门禁**：`test_golden_frames.py` 删除；`tools/golden.py --check` 是唯一逐字节视觉门禁（CI 已跑）。
- **API 名单 pin**：`test_api_root.py` 删除 34/40/44 的精确名单与旧名清单；`test_api.py` 只保留
  “facade 名字可解析、无私有名、根名字有层归属、testing 三名字稳定”。
- **实现镜像**：各波删掉 `_width`/`_prefix` 缓存、revision/snapshot、sealed block 到达屏幕、
  viewport/frame/painter 的 memo 同一性、scrollbar memo key、`invalidate exactly once` 等。
- **重复路径**：逐组件复制的 hover/focus/disabled/glyph 宽度测试收敛为参数化或单测内的代表矩阵；
  `test_widgets_form.py` 与 `test_widgets_forms.py` 合并；`test_widgets_basics.py` 按 Tabs/Tree 拆开。

### 有意不再覆盖

- 文档 prose、README 代码块、docs 链接/计数/陈旧名。
- demo 的 section 顺序、topic 数量、八块模板、组件覆盖声明。
- `Revisioned.revision()` 作为断言对象；缓存命中/失效路径。
- 平台无声明的 POSIX-only source 分支（基线在 Windows 本就 skip；新 `test_sources.py` 用真实 pipe 覆盖
  cooked fallback/EOF/close，跨平台可跑）。
- 精确全帧字符串（除 ansi/screen/painter/decoder 这些“字节即产品”的层）。
- 迁移考古（旧 Page/Exhibit、stale names、旧常量逐字段相等）。

### 取舍

- `test_invariants.py` 用 1 个循环覆盖 38 个组件 × 7 个宽度（266 次检查），不是 281 个独立 case：
  失败信息带组件名/宽度；新增公开 `Component` 而没加 factory 会被完整性问题抓住。
- 多个文件为落进用例预算，把参数化矩阵改成测试内循环；语义覆盖保留，collected case 减少。
- `tests/testing/` 是唯一共享入口；`motui.testing` 保持三名字不变，没有扩大公开 API。
- 旧 `tests/_doubles.py` 在 W0 作为临时桥保留，W4 删除；`tests/conftest.py` 同步去掉 `tests/` 的 path 注入。

### 已知风险

- **跨平台**：新 `test_sources.py` 用 `os.pipe` + `asyncio.wait_for`，Windows 已绿；Linux CI 未在本机跑，
  但所有平台分支都在 `motui.keys.console` 的纯 mapper 与 VT 路径上，未调用 `kernel32`。
- **demo smoke**：`test_smoke.py` 的 piped 入口会跑完整 scripted replay（约 0.3s），是本套件最慢的测试；
  如果未来变慢，优先保留 `--pages` 与全 topic 渲染，piped 可降为 1 个。
- **invariants**：只保证“不溢出/幂等/不漂移”，不保证视觉正确；视觉正确由 golden 工具负责。
- 版本仍是 1.1.8；W8 发版等用户指令。

## C. 指针

- spec：`specs/2026-10-21-0310-test-refactor/00-overview.md`
- 共享层契约：`ref/interfaces.md` §1
- 三波 handoff：`handoff/W1-kernel-keys.md`、`W2-widgets.md`、`W3-app-interaction.md`
- 目标目录：`tests/kernel/`、`tests/keys/`、`tests/widgets/`、`tests/app/`、`tests/interaction/`
- 根级契约：`tests/test_api.py`、`tests/test_packaging.py`、`tests/test_invariants.py`、`tests/test_smoke.py`
- 视觉门禁：`tools/golden.py` + `tests/golden/`
- 基线 commit：`00b7515`（W0）；W1/W2/W3 合并见 `git log --oneline --merges`
