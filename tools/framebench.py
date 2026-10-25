"""Frame-cost benchmark: the same measuring stick for every performance wave.

Run it from the repository root::

    uv run python tools/framebench.py [--frames N]

Nine lines, one per measurement.  Seven are timings, each printing ms per
operation:

``stream-single``  one pane, an open Markdown block growing one source line
per frame (the /md and reply-turn shape);
``stream-split``   the /split shape -- transcript | preview, the preview's
Markdown streaming the same way, both panes composed every frame;
``scroll``         a long sealed transcript scrolled through a storm of
wheel notches, repaint included;
``scroll-long``    the same scroll against a 3000-row document (the
viewport's slicing path);
``text-open``      one OPEN 3000-line ``Text`` block repainted frame after
frame -- the block-row cache's steady state (render-cost W1);
``table-open``     one OPEN 240x6 ``Table`` block repainted frame after
frame -- the table's own row memory, on top of the block's cache
(render-cost W2);
``stream-paragraph``
                   one Markdown paragraph that only ever gains a line, one
append and one repaint per frame, measured once a thousand lines have
landed -- the tail block's suffix render (render-cost W4);
and two are the end-to-end lines:

``replay``         the demo's whole piped replay (a subprocess) in wall time,
the end-to-end smoke the red lines already name;
``render-hash``    a digest of one deterministic session's every recorded
output byte -- the rendering-bytes gate (a wave that moves it changed what
the user sees).

The numbers live in the perf group's overview (``specs/``); a wave that
cannot show its workload line moving has no business merging.

**Baseline, demo-structure W2 (2026-10-17): the digest held, the tour
converged.**  The wave reclassifies the demo's twelve pages into ten
families on the kit's exhibit grammar (``specs/2026-10-17-demo-structure``,
the pages wave): the old ``action`` / ``input`` / ``choice`` / ``data`` /
``modal`` / ``chrome`` / ``styles`` names become ``actions`` / ``forms`` /
``views`` / ``modals`` / ``shell`` / ``themes``, the fields and the menus
merge into ``forms``, ``Checkbox`` joins ``actions``, ``StatusLine`` joins
``layout``, the Palette rides the modals page, the feedback page's Toasts /
Tooltip / live bars ride the shell page, and ``demo/content.py`` retires
for ``demo/assets.py``.  ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122``: the
digest composes one ``HeadlessScreen``, one ``Scrollbar``, two ``Markdown``
blocks, a split and a fixed scroll/reflow script -- no demo page, no page
rail, no ``Echo`` is on that path, and nothing the wave changed reaches a
plain ``Markdown`` frame.  The one line that moves is ``replay``: the
piped tour builds ten pages instead of twelve (the palette road moved from
the chrome stop to the modals stop, and the walk between pages is two
``c-n`` steps shorter) and reads **about 270 ms per run (268-280 ms over
four runs)** against the 292 ms it recorded after the choice-architecture
wave.  Recorded as found: no new hash baseline, because nothing moved.

**Baseline, demo-structure W3 (2026-10-17): the digest held, the anchors went
symbolic.**  The wave empties the session of page special cases (the pick
road, ``c-t``'s filter seat on the exhibit slot, one structured report), makes
the bottom hint band follow the page and replaces the replay's hand-computed
mouse cells with symbolic anchors resolved against a live layout at the
replay's own geometry -- all of it demo-side wiring, none of it on a
rendering path.  ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122``, the W1
value, and ``replay`` does not move either: the anchor probe builds its own
headless session inside the replay process and resolves every cell in about
50 ms, so the line reads **296-308 ms over three runs**, against the ~298 ms
W2's own runs recorded.  Recorded as found: nothing moved.

**Baseline, choice-architecture W4 (2026-10-17): the digest held, the demo's
route grew.**  The group's closeout rebuilds the demo and lands the last
component: `ComboBox` joins the widget library, the demo gains the `modal`
page and the input page's ComboBox exhibit, `Table`/`List` gain their mark
column (an empty set renders the old bytes) and the golden set goes 11 -> 12
pages.  ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122``, the W1
value: ``hash_workload`` composes one ``HeadlessScreen``, one ``Scrollbar``,
two ``Markdown`` blocks, a split and a fixed scroll/reflow script -- no demo
page, no marked view and no ComboBox is on that path, and nothing the wave
changed reaches a plain ``Markdown`` frame.  The one line that moves is
``replay``: the piped tour now builds twelve pages and plays the modal page's
walk plus the ComboBox road (two clicks on the exhibit row, a typed query,
one pick), so it reads about **270 ms per run (264-275 ms over three runs)**
-- the tour is longer, the rendering is not.  Recorded as found: no new hash
baseline, because nothing moved.

**Baseline, tui-depth W1 (2026-10-16): re-recorded once.**  The group's
``render-hash`` is
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122``,
re-run twice on the branch with the same value.  The one intentional change
is W1's synchronized output (DECSET 2026): the painter now brackets every
non-empty frame in ``\x1b[?2026h`` / ``\x1b[?2026l``, so the digest of a
session's recorded bytes moves by exactly that pair around each frame --
the wave's whole point (the terminal swaps the frame in one repaint).  The
payload inside the bracket is the same joined rows as before --
``Painter(sync=False)`` reproduces the old bytes verbatim -- and the
unchanged-frame zero-byte contract is untouched.  Before this wave the value
was ``5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a``,
the same it had been since frame-budget recorded it: the base-components
group (2026-10-16) moved rendered bytes, but never on a path this workload
composes -- it retired the agent display layer under ``chat/`` (the
per-message, tool-call and edit blocks and their streamed-reply
controllers) and the ``Theme`` band fields ``user_bg`` / ``tool_bg`` /
``code_bg`` with their two derived tone tables, migrated the slash palette
and the two-column status row into ``widgets/`` as ``Palette`` /
``StatusLine``, added the ``Button`` / ``Checkbox`` / ``Link`` primitives
and the ``Pointer`` tier with ``Theme.hover``, rebuilt the demo as the
page-per-category gallery (since MOTUI W5 it ships as
``src/motui/demo/``), and normalized the wire's button-free motion in the
decoder / console bridge.  ``hash_workload`` composes only a
``HeadlessScreen``, one ``Scrollbar``, two ``Markdown`` blocks, a vertical
split and a fixed scroll/reflow script -- no retired component, no theme
band, no status row, no palette, no action primitive, no pointer report and
no demo page is on that path, so not one byte the digest recorded changed.
Recorded as found: no new baseline, because nothing moved.

**Baseline, tui-depth W2 (2026-10-16): recorded as unchanged.**  W2 taught
``Segment`` to carry the inline payloads (``link``/``action``) and
``Markdown`` to hang a link's url on its label, and ``Line.styled`` now
wraps such a run in the OSC 8 pair -- bytes *did* change on every row that
carries a link (a full-width render of the fixture holds 18 rule-matched
links, the TOC / anchor / table sections, each label wrapped in
``\x1b]8;;URL\x1b\\`` ... ``\x1b]8;;\x1b\\``).  None of them is on this
workload's path: ``hash_workload`` opens with the viewport pinned to the
document's **tail** (the stick-to-bottom default) and its whole script --
twelve +/-3-row scrolls, one reflow to 120 columns, three
``scroll_to_bottom`` passes -- stays there, so no frame it records ever
paints a link row (a probe counted zero OSC 8 occurrences at every stage).
The digest over two runs is therefore still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122``, the
W1 value.  Recorded as found: the wave's byte change is real but off this
workload's window, and the workload is the measuring stick -- it is not
retargeted to make a hash move.

**Baseline, tui-depth W9 (2026-10-16): unchanged since W2.**  The group's
closing wave adds only engineering furniture -- CI, the release workflow and
the generated API page -- and touches no rendering path.  The same held for
every wave between: the double and triple click with the tooltip, the find
tier, the fuzz / golden / stats tools, the form four with the
text buffer's undo and selection, ``Diff`` and ``List`` with the grapheme
corners, and the ``Table`` / ``Tree`` / ``Markdown`` deepening all left this
digest where W2 recorded it -- still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122``, W1's
number.  Verified once more at W9, on the merged tree: this is the group's
final value.

**Baseline, render-cost W1 (2026-10-17): the new line recorded, the digest
held.**  The wave moved the row cache from the viewport onto the block
(``Block.rows(width)``, keyed on the width and the component's revision
snapshot), so ``text-open`` -- an open 3000-line ``Text`` block repainted
the way a mouse move repaints it -- stops re-wrapping all 3000 lines every
frame: **28.2 ms/frame before the wave, 0.1 ms/frame after**, recorded here
as the line's first number (the warm paint fills the block's memory and
every measured frame hits it).  The line exists by the rule up top: a wave
that cannot show its own workload moving has no business merging, and no
pre-existing line covers a long *open* plain-text block -- the stream lines
grow *Markdown*, the scroll lines are *sealed*.

One older line moved with it, by the same fix: ``scroll-long`` builds its
3000-row document out of 2649 **unsealed** one-row ``Text`` blocks, so
before the cache every wheel notch re-wrapped all of them; now they are
answered from each block's memory and the line reads **2.6 ms/notch
against the 16.0 it recorded at tui-depth W1** (``scroll``, whose 350-row
transcript *is* sealed, does not move: 2.7 ms/notch).  The other timings
and ``replay``'s workload are untouched, and ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`` --
this wave recomputes less, it renders the same bytes.

**Baseline, render-cost W2 (2026-10-17): the table's line recorded, the
digest held.**  ``Table`` renders its whole grid per call -- normalizing,
banding, measuring, padding and fusing every cell -- and nothing memoized
it, so the new line (a 240x6 grid: 240 records, 6 columns, 483 rendered
rows, repainted the way a mouse move repaints it) read **25.6 ms/frame
before the wave, 0.1 ms/frame after**: the table now remembers its last
grid behind a value snapshot of its own rows, and the block's cache keys
on the same snapshot, so one answer serves both tiers.  The wave's other
large win -- the editor's wrap memory -- needs no line of its own: no
existing line covers a long edited buffer (the stream lines grow Markdown,
the scroll lines are sealed, ``text-open`` is plain text), and the spec's
probe records it -- a 3000-line editor's warm render drops from 9.0 ms to
microseconds and its per-key cost from 9.1 ms to **0.2 ms**, because a
keystroke now re-wraps one line instead of 3000.  The other timings and
``replay``'s workload are untouched, and ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`` --
this wave recomputes less, it renders the same bytes.

**Baseline, render-cost W4 (2026-10-17): the new line recorded, the digest
held.**  The wave taught the Markdown tail block to render a *suffix*: a
text that only grew re-parses and re-wraps from its first changed word on
instead of painting the whole paragraph again, and the container's wrap of
unchanged child rows is remembered.  ``stream-paragraph`` -- one growing
paragraph, one append and one repaint per frame, the clock started after a
thousand lines landed (the workload records the append ``stream-single``
never reaches) -- reads **36.8 ms/frame before the wave, 0.6 ms/frame
after**: the pre-wave renderer re-parsed the whole paragraph on every frame,
so the line is the wave's own move, not a neighbour's.  The ``I`` probe
case does better still: ``Panel(Markdown 2000 lines)`` re-rendered is
0.12 ms/frame against the 34.7 it spends wrapping a *fresh* panel (the probe
builds a new one per measured frame, so its number is the cold wrap; the
memory is what a repainting host sees).  ``stream-single`` and
``stream-split`` hold at 0.7 / 4.3 ms/frame (their paragraphs are short and
nothing in their frame grew with the wave), ``scroll`` / ``scroll-long`` /
``text-open`` are where W1 and W3 left them, and ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`` --
the same rows, computed once.

**Baseline, demo-presentation W2 (2026-10-18): the digest held, recorded as
found.**  The group's closing wave normalizes what the demo *says*, not what
it renders on this workload's path: every page's captions become state
enumerations, the `notes` page grows into the manual (how to play, the tour,
the signature quick reference in one fenced block, the interaction model) and
the `layout` page gains the `Tabs` strip.  ``render-hash`` is still
``de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`` --
``hash_workload`` composes one ``HeadlessScreen``, one ``Scrollbar``, two
``Markdown`` blocks, a split and a fixed scroll/reflow script: no demo page,
no rail and no ``Tabs`` is on that path, and the wave's demo edits never
reach it.  ``replay`` reads **290-307 ms over four runs** (290 / 296 / 302 /
307): the piped tour builds the same eleven pages the W1 tour built, and the
one page that grew -- ``notes``, 50 manual rows before the wave, 137 after --
is painted once and then left alone, so the line moves by noise, not by
workload.  Recorded as found: no new hash baseline, because nothing moved.

**Baseline, frame-perf W2 (2026-10-22): the new line recorded, the digest
held.**  The wave replaces the layout's per-frame walk over every block with
the viewport's private body index (per-block heights and prefix sums keyed on
the document mutation and the width, one snapshot probe per body block per
frame, the window located by bisect), and the tool prints **ten lines** now:
``idle-long`` -- the same 3000-row document ``scroll-long`` scrolls, with
nothing changing, one ``refresh`` + ``paint`` per measured frame -- is the
line the wave adds, and it reads **0.6-0.7 ms/frame over three runs**
(0.6 / 0.7 / 0.6).  That is the between-frames floor of a long document, and
it is honest about what the floor is made of: not one of the 3000 blocks
re-renders, but every one of the ~2650 body blocks is probed per frame --
``Text.revision()`` builds its snapshot tuple per call -- so the line sits
above ``text-open``'s 0.1 ms display floor by exactly the sweep over 2650
blocks; the wave moved the walk and the window (``scroll-long`` reads
**0.7-0.9 ms/notch against the 1.3-1.9 the frame-perf W1 tree recorded on
the same machine**), and the probe-per-block sweep is what remains.  The
other timings and ``replay`` are untouched, and ``render-hash`` is still
``a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`` --
the index recomputes less, it renders the same bytes.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from motui import Markdown, TUI, Table, Text
from motui.app import Scrollbar
from motui.terminal import HeadlessScreen

FIXTURE = (ROOT / "src" / "motui" / "demo" / "fixture.md").read_text(
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
        tui.refresh()
        tui.paint()
    return (time.perf_counter() - t0) / frames * 1000.0


def scroll_workload(notches: int, rows: int = 350) -> float:
    tui, _ = _tui(split=False)
    tui.paint()
    if rows > 350:
        from motui import Text

        for i in range(rows - 350):
            tui.add(Text(f"line {i} of {rows}"))
        tui.paint()
    t0 = time.perf_counter()
    for i in range(notches):
        tui.scroll_up(3 if i % 2 == 0 else -3)  # wheel down, wheel up
        tui.refresh()
        tui.paint()
    return (time.perf_counter() - t0) / notches * 1000.0


def text_open_workload(frames: int) -> float:
    """Frame cost of one OPEN ``Text`` block holding 3000 lines.

    The shape the block-row cache (render-cost W1) is about: a long text
    block that nothing seals, repainted frame after frame the way a mouse
    move repaints it.  The warm paint fills the block's row memory, the
    measured paints hit it -- before the cache lived on the block every one
    of them re-wrapped all 3000 lines.
    """
    tui = TUI(screen=HeadlessScreen(180, 45), interactive=False)
    text = Text(
        "\n".join(
            f"line {i} with some words in it, wrapped by the renderer as it goes"
            for i in range(3000)
        )
    )
    tui.add(text)
    tui.paint()  # the cold paint: it wraps once and fills the cache
    t0 = time.perf_counter()
    for _ in range(frames):
        tui.refresh()
        tui.paint()
    return (time.perf_counter() - t0) / frames * 1000.0


def idle_long_workload(frames: int) -> float:
    """Frame cost of a 3000-row document with nothing changing.

    The long-document steady state the viewport's body index (frame-perf
    W2) is about: the same document ``scroll-long`` scrolls -- a sealed
    Markdown transcript grown to 3000 rows with single-line ``Text``
    blocks -- repainted frame after frame with no scroll and no edit, so a
    measured frame is pure between-frames work: the index's snapshot
    probes over the body blocks and the window's re-materialization, and
    not one render (every block's cache answers).  Before the index, each
    of those frames walked all 3000 blocks and rebuilt the window's
    geometry tables by hand; the line exists because no earlier one
    isolated a long document's do-nothing frame from the scrolling that
    every other long-document line measures.
    """
    tui, _ = _tui(split=False)
    tui.paint()
    for i in range(3000 - 350):  # the same growth scroll_workload(rows=3000) does
        tui.add(Text(f"line {i} of 3000"))
    tui.paint()  # the warm paint: the index is built, every block's cache filled
    t0 = time.perf_counter()
    for _ in range(frames):
        tui.refresh()
        tui.paint()
    return (time.perf_counter() - t0) / frames * 1000.0


def table_open_workload(frames: int) -> float:
    """Frame cost of one OPEN ``Table`` block holding a 240x6 grid.

    The shape the table's own row memory (render-cost W2) is about: a grid
    of 240 records and 6 columns -- 483 rendered rows, taller than the pane
    -- that nothing seals, repainted frame after frame the way a mouse move
    repaints it.  The warm paint builds the grid once and fills the
    table's memory, the measured paints hit it -- before the memory every
    one of them re-normalized, banded, measured, padded and fused all 1440
    cells.
    """
    tui = TUI(screen=HeadlessScreen(180, 45), interactive=False)
    table = Table(
        [f"col {c}" for c in range(6)],
        [[f"cell {r}.{c}" for c in range(6)] for r in range(240)],
    )
    tui.add(table)
    tui.paint()  # the cold paint: it builds the grid and fills the memory
    t0 = time.perf_counter()
    for _ in range(frames):
        tui.refresh()
        tui.paint()
    return (time.perf_counter() - t0) / frames * 1000.0


#: One line of the paragraph ``stream-paragraph`` grows: long enough to wrap
#: twice at 180 columns, so the document's row count moves with its line
#: count and the wrap is real work, not a per-line fit.
PARAGRAPH_LINE = (
    "line %d of one growing paragraph, and the renderer still has to wrap it"
)


def stream_paragraph_workload(frames: int) -> float:
    """Frame cost of one Markdown paragraph that only ever grows.

    The reply-turn shape without its blank lines: a single paragraph gains
    one source line per frame and the pane repaints, so nothing ever seals
    and the tail block is the whole document.  The document is brought to a
    thousand lines and then through one append -- the cold frames that fill
    the tail block's memory, the ``text-open`` convention -- before the
    clock starts, so the measured frames are the steady state: every one of
    them appends a line to a thousand-line paragraph.  The suffix render
    (render-cost W4) is what the line catches: a renderer that re-parses the
    paragraph per frame pays for every line landed, this one for the line
    that arrived.
    """
    tui = TUI(screen=HeadlessScreen(180, 45), interactive=False)
    stream = Markdown("")
    tui.add(stream)
    tui.paint()
    lines = [PARAGRAPH_LINE % i for i in range(1000)]
    stream.text = "\n".join(lines)
    tui.refresh()
    tui.paint()  # the cold paint: a thousand lines parsed and wrapped
    lines.append(PARAGRAPH_LINE % 1000)
    stream.text = "\n".join(lines)
    tui.refresh()
    tui.paint()  # the cold append: it fills the tail block's memory
    t0 = time.perf_counter()
    for i in range(frames):
        lines.append(PARAGRAPH_LINE % (1001 + i))
        stream.text = "\n".join(lines)
        tui.refresh()
        tui.paint()
    return (time.perf_counter() - t0) / frames * 1000.0


def replay_workload() -> float:
    t0 = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-m", "motui"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        cwd=ROOT,
        # The tool bootstraps ``src/`` on its own path; the demo subprocess
        # gets the same seam so the workload never depends on an install.
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
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
    print(f"idle-long    : {idle_long_workload(frames):7.1f} ms/frame")
    print(f"text-open    : {text_open_workload(frames):7.1f} ms/frame")
    print(f"table-open   : {table_open_workload(frames):7.1f} ms/frame")
    print(f"stream-paragraph: {stream_paragraph_workload(frames):7.1f} ms/frame")
    print(f"replay       : {replay_workload():7.0f} ms total")
    print(f"render-hash  : {hash_workload()}")


if __name__ == "__main__":
    main()
