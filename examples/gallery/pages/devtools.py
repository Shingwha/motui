"""The devtools page: the wave's developer tools -- shown, not just described.

Four exhibits in one page (D11-D14):

* a **frame-rate row** and an **event-count row**, refreshed by the page's
  own ``tick`` on the session's beat: the first reads the session's fps
  sample (``gallery.fps``, the ``FPS_INTERVAL`` tick), the second the
  mounted :class:`~motui.Stats` overlay's own counter -- so ``c-g``
  flips the row from "off" to live numbers without a second counting
  mechanism anywhere;
* a **hit-test probe**: three hoverable leaves, each its own block, and a
  row that resolves the pointer's cell through
  :meth:`~motui.app.TUI.hit_component` once per beat -- the same walk a
  click takes;
* **the rest of the toolbox** as static text: the golden frames
  (``tools/golden.py --check`` / ``--update``) and the recorded-replay pair
  (``RecordingKeys`` / ``ReplayKeys``), each closed by an ``api_note``
  naming something that exists in the tree.

The page adds **no timing mechanism of its own**: the beat is the session's
``PAGE_TICK``, the fps is the session's sample, and the event count is the
overlay's -- three readers, no new clock.  It is also dump-stable: with no
loop running (``--pages``) the two live rows show their placeholders, and
in the scripted replay the tour only passes through.
"""

from __future__ import annotations

from motui import Button, Checkbox, FocusRing, Link, Text

from ..page import PageBody, api_note, header, section, try_line

__all__ = ["page"]


def _hit_line(gallery) -> str:
    """What ``TUI.hit_component`` resolves at the pointer's last cell.

    ``gallery.pointer`` is the session's own tier, so the row reports the
    same walk a click takes -- through the frame's ownership table and every
    ``Container.child_at`` down to the leaf -- and the leaf's own cell
    inside its block, not the screen cell.
    """
    pointer = gallery.pointer
    position = None if pointer is None else pointer.position
    if position is None:
        return "hit (pointer cell): -- move the pointer over the probe rows below"
    hit = gallery.tui.hit_component(position[0], position[1])
    if hit is None:
        return f"hit ({position[0]}, {position[1]}): -- no block owns that cell"
    component, row, col = hit
    return (
        f"hit ({position[0]}, {position[1]}): {type(component).__name__} "
        f"-> its own cell ({row}, {col})"
    )


def page(gallery) -> PageBody:
    """The dev toolbox: two live rows, a hit-test probe, and the recipes."""
    theme = gallery.theme
    # The live rows start as placeholders: with no loop (--pages) they stay
    # these, and the tick below is what moves them.
    rate = Text("frame rate: -- (the session samples it every 0.5 s)", style=theme.dim)
    events = Text("events: -- (c-g mounts the overlay that counts them)", style=theme.dim)
    probe = Text("hit (pointer cell): -- move the pointer over the probe rows below", style=theme.dim)
    one = Button("probe one -- a Button")
    two = Checkbox("probe two -- a Checkbox")
    three = Link("probe three -- a Link")

    def tick() -> None:
        """One beat: republish the live rows from the session's own state."""
        rate.text = f"frame rate: {gallery.fps:4.1f} fps -- the session's own sample"
        if gallery.stats is None:
            events.text = "events: -- the overlay is off; c-g mounts it"
        else:
            events.text = (
                f"events: {gallery.stats.events} counted, "
                f"last {gallery.stats.last or '--'} (c-g unmounts)"
            )
        probe.text = _hit_line(gallery)

    return PageBody(
        [
            *header(
                "developer tools",
                "Stats, golden frames, recorded replays and the invariant batteries -- what this "
                "wave added for the people who build on the toolkit.",
                theme,
            ),
            try_line(
                "press c-g: the dev overlay mounts in the corner and counts this very page; move "
                "the pointer down the probe rows and the line above them resolves the hit",
                theme,
            ),
            section("live readouts -- the session's own fields, no new clock", theme),
            rate,
            events,
            probe,
            api_note(
                "Stats(tui, pointer=...) -- handle(event) counts; painter.frames + tui.clock() are the whole reading",
                theme,
            ),
            section("the hit-test probe -- three hoverable leaves, one block each", theme),
            one,
            two,
            three,
            api_note(
                "TUI.hit_component(x, y) -> (component, row, col) | None -- the deepest leaf, the click's own walk",
                theme,
            ),
            section("golden frames -- every page pinned byte for byte", theme),
            Text(
                "uv run python tools/golden.py --check    diffs every page against tests/golden/pages/<page>.txt",
                style=theme.dim,
            ),
            Text(
                "uv run python tools/golden.py --update   re-records the whole set (only a wave that means to move rendering)",
                style=theme.dim,
            ),
            api_note(
                "tools/golden.py --check / --update; tests/test_golden_frames.py is the same assertion in pytest",
                theme,
            ),
            section("record a real session, replay it as a regression", theme),
            Text(
                "RecordingKeys(source, path) wraps any KeySource and appends one JSON line per event; an EOF ends the file",
                style=theme.dim,
            ),
            Text(
                "ReplayKeys(path, speed=0) serves the events back with no wait -- the shape a pytest drives",
                style=theme.dim,
            ),
            api_note(
                "motui.keys.RecordingKeys / ReplayKeys; encode_event / decode_event are the pure pair under them",
                theme,
            ),
            section("the invariant batteries -- stdlib and pytest, nothing else", theme),
            Text(
                "tests/test_decoder_fuzz.py: a fixed random.Random(seed) byte matrix through KeyDecoder -- total, bounded, byte-wise == whole-block",
                style=theme.dim,
            ),
            Text(
                "tests/test_render_invariants.py: the component matrix at widths 1..80 -- idempotent, never wider, drift-free",
                style=theme.dim,
            ),
            api_note("random.Random(seed) matrices; uv run pytest -q runs both", theme),
        ],
        focus=FocusRing([one, two]),
        hint="probe, c-g",
        tick=tick,
    )
