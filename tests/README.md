# Tests

The suite mirrors the package layout:

```
tests/
  kernel/    pure values, rows, layout, frame, selection
  pixel/     Raster verbs, palette, quantize
  widgets/   component families; cross-family contracts in test_contracts.py
  app/       runtime, workspace, focus, pointer, modal, palette
  terminal/  screen, decoder, painter, clipboard
  testing/   the test harness and the tools' probe files
  demo/      registry, lifecycle, scenes, entry modes and semantic goldens
  test_api.py, test_invariants.py, test_packaging.py
  golden/semantic/   ten cell-grid snapshots
```

Rules:

1. A test names a public contract or a real regression; do not pin a
   private field. If a scene needs a state read, make the state public.
2. Visual details belong to a semantic golden; a scene test asserts state
   and transitions, not exact glyph strings.
3. Timings belong to `tools/framebench.py`, never to a unit test.
4. A cross-widget contract lives once in `tests/widgets/test_contracts.py`.
   This is the one documented exception to one-source-module/one-test-file.
5. Keep width, marker, error and boundary matrices; they are cheap and
   catch real regressions. Do not delete coverage to hit a count.
6. Demo tests build scenes directly for mechanics and use `Showcase` for
   lifecycle, routing and the wipe.

Run `uv run pytest -q -p no:cacheprovider` for the suite, and the gates in
`CONTRIBUTING.md` before a release.
