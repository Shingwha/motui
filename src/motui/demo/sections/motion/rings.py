"""The rings game model: schedule, spawning, judgment and score."""

from __future__ import annotations

import random
from dataclasses import dataclass

from ...scene import TICK_HZ

__all__ = [
    "POINTS",
    "RINGS_SEED",
    "Ring",
    "RingsGame",
    "window_stage",
]

#: The spawn sequence's seed; a board resize resets the generator to it.
RINGS_SEED = 20261028

#: The rings schedule, in seconds: the first birth, the spacing, the
#: approach, the three judgment windows around the deadline, the target
#: disc's pop, the hit burst and the miss fade.
BIRTH_DELAY = 0.4
SPAWN_PERIOD = 1.2
APPROACH = 1.0
OUTER_RADIUS = 26
TARGET_RADIUS = 8
WINDOW_PERFECT = 0.10
WINDOW_GOOD = 0.20
WINDOW_FORCE = 0.35
POINTS = {"perfect": 300, "good": 100, "force": 40}
POP = 0.15
BURST = 0.35
BURST_OVERSHOOT = 20
MISS_FADE = 0.4

#: The four ring slots rotate by concurrency order.
RING_SLOTS = 4


@dataclass(slots=True)
class Ring:
    """One judgment circle: position, slot color and where it stands."""

    cx: float
    cy: float
    slot: int
    born: float
    state: str  # "live" | "burst" | "miss"
    verdict: str | None  # "perfect" | "good" | "force" on a judged ring
    at: float  # the judgment or miss time


def window_stage(error: float) -> str:
    if error <= WINDOW_PERFECT:
        return "perfect"
    if error <= WINDOW_GOOD:
        return "good"
    if error <= WINDOW_FORCE:
        return "close"
    return "approach"


class RingsGame:
    """The deterministic rings state machine, independent of the canvas.

    Births come from one seeded RNG in schedule order, misses from the
    deadline, so every render is a pure function of phase and geometry."""

    __slots__ = (
        "_phase",
        "_rng",
        "attempts",
        "born_count",
        "combo",
        "hits",
        "rings",
        "score",
    )

    def __init__(self) -> None:
        self._phase = 0
        self._rng = random.Random(RINGS_SEED)
        self.rings: list[Ring] = []
        self.born_count = 0
        self.score = 0
        self.combo = 0
        self.hits = 0
        self.attempts = 0

    @property
    def phase(self) -> int:
        return self._phase

    @property
    def now(self) -> float:
        return self._phase / TICK_HZ

    @property
    def stage(self) -> str:
        errors = [
            abs(self.now - (ring.born + APPROACH))
            for ring in self.rings
            if ring.state == "live"
        ]
        return window_stage(min(errors, default=float("inf")))

    def reset(self) -> None:
        self._phase = 0
        self._rng = random.Random(RINGS_SEED)
        self.rings.clear()
        self.born_count = 0
        self.score = 0
        self.combo = 0
        self.hits = 0
        self.attempts = 0

    def sync(self, phase: int, width: int, height: int) -> None:
        self._phase = phase
        now = phase / TICK_HZ
        while True:
            born = BIRTH_DELAY + self.born_count * SPAWN_PERIOD
            if born > now:
                break
            self._spawn(born, width, height)
        for ring in self.rings:
            deadline = ring.born + APPROACH + WINDOW_FORCE
            if ring.state == "live" and now > deadline:
                ring.state = "miss"
                ring.at = deadline
                self.combo = 0
                self.attempts += 1
        self.rings = [
            ring
            for ring in self.rings
            if ring.state == "live"
            or now - ring.at < (BURST if ring.state == "burst" else MISS_FADE)
        ]

    def _spawn(self, born: float, width: int, height: int) -> None:
        """Deal one ring: the next slot color and a position inside the margin."""
        margin = min(34, width // 2, height // 2)
        self.rings.append(
            Ring(
                cx=self._rng.uniform(margin, width - margin),
                cy=self._rng.uniform(margin, height - margin),
                slot=1 + self.born_count % RING_SLOTS,
                born=born,
                state="live",
                verdict=None,
                at=0.0,
            )
        )
        self.born_count += 1

    def judge(self, now: float) -> Ring | None:
        best: Ring | None = None
        best_error = 0.0
        for ring in self.rings:
            if ring.state != "live":
                continue
            error = abs(now - (ring.born + APPROACH))
            if best is None or error < best_error:
                best, best_error = ring, error
        if best is None:
            return None
        if best_error <= WINDOW_PERFECT:
            verdict = "perfect"
        elif best_error <= WINDOW_GOOD:
            verdict = "good"
        elif best_error <= WINDOW_FORCE:
            verdict = "force"
        else:
            return None
        best.state = "burst"
        best.verdict = verdict
        best.at = now
        self.score += POINTS[verdict]
        if verdict == "force":
            self.combo = 0
        else:
            self.combo += 1
            self.hits += 1
        self.attempts += 1
        return best
