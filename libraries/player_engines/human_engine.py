from __future__ import annotations


class HumanPlayerEngine:
    """Marker engine for a player controlled by a person."""

    def decide_to_start(self, hand: list[int], time_waited: int = 0) -> bool:
        _ = time_waited
        return bool(hand)

    def choose_tile_to_play(
        self,
        hand: list[int],
        last_tile: int | None,
        round_number: int,
        other_player_hand_sizes: list[int],
        forced: bool = False,
    ):
        _ = hand
        _ = last_tile
        _ = round_number
        _ = other_player_hand_sizes
        _ = forced
        return None, None, None
