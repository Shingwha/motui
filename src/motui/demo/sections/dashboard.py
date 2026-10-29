"""A controllable deep-space uplink built from live data widgets."""

from __future__ import annotations

import math

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Column, Panel, ProgressBar, Row, Sparkline, Table, Text
from ..common import FixedHeight, LinesView, pad_rows
from ..scene import Scene

__all__ = ["DashboardScene"]

_CLIP = WrapMode.CLIP
_CHANNELS = ("relay-02 / N-42", "relay-04 / K-17", "relay-07 / A-09")
_STAGES = (
    (0, "SIGNAL LOCKED", "nominal"),
    (240, "SOLAR WIND RISING", "interference"),
    (390, "REROUTING TRAFFIC", "reroute"),
    (510, "SIGNAL RECOVERED", "recovery"),
    (660, "SIGNAL LOCKED", "nominal"),
)


class DashboardScene(Scene):
    name = "dashboard"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._time = 0
        self._channel = 0
        self._paused = False
        self._incident_at: int | None = None
        self._recovery_at: int | None = None
        self._stage = ""
        self.samples: list[float] = []
        self.log: list[str] = []
        self.spark = Sparkline([0.5] * 48, marker="braille", style=theme.status.success)
        self.signal_bar = ProgressBar(0.96, label="signal", theme=theme)
        self.relay_table = Table(
            [
                ["02", "42", "on"],
                ["04", "68", "idle"],
                ["07", "91", "idle"],
            ], headers=["id", "ms", "state"],
            theme=theme,
        )
        self._summary = Text("", style=theme.text.muted, theme=theme)
        self._events = LinesView(theme)
        self._graph_box = FixedHeight(self.spark, 8)
        self._side_box = FixedHeight(
            Column([self.signal_bar, self.relay_table, self._summary], gap=0),
            8,
        )
        self._sync(0, force=True)

    def enter(self) -> None:
        super().enter()
        self._time = 0
        self._channel = 0
        self._paused = False
        self._incident_at = None
        self._recovery_at = None
        self._stage = ""
        self.log = []
        self._sync(0, force=True)

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def channel(self) -> int:
        return self._channel

    def _story(self, step: int) -> tuple[str, str]:
        cycle = step % 720
        stage = _STAGES[0][1:]
        for start, title, name in _STAGES:
            if cycle >= start:
                stage = (title, name)
        if self._incident_at is not None and step >= self._incident_at:
            if self._recovery_at is None or step < self._recovery_at:
                stage = ("MANUAL INTERFERENCE", "interference")
            elif step - self._recovery_at < 150:
                stage = ("RECOVERING UPLINK", "recovery")
        return stage

    def _strength(self, step: int) -> float:
        cycle = step % 720
        automatic = 0.0
        if 240 <= cycle < 390:
            automatic = min(1.0, (cycle - 240) / 90)
        elif 390 <= cycle < 510:
            automatic = 0.9
        elif 510 <= cycle < 660:
            automatic = max(0.0, 0.9 * (1 - (cycle - 510) / 150))
        manual = 0.0
        if self._incident_at is not None and step >= self._incident_at:
            manual = min(1.0, (step - self._incident_at) / 75)
            if self._recovery_at is not None and step >= self._recovery_at:
                manual *= max(0.0, 1 - (step - self._recovery_at) / 150)
        return max(automatic, manual)

    def _sample(self, step: int) -> float:
        strength = self._strength(step)
        wave = 0.035 * math.sin(step / 38 + self._channel) + 0.018 * math.cos(step / 17)
        return max(0.08, min(1.0, 0.91 - strength * 0.55 + wave))

    def _append(self, text: str) -> None:
        seconds = self._time // 60
        self.log.append(f"{seconds // 60:02d}:{seconds % 60:02d}  {text}")
        del self.log[:-6]

    def _sync(self, step: int, *, force: bool = False) -> None:
        previous_stage = self._stage
        self._time = max(0, step)
        self._stage, _name = self._story(self._time)
        if self._stage != previous_stage:
            messages = {
                "SIGNAL LOCKED": "signal    lock confirmed · all probes nominal",
                "SOLAR WIND RISING": "solarwind interference rising · watch latency",
                "REROUTING TRAFFIC": "route     traffic moved to relay-04",
                "SIGNAL RECOVERED": "signal    lock recovered · error budget stable",
                "MANUAL INTERFERENCE": "operator  interference injected from console",
                "RECOVERING UPLINK": "operator  recovery sequence engaged",
            }
            self._append(messages.get(self._stage, "signal    state changed"))
        if not force and self._time % 15 != 0 and self._stage == previous_stage:
            return
        strength = self._strength(self._time)
        self.samples = [self._sample(self._time - index * 15) for index in range(47, -1, -1)]
        signal = 1 - strength * 0.58
        latency = round(42 + strength * 104 + self._channel * 13)
        throughput = round(880 - strength * 310 + 28 * math.sin(self._time / 80))
        drops = round(strength * 17)
        self.spark.values = self.samples
        self.spark.style = (
            self.theme.status.danger if strength > 0.65 else self.theme.status.success
        )
        self.signal_bar.fraction = signal
        rows = []
        for index in range(3):
            active = index == self._channel
            ping = latency if active else 55 + index * 21 + round(strength * 30)
            rows.append([f"{2 + index * 2:02d}", str(ping), "on" if active else "idle"])
        self.relay_table.rows = rows
        self._summary.text = f"{throughput}/s · {drops} drop · {latency}ms"
        self._events.lines = [
            Line.from_text(entry, self.theme.text.muted) for entry in self.log[-3:]
        ]

    def tick(self, phase: int) -> str | None:
        if not self._paused:
            self._sync(phase)
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "space":
            self._paused = not self._paused
        elif key == "n":
            self._incident_at = self._time
            self._recovery_at = None
            self._sync(self._time, force=True)
        elif key == "r":
            if self._incident_at is None:
                self._incident_at = self._time
            self._recovery_at = self._time
            self._sync(self._time, force=True)
        elif key in ("left", "right"):
            step = -1 if key == "left" else 1
            self._channel = (self._channel + step) % len(_CHANNELS)
            self._sync(self._time, force=True)
        elif key in ("1", "2", "3"):
            self._channel = int(key) - 1
            self._sync(self._time, force=True)
        elif key in ("escape", "q"):
            return "menu" if key == "escape" else "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        if 3 <= pos.y < 3 + self._top_h:
            if pos.x < self._left_w:
                self.on_key(KeyEvent("n"))
            else:
                self.on_key(KeyEvent("right"))
        elif pos.y >= 4 + self._top_h:
            self.on_key(KeyEvent("r"))
        return None

    def render(self, c: Constraints, phase: int) -> Surface:
        if not self._paused:
            self._sync(phase)
        width, height = c.width, c.max_height or 24
        top_h = max(12, height - 11)
        left_w = max(28, width * 64 // 100)
        right_w = max(20, width - left_w - 1)
        self._top_h = top_h
        self._left_w = left_w
        self._graph_box.height = top_h - 2
        self._side_box.height = top_h - 2
        graph = Panel(
            self._graph_box,
            title="SIGNAL STRENGTH / 4 HZ VISUAL STREAM",
            theme=self.theme,
        )
        side = Panel(self._side_box, title=_CHANNELS[self._channel], theme=self.theme)
        top = Row([graph, side], widths=[left_w, right_w], gap=1).render(
            Constraints(width=width)
        )
        events = Panel(
            FixedHeight(self._events, 3),
            title="MISSION EVENTS / CAUSE AND EFFECT",
            theme=self.theme,
        ).render(Constraints(width=width))
        rows = [
            self._header(width),
            self._status(width),
            Line(),
            *list(top)[:top_h],
            Line(),
            *list(events)[:5],
            self._hint(width),
        ]
        return Surface.of(pad_rows(rows, height), width)

    def _header(self, width: int) -> Line:
        left = "DSN-07 / DEEP SPACE UPLINK"
        seconds = self._time // 60
        right = f"T+{seconds // 60:02d}:{seconds % 60:02d} · CH-{self._channel + 1:02d}"
        gap = max(1, width - len(left) - len(right) - 2)
        return Line(
            (
                Segment(" "),
                Segment(left, self.theme.content.accent),
                Segment(" " * gap),
                Segment(right, self.theme.text.faint),
                Segment(" "),
            )
        ).clip(_CLIP, width)

    def _status(self, width: int) -> Line:
        style = self.theme.status.success
        if self._stage in ("SOLAR WIND RISING", "REROUTING TRAFFIC"):
            style = self.theme.status.warning
        elif self._stage == "MANUAL INTERFERENCE":
            style = self.theme.status.danger
        paused = " · PAUSED" if self._paused else ""
        return Line.from_text(f" ● {self._stage}{paused}", style).clip(_CLIP, width)

    def _hint(self, width: int) -> Line:
        return Line.from_text(
            "space pause · n/r interfere/recover · ←/→ relay · esc lab",
            self.theme.text.faint,
        ).clip(_CLIP, width)
