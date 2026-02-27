from __future__ import annotations


class RandomPlayerEngine:
    """Simple deterministic engine: always favors the lowest legal tile."""

    def decide_to_start(self, hand: list[int], time_waited: int = 0) -> bool:
        if not hand:
            return False
        confidence_threshold = 8 + time_waited
        return min(hand) <= confidence_threshold

    def choose_tile_to_play(self, hand: list[int], last_tile: int | None) -> int | None:
        playable = [tile for tile in sorted(hand) if last_tile is None or tile > last_tile]
        if not playable:
            return None
        return playable[0]
