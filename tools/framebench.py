"""Frame-cost benchmark: the same measuring stick for every performance wave.

Run it from the repository root::

    uv run python tools/framebench.py [--frames N]

Six lines, one per measurement.  Four are timings, each printing ms per
operation:

``stream-single``  one pane, an open Markdown block growing one source line
per frame (the /md and reply-turn shape);
``stream-split``   the /split shape -- transcript | preview, the preview's
Markdown streaming the same way, both panes composed every frame;
``scroll``         a long sealed transcript scrolled through a storm of
wheel notches, repaint included;
``scroll-long``    the same scroll against a 3000-row document (the
viewport's slicing path);
and two are the end-to-end lines:

``replay``         the demo's whole piped replay (a subprocess) in wall time,
the end-to-end smoke the red lines already name;
``render-hash``    a digest of one deterministic session's every recorded
output byte -- the rendering-bytes gate (a wave that moves it changed what
the user sees).

The numbers live in the perf group's overview (``specs/``); a wave that
cannot show its workload line moving has no business merging.

**Baseline, base-components (2026-10-16): unchanged.**  The group's
``render-hash`` is ``5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a``
before and after -- the same value every group since frame-budget recorded,
re-verified twice on the final branch.  The group did move rendered bytes,
but never on a path this workload composes: it retired the agent display
layer under ``chat/`` (the per-message, tool-call and edit blocks and their
streamed-reply controllers) and the ``Theme`` band fields ``user_bg`` /
``tool_bg`` / ``code_bg`` with their two derived tone tables, migrated the
slash palette and the two-column status row into ``widgets/`` as ``Palette``
/ ``StatusLine``, added the ``Button`` / ``Checkbox`` / ``Link`` primitives
and the ``Pointer`` tier with ``Theme.hover``, rebuilt the demo as
``examples/gallery/``, and normalized the wire's button-free motion in the
decoder / console bridge.  ``hash_workload`` composes only a
``HeadlessScreen``, one ``Scrollbar``, two ``Markdown`` blocks, a vertical
split and a fixed scroll/reflow script -- no retired component, no theme
band, no status row, no palette, no action primitive, no pointer report and
no demo page is on that path, so not one byte the digest records changed.
Recorded as found: no new baseline, because nothing moved.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mocode_tui import HeadlessScreen, Markdown, Scrollbar, TUI  # noqa: E402

FIXTURE = (ROOT / "examples" / "Markdown-Rendering-Test.md").read_text(
    encoding="utf-8"
)
LINES = FIXTURE.split("\n")


def _tui(split: bool) -> tuple[TUI, Markdown | None]:
    tui = TUI(screen=HeadlessScreen(180, 45), interactive=False)
    Scrollbar(tui, pane="primary")
    tui.add(Markdown(FIXTURE))
    stream = None
    if split:
        _, right = tui.split("vertical", ratios=(2, 1))
        stream = Markdown("")
        right.document.add(stream)
    tui.paint()
    return tui, stream


def stream_workload(split: bool, frames: int) -> float:
    tui, stream = _tui(split)
    source = tui.document.get("b0").component
    t0 = time.perf_counter()
    for i in range(frames):
        if stream is not None:
            stream.text = "\n".join(LINES[: 20 + (i % 60)])
        source.text = "\n".join(LINES[: 30 + (i % 60)])
        tui.invalidate()
        tui.paint()
    return (time.perf_counter() - t0) / frames * 1000.0


def scroll_workload(notches: int, rows: int = 350) -> float:
    tui, _ = _tui(split=False)
    block = tui.document.get("b0")
    block.seal()
    tui.paint()
    if rows > 350:
        from mocode_tui import Text

        last = None
        for i in range(rows - 350):
            last = tui.add(Text(f"line {i} of {rows}"))
        last.seal()
        tui.paint()
    t0 = time.perf_counter()
    for i in range(notches):
        tui.scroll_up(3 if i % 2 == 0 else -3)  # wheel down, wheel up
        tui.invalidate()
        tui.paint()
    return (time.perf_counter() - t0) / notches * 1000.0


def replay_workload() -> float:
    t0 = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "examples/demo.py"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        cwd=ROOT,
        check=False,
    )
    if done.returncode != 0:
        raise SystemExit(f"demo replay exited {done.returncode}")
    return (time.perf_counter() - t0) * 1000.0


def hash_workload() -> str:
    """A digest of one deterministic session's every recorded output byte.

    Fixed geometry, fixed document, fixed scroll-and-reflow script, driven
    synchronously (``paint`` straight, no pump, no clock) -- so the bytes are
    a pure function of the rendering code.  A performance wave that moves
    this hash has changed what the user sees, and has failed its gate.
    """
    import hashlib

    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    Scrollbar(tui, pane="primary")
    tui.add(Markdown(FIXTURE))
    tui.paint()
    _, right = tui.split("vertical", ratios=(2, 1))
    right.document.add(Markdown(FIXTURE))
    tui.paint()
    for step in range(12):
        if step % 2:
            tui.scroll_down(3)
        else:
            tui.scroll_up(3)
        tui.paint()
    tui.screen.width = 120  # a reflow: the split re-divides, rows re-wrap
    tui.paint()
    for _ in range(3):
        tui.scroll_to_bottom()
        tui.paint()
    return hashlib.sha256(tui.screen.output.encode("utf-8")).hexdigest()


def main() -> None:
    frames = 60
    if len(sys.argv) > 2 and sys.argv[1] == "--frames":
        frames = int(sys.argv[2])
    print(f"stream-single: {stream_workload(False, frames):7.1f} ms/frame")
    print(f"stream-split : {stream_workload(True, frames):7.1f} ms/frame")
    print(f"scroll       : {scroll_workload(frames):7.1f} ms/notch")
    print(f"scroll-long  : {scroll_workload(frames, rows=3000):7.1f} ms/notch")
    print(f"replay       : {replay_workload():7.0f} ms total")
    print(f"render-hash  : {hash_workload()}")


if __name__ == "__main__":
    main()
