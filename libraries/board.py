from __future__ import annotations


class GameBoard:
    def __init__(self, size: int):
        self.size = size
        self.placed_tiles: list[int] = []

    @property
    def last_tile(self) -> int | None:
        if not self.placed_tiles:
            return None
        return self.placed_tiles[-1]

    def place_tile(self, tile: int) -> bool:
        if len(self.placed_tiles) >= self.size:
            return False
        self.placed_tiles.append(tile)
        return True
