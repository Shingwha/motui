# Spec MOTUI · W6：测试层精简（波次 W6）

> 分支 `rl6-tests`；worktree `C:/Users/shifu/.worktrees/mocode-tui/rl6-tests`；
> 前置：W3 + W4 + W5 全部合并；深读：`00-overview.md` + 本文件（**唯一的裁剪清单**）

## 目标

把测试层裁到「一条命令能读完的高价值核心」：删掉冗余、脆弱、低信号、重复参数化的用例，
并合并同类测试文件。**不删任何契约门禁，不删任何历史回归钉。**

## 侦察结论（lead 已核实，别再重新论证）

- 结构：44 个 `tests/test_*.py` + `tests/_doubles.py`（18 个文件共用，保留）+ `tests/golden/`（门禁 fixture，保留）。
- **没有任何一个文件该整份删掉**：每份都至少持有一条覆盖率下限要求的行为。本波全部是 **TRIM**。
- 分类口径（每个被删的用例都要能归到一类，报告里逐条标）：
  - **b1 冗余**：同一行为另有保留的用例在断言（报告里点名那个保留者）。
  - **b2 脆弱**：断言的是实现细节（私有 helper 的等价性/调用次数、内部迭代顺序、挂钟时间、平台琐事），
    不是对外行为。
  - **b3 低信号**：常识性属性（`__repr__` 字符串、`isinstance` 能力探针、dataclass 默认值、
    「构造器存下了参数」这类）。
  - **b4 重复参数化**：同一性质的第 N 个参数点。

## 工单（按序执行，每项一个 commit）

### T1 起手基线

- `uv sync`，然后 `uv run pytest -q` 记下**真实用例数**（W3/W4/W5 会改动它；本文件里的
  「now」列是 2026-10-17 侦察时的数字，用于定位，不是断言）。
- 把基线与逐文件的当前用例数写进报告。

### T2 按清单裁剪（这是本波主体）

逐文件执行下表。`删` = 删掉列出的用例；`参数收窄` = 保留用例但减少参数点；
`保留` = lead 已裁定不删（**不要**再删它们）。

| 文件 | 动作 |
|---|---|
| `test_core_text.py` | 删 `test_ellipsize_tail`（b1：`test_ellipsize_tail_keeps_its_documented_shape` 已覆盖）；删 `test_terminal_size_reports_positive_columns_and_rows`（b2 真 tty 琐事）；删 `test_styled_with_matches_styled_on_truecolor`（b1：`test_styled_with_downgrades_each_segment_and_never_caches` 覆盖） |
| `test_selection.py` | 删 `test_a_range_spanning_blocks_marks_both_sides`（b1：`test_backwards_drag_normalizes_direction_into_the_same_range`）；参数收窄 `test_wide_character_boundaries_never_split_a_double_width_cell` 的切点 `[1,2,3,4,5,6]` → `[1,3,6]`（b4） |
| `test_viewport.py` | 删 `test_the_layout_carries_the_window_offset_and_total_rows`（4 例，b1：`test_the_window_equals_full_materialization_at_any_address` 覆盖同字段）；删 `test_a_layout_without_scroll_state_defaults_to_nothing_known`（b3 默认值） |
| `test_screen.py` | 删 `test_headless_records_the_real_enter_leave_brackets`（b1：`test_the_default_bracket_pins_its_exact_bytes` 逐字节同序列）；删 `test_both_screens_satisfy_the_protocol`（b3）、`test_headless_simulates_a_resize_by_setting_dimensions`（b3，真实 resize 由 scrollbar/toast 重排用例覆盖） |
| `test_gesture.py` | 删 `test_a_press_anchors_the_reported_cell`（b1：`test_a_press_anchors_the_cell_the_hit_test_resolves` 的 (0,0) 特例）、`test_a_press_resolves_the_document_row_the_layout_shows`（b1）；参数收窄 `test_the_word_run_is_the_maximal_non_whitespace_stretch` 14 → 8（b4） |
| `test_keys_sources.py` | 删 `test_console_drag_is_identical_under_the_hover_switch_either_way`（b1：`test_console_press_drag_and_release_surface_all_three_kinds`） |
| `test_frame.py` | 删 `test_an_empty_registry_hands_the_composed_layout_through`（b1：`test_an_overlay_that_rewrites_nothing_leaves_the_layout_alone`）；删 `test_splice_row_resolves_its_base_cuts_in_one_walk`（b2 私有 helper 等价性）；**保留** `test_the_survivors_tile_the_span_exactly_after_a_close`（lead 裁定：跨 span 的 close 后铺满是真几何契约） |
| `test_widgets_statusline.py` | 删 `test_matches_the_demo_status_row_row_for_row`（b1/b2：`_expected` 复述实现，`test_the_row_composes_left_gutter_right` 已覆盖） |
| `test_widgets_editing.py` | 删 `test_repr`（b3）、`test_is_a_component`（b3）、`test_the_fields_are_clickable`（b3，点击行为另有覆盖）、`test_place_reports_a_hit_when_the_cursor_already_sat_there`（b3）；**保留** `test_default_keymap_is_stored_when_none`（lead 裁定：默认键图被采纳是真接线） |
| `test_widgets_basics.py` | 删 `test_narrow_widths_never_overflow`（23 例，b1）——**同 commit 必须**把 `tests/test_render_invariants.py` 的 `WIDTHS` 里补上 `0`（把丢掉的窄宽收益收进 D12 门禁）；删 `test_is_a_component`、`test_the_frame_and_label_are_the_state_a_host_paints`、`test_empty_tabs_render_one_empty_row`、`test_a_focused_strip_renders_the_same_bytes_as_the_default`、`test_a_focused_tree_renders_the_same_bytes_as_the_default`（b3）；删 `test_custom_frames_cycle`（b4：`test_advance_steps_the_cycle_and_wraps`） |
| `test_widgets_choice.py` | 删 `test_option_fields_and_defaults`、`test_choice_components_are_clickable`、`test_the_menu_family_is_activable`、`test_the_menu_family_is_focusable`、`test_a_focused_menu_renders_the_same_bytes_as_the_default`（b3） |
| `test_widgets_forms.py` | 删 `test_radio_declares_its_capabilities`、`test_slider_declares_its_capabilities`（b3） |
| `test_widgets_action.py` | 删 `test_the_action_primitives_declare_their_capabilities`、`test_the_action_primitives_declare_a_hint_slot`（b3） |
| `test_widgets_list.py` | 删 `test_the_result_is_hoverable_focusable_clickable_and_activable`（b3） |
| `test_widgets_autocomplete.py` | 删 `test_autocomplete_is_a_select`（b3） |
| `test_widgets_table.py` | 删 `test_the_table_is_clickable_activable_and_focusable`（b3） |
| `test_container_hit.py` | 删 `test_hoverable_is_a_runtime_protocol_over_one_flag`、`test_container_is_a_runtime_protocol_over_child_at`、`test_the_layout_containers_implement_child_at`（b3；`descend`/`child_at` 行为用例全保留） |
| `test_focus.py` | 删 `test_repr_names_the_ring_and_its_focus`（b3） |
| `test_app.py` | 删 `test_read_key_escape_hatch_reads_the_raw_source`、`test_headless_tui_wires_a_recording_screen_and_scripted_keys`（b3） |
| `test_widgets_markdown.py` | 删 `test_the_shared_registries_are_immutable_and_the_factories_fresh`（b2/b3 内部表卫生） |
| `test_style.py` | 删 `test_reset_constant`、`test_style_is_frozen_and_hashable`（b3）；删 `test_the_prefix_is_computed_once_even_when_it_is_empty`、`test_sgr_prefix_truecolor_delegates_to_the_instance_cache`（b2：对私有 `_sgr_codes` 的 monkeypatch 调用计数；性能地板由 framebench 守） |
| `test_theme.py` | 删 `test_default_theme_is_a_plain_theme_instance`（b3） |
| `test_block.py` | 删 `test_component_protocol_is_duck_typed`、`test_block_state_is_open_or_sealed_only`（b3）；`test_block_initial_views_and_pin` 里的 pin 校验 `ValueError` 断言**先移到**附近的保留用例里再删该用例（别丢掉这条真实校验） |
| `test_painter.py` | 删 `test_rows_are_empty_before_the_first_paint`（b3） |
| `test_pointer.py` | **保留** `test_every_key_and_paste_is_left_alone`（lead 裁定：指针层不吃键/粘贴是真契约） |
| `test_keys.py` | 删 `test_events_are_frozen_and_the_source_protocol_is_structural`（b3） |
| `test_ansi.py` | 删 `test_enable_vt_returns_bool`（b3） |
| `test_chrome_toasts.py` | 删 `test_construct_attaches_the_overlay_and_detach_is_reported_clean`（b3 repr；attach/detach 成员关系另有覆盖） |
| `test_decoder_fuzz.py` | 删 `test_the_matrix_covers_the_promised_seeds_and_lengths`（b3 自指的元测试）；fuzz 不变量全保留 |
| `test_widgets_syntax.py` | 删 `test_default_highlighter_is_built_once_and_is_a_highlighter`（b3） |
| `test_widgets_containers.py` | 删 `test_padding_is_a_component`（b3） |

**不许删**（门禁与历史钉，逐条 protected）：

- 门禁：`test_api_root.py`、`test_api_doc.py`、`test_golden_frames.py`、`test_readme_examples.py`、
  `test_render_invariants.py`（除 T2 里**加**一个 width 0 外不动）、`test_packaging.py`。
- 历史回归钉（都带 wave/D 编号注释）：`test_ansi.py` 的 mouse-tracking 两例；
  `test_screen.py::test_the_default_bracket_pins_its_exact_bytes`；
  `test_keys_sources.py::test_console_bytes_assemble_escape_sequences_across_records`；
  `test_keys.py::test_a_paste_end_marker_split_across_feeds_still_closes_the_paste`；
  `test_core_text.py` 的 VS16 / 属性重置 / cluster 窗口 / D17 字素家族；
  `test_frame.py::test_splice_row_tiles_a_frame_row_across_cluster_boundaries`；
  `test_app.py`、`test_gesture.py` 里带 D4/D5/D8 的 divider/滚轮/reflow 用例；
  `test_theme.py::test_default_theme_matches_the_old_module_constants`；
  `test_widgets_statusline.py::test_the_row_locks_its_bytes_after_the_move`；
  `test_demo_protocol.py`（原 gallery）里的 W4 光标形状与 `c-g` 探针。
- 唯一覆盖风险项（lead 裁定**保留**）：`test_terminal_size_reports_positive_columns_and_rows`
  （T2 表里注的是删，**以本条为准：保留**——它是 `terminal_size` 的唯一覆盖）；
  markdown 的流式缓存/重放身份三例；`test_keys_sources.py` 的 settle-window 用例
  （真实 50ms 挂钟、Linux-only，是唯一覆盖，保留并在报告里标为已知 flake 候选）。

### T3 文件合并：`test_chrome.py`

- `test_chrome_scrollbar.py` + `test_chrome_stats.py` + `test_chrome_toasts.py` + `test_chrome_tooltip.py`
  → **合并为 `tests/test_chrome.py`**（对齐 `src/motui/chrome.py` 一个源文件一个测试文件）。
- 纯机械合并：内容逐字搬、只允许改文件头 docstring 与 import 段；用例名沿用（重名才加前缀）。
- 硬证据：合并前后 `uv run pytest -q tests/` 的用例数与通过数**完全一致**（贴两组数字）。

### T4 全门禁 + 报告

- `uv run pytest -q`（贴真实用例数、pass/fail、耗时）
- `uv run python tools/golden.py --check` → 11 页 match
- `uv run python tools/framebench.py` → exit 0 + hash 行
- `uv run python -m motui < /dev/null` 与 `uv run python -m motui --pages` → exit 0
- `uv run python tools/apidoc.py --check` → 通过
- 报告里给出**逐文件 before/after 用例数表**（覆盖全部 44 个文件）与删除总数

## 验收

1. 用例数：基线 − 本清单删除数（误差 0；每个删除都要在表里可查）
2. 六条门禁全绿（含 demo 两档）
3. `tests/test_chrome.py` 存在，四个旧文件不再存在
4. 报告的删除明细必须逐条附分类桶（b1/b2/b3/b4）与「谁覆盖了它」

## 禁触清单

- `src/**`、`tools/**`、`docs/**`、`README.md`、`pyproject.toml`、`.github/**`
- 上面「不许删」清单里的任何用例；`tests/_doubles.py`；`tests/golden/**`（fixture 只读）
- `specs/**`

## 最终报告格式

工单状态表（T1–T4 + commit hash）/ commit 清单 / 自测真实结论（六条）/ 逐文件 before-after 用例数表 /
删除明细（用例名 + 分类桶 + 覆盖者）/ 偏差与取舍（含「本清单外你还认为可删但没删」的观察）/ 未决问题。
阻塞即停。
