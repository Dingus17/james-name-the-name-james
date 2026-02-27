from __future__ import annotations

from math import exp


class RandomPlayerEngine:
    """Simple deterministic engine: always favors the lowest legal tile."""

    def decide_to_start(self, hand: list[int], time_waited: int = 0) -> bool:
        if not hand:
            return False
        confidence_threshold = 2 + time_waited
        return min(hand) <= confidence_threshold

    def choose_tile_to_play(
        self,
        hand: list[int],
        last_tile: int | None,
        round_number: int,
        other_player_hand_sizes: list[int],
    ) -> int | None:
        _ = other_player_hand_sizes
        playable = [tile for tile in sorted(hand) if last_tile is None or tile > last_tile]
        if not playable:
            return None

        selected_tile = playable[0]
        if last_tile is None:
            return selected_tile

        gap = selected_tile - last_tile
        if gap > 12:
            return None

        confidence_threshold = exp(-gap / 4) * (1 + round_number * 0.5)
        if confidence_threshold <= 0.1:
            return None

        return selected_tile
