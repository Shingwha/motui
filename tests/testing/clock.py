"""A clock seam: time a test advances by hand, never by sleeping."""

from __future__ import annotations

__all__ = ["Clock", "tick"]


class Clock:
    """A callable clock for ``tui.clock``: advance it explicitly.

    ``tui.clock`` is the documented seam time enters the driver through, so a
    test installs this object and moves time with :meth:`advance` instead of
    sleeping::

        clock = Clock().install(tui)
        clock.advance(0.05)
        tui.tick()
    """

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def install(self, tui) -> "Clock":
        tui.clock = self
        return self


def tick(tui, clock: Clock, count: int = 1, seconds: float = 0.05) -> None:
    """Fire ``count`` driver ticks, advancing ``clock`` by ``seconds`` each."""
    for _ in range(count):
        clock.advance(seconds)
        tui.tick(clock())
