"""A tiny snake game: a mutable Canvas rendered through a document FILL.

    uv run python examples/snake.py --headless     # a scripted game
    uv run python examples/snake.py                # live; arrow keys turn
"""

from __future__ import annotations

import argparse
import random
from collections import deque

from motui import App, headless_tui
from motui.kernel.cell import Surface
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.widgets import Canvas

_SNAKE = Style(fg="green")
_HEAD = Style(fg="green", bold=True)
_FOOD = Style(fg="red", bold=True)
_WALL = Style(fg="bright_black")


class Snake:
    """The game state and its canvas renderer (the document's FILL)."""

    def __init__(self, width: int = 40, height: int = 20, *, seed: int = 7) -> None:
        self.width = width
        self.height = height
        self.random = random.Random(seed)
        x, y = width // 2, height // 2
        self.body = deque([(x, y), (x - 1, y), (x - 2, y)])
        self.direction, self.alive, self.score, self.steps = (1, 0), True, 0, 0
        self.food = self._place_food()

    def _place_food(self):
        free = [
            (x, y) for y in range(1, self.height - 1) for x in range(1, self.width - 1)
            if (x, y) not in self.body
        ]
        return self.random.choice(free) if free else None

    def turn(self, dx: int, dy: int) -> None:
        if (dx, dy) != (-self.direction[0], -self.direction[1]):
            self.direction = (dx, dy)

    def step(self) -> None:
        if not self.alive or self.food is None:
            return
        self.steps += 1
        head = self.body[0]
        target = (head[0] + self.direction[0], head[1] + self.direction[1])
        inside = 1 <= target[0] < self.width - 1 and 1 <= target[1] < self.height - 1
        if not inside or target in self.body:
            self.alive = False
            return
        self.body.appendleft(target)
        if target == self.food:
            self.score += 1
            self.food = self._place_food()
        else:
            self.body.pop()

    def revision(self) -> object:
        """The row cache's snapshot: every input ``render`` reads."""
        return (self.steps, self.alive, self.score, tuple(self.body), self.food)

    def render(self, c: Constraints) -> Surface:
        """Draw the board into a canvas no larger than the constraints."""
        budget = self.height if c.max_height is None else c.max_height
        width, height = min(c.width, self.width), max(0, min(budget, self.height))
        canvas = Canvas(width, height)
        if width and height:
            canvas.box(0, 0, width, height, style=_WALL)
            for index, (x, y) in enumerate(self.body):
                if 0 < x < width and 0 < y < height:
                    canvas.put(x, y, "\u2588", _HEAD if index == 0 else _SNAKE)
            if self.food is not None:
                canvas.put(self.food[0], self.food[1], "\u25cf", _FOOD)
        return canvas.render(Constraints(width=c.width, max_height=height))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="motui snake example")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    game = Snake(40, 20, seed=args.seed)
    if args.headless:
        tui = headless_tui(game.width, game.height)
        tui.fill(game)
        for _ in range(max(0, args.steps)):
            game.step()
            tui.paint()
            if not game.alive:
                break
        print(f"snake headless: score {game.score}, steps {game.steps}, alive {game.alive}")
        return 0
    app = App()
    app.fill(game)
    turns = (("up", (0, -1)), ("down", (0, 1)), ("left", (-1, 0)), ("right", (1, 0)))
    for name, delta in turns:
        app.bind(name, lambda delta=delta: game.turn(*delta))

    def tick() -> None:
        game.step()
        if not game.alive:
            app.runtime.exit()
        app.runtime.refresh()

    app.runtime.every(0.12, tick)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
