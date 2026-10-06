# Spec W3 · `/preview` streams in the background

> Branch `fix/w3-preview-background`; 前置: baseline `main` at `b1ddf5e`
> (parallel with W1, disjoint files); 深读:
> `specs/2026-10-06-preview-fidelity/00-overview.md` (report 5),
> `examples/pi_demo.py` (`_run_command`, `_show_fixture`, `_TURNS`).

## 目标

While the fixture streams into the new preview pane, the host loop reads no
keys, so the composer and the transcript look frozen until the stream
lands; afterwards every keystroke that was queued applies at once. That is
visible as "the left side does nothing while the preview runs". 最高约束:
the library changes not at all — this is demo policy over the task pattern
`/md` already uses, and the split still happens the instant the command
runs (the pane is on screen before the first row streams in).

## 工单（按序，每项一个 commit）

### T1 后台流式

- `examples/pi_demo.py`: `/preview` schedules `_stream_preview` as a
  background task registered in `_TURNS` (exactly the `_show_fixture`
  pattern: `asyncio.create_task`, `_TURNS.add`, `add_done_callback(
  _TURNS.discard)`), so `_run_command` returns immediately and the host
  loop keeps reading keys while the fixture assembles. `tui.split(...)`
  stays synchronous in the command body, and `preview.pane` is still set
  there so a repeat command dismisses correctly.
- Keep the module docstring honest: it currently says `/preview` streams
  in the foreground. Reword the sentence that claims it (the surrounding
  argument — watching the fixture assemble — still holds, and is now
  watchable *while typing*).
- Nothing else in the demo changes.

### T2 验证

- Run the piped replay and the demo's scripted replay path and confirm the
  final screen is complete and identical to the baseline's (the
  `/preview` visit in `_script()` must still open, wheel, focus and close
  the preview before the dump).

## 验收（自测，报告真实结论）

1. `uv run pytest -q` — paste the real counts.
2. `uv run python examples/pi_demo.py < /dev/null; echo exit=$?`
   — exit 0, and the final screen identical to `git stash`-free baseline:
   capture both (`uv run python examples/pi_demo.py < /dev/null >
   /tmp/after.txt`) and diff against the same command on a clean baseline
   checkout (`git show` of the baseline into a temp worktree, or
   `git stash` + rerun + `git stash pop`). Paste the diff result — "identical"
   is the pass condition.
3. A probe that a keystroke typed while the preview streams is echoed
   before the stream ends: drive `chat()` headlessly with
   `ScriptedKeys` — `/preview`, then a key event, then let the tasks
   finish — and assert the composer's buffer holds the key and the final
   painted rows show it. Paste the output.

## 禁触清单

`src/**`, `tests/**`, `docs/**`, `README.md`, `.zcode/**` — except the
one probe in T3, which lives in a temp file you delete before committing.

## 最终报告格式

Task table / commits (hash + message) / the three real outputs above /
deviations & trade-offs / open questions.
