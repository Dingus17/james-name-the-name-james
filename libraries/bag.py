from __future__ import annotations

import random


class TileBag:
    def __init__(self, min_tile: int, max_tile: int):
        self.tiles = list(range(min_tile, max_tile + 1))
        random.shuffle(self.tiles)

    def draw_tile(self) -> int | None:
        if not self.tiles:
            return None
        return self.tiles.pop()
