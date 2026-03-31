from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TilePlacement:
    tile: int
    player_index: int | None
    round_number: int
    kind: str
    turn_count: int


class GameBoard:
    def __init__(self, size: int):
        self.size = size
        self.placed_tiles: list[int] = []
        self.placements: list[TilePlacement] = []

    @property
    def last_tile(self) -> int | None:
        if not self.placed_tiles:
            return None
        return self.placed_tiles[-1]

    def place_tile(
        self,
        tile: int,
        player_index: int | None = None,
        round_number: int = 1,
        kind: str = "normal",
        turn_count: int = 0,
    ) -> bool:
        if len(self.placed_tiles) >= self.size:
            return False
        self.placed_tiles.append(tile)
        self.placements.append(
            TilePlacement(
                tile=tile,
                player_index=player_index,
                round_number=round_number,
                kind=kind,
                turn_count=turn_count,
            )
        )
        return True
