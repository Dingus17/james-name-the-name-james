from __future__ import annotations

from libraries.bag import TileBag


class Player:
    def __init__(self, name: str, engine, start_points: int):
        self.name = name
        self.engine = engine
        self.hand: list[int] = []
        self.points = start_points
        self.leapfrogs = 0
        self.leapfrogged = 0
        self.penalties = 0

    def draw_tile(self, tile_bag: TileBag) -> None:
        tile = tile_bag.draw_tile()
        if tile is not None:
            self.hand.append(tile)

    def sorted_hand(self) -> list[int]:
        return sorted(self.hand)

    def lowest_playable_tile(self, last_tile: int | None) -> int | None:
        for tile in self.sorted_hand():
            if last_tile is None or tile > last_tile:
                return tile
        return None

    def remove_tile(self, tile: int) -> None:
        self.hand.remove(tile)

    def has_tiles(self) -> bool:
        return len(self.hand) > 0
