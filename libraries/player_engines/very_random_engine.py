from __future__ import annotations

from math import exp
import random


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
        forced: bool = False
    ) -> int | None:
        _ = other_player_hand_sizes
        playable = [tile for tile in sorted(hand) if last_tile is None or tile > last_tile]
        if not playable:
            return None, None, None

        selected_tile = playable[0]
        if forced:
            return selected_tile, None, None

        if last_tile is None:
            return selected_tile, None, None

        gap = selected_tile - last_tile
        confidence_threshold = 0.7

        random_factor = random.uniform(0.4, 1.6)
        confidence = exp(-gap / (6.5 * random_factor)) * (1 + round_number * 0.2)
        if confidence <= confidence_threshold:
            return None, confidence, confidence_threshold

        return selected_tile, confidence, confidence_threshold