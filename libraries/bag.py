from __future__ import annotations

import random


class TileBag:
    def __init__(self, min_tile: int, max_tile: int, rng: random.Random | None = None):
        self.rng = rng if rng is not None else random.SystemRandom()
        self.tiles = list(range(min_tile, max_tile + 1))
        self.rng.shuffle(self.tiles)

    def draw_tile(self) -> int | None:
        if not self.tiles:
            return None
        return self.tiles.pop()
