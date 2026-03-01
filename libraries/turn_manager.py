from __future__ import annotations

from dataclasses import dataclass

from libraries.board import GameBoard
from libraries.game_config import GameConfig
from libraries.player import Player


@dataclass
class TurnState:
    round_number: int
    pending_order: list[int]


class TurnManager:
    """Shared game orchestration logic for turn progression and scoring."""

    def __init__(self, players: list[Player], config: GameConfig, board: GameBoard):
        self.players = players
        self.config = config
        self.board = board
        self.turn_count = 0
        self.leading_player_index = 0
        self.turn_state: TurnState | None = None

    def start_turn(self) -> None:
        self.turn_count += 1
        self.turn_state = TurnState(round_number=1, pending_order=self.turn_order_from_leader())

    def current_player_index(self) -> int | None:
        if self.turn_state is None or not self.turn_state.pending_order:
            return None
        return self.turn_state.pending_order[0]

    def apply_action(self, player_index: int, play: bool) -> bool:
        """Apply play/pass action for the current player.

        Returns True when the action ended the turn (because a tile was played).
        """
        if self.turn_state is None:
            raise RuntimeError("Turn has not started")
        if not self.turn_state.pending_order or self.turn_state.pending_order[0] != player_index:
            raise RuntimeError("Action submitted for non-current player")

        player = self.players[player_index]
        round_number = self.turn_state.round_number
        can_play = player.lowest_playable_tile(self.board.last_tile) is not None
        played = play and can_play

        self.turn_state.pending_order.pop(0)

        if played:
            self.execute_play(player, round_number)
            self.leading_player_index = player_index
            self.start_turn()
            return True

        return False

    def advance_round_or_turn(self) -> int | None:
        """Advance to round 2 or force a play when both rounds pass.

        Returns forced player index when forced play happened, else None.
        """
        if self.turn_state is None:
            raise RuntimeError("Turn has not started")

        if self.turn_state.round_number == 1:
            self.turn_state.round_number = 2
            self.turn_state.pending_order = self.turn_order_from_leader()
            return None

        forced_index = self.find_forced_player_index()
        if forced_index is not None:
            forced_player = self.players[forced_index]
            forced_player.points -= self.config.points.forced_play_penalty
            forced_player.penalties += 1
            self.execute_play(forced_player, round_number=2, forced=True)
            self.leading_player_index = forced_index

        self.start_turn()
        return forced_index

    def find_forced_player_index(self) -> int | None:
        lowest_index: int | None = None
        lowest_tile: int | None = None
        for idx, player in enumerate(self.players):
            tile = player.lowest_playable_tile(self.board.last_tile)
            if tile is None:
                continue
            if lowest_tile is None or tile < lowest_tile:
                lowest_tile = tile
                lowest_index = idx
        return lowest_index

    def turn_order_from_leader(self) -> list[int]:
        order = list(range(len(self.players)))
        return order[self.leading_player_index :] + order[: self.leading_player_index]

    def other_player_hand_sizes(self, acting_player: Player) -> list[int]:
        return [len(player.hand) for player in self.players if player is not acting_player]

    def game_over(self) -> bool:
        if len(self.board.placed_tiles) >= self.config.board_size:
            return True
        return all(not player.has_tiles() for player in self.players)

    def execute_play(self, player: Player, round_number: int, forced: bool = False) -> None:
        last_tile_before_play = self.board.last_tile
        tile = player.lowest_playable_tile(last_tile_before_play)
        if tile is None:
            return

        skipped_plays = self.collect_skipped_tiles(player, last_tile_before_play, tile)
        if skipped_plays:
            self.resolve_skipped_plays(player, skipped_plays, round_number)

        self.board.place_tile(tile)
        player.remove_tile(tile)

        if not forced or self.turn_count == 1:
            if round_number == 1:
                player.points += self.config.points.first_round_play
            else:
                player.points += self.config.points.second_round_play

    def collect_skipped_tiles(
        self,
        acting_player: Player,
        last_tile_before_play: int | None,
        played_tile: int,
    ) -> list[tuple[int, Player]]:
        low_bound = last_tile_before_play if last_tile_before_play is not None else 0
        skipped_tiles: list[tuple[int, Player]] = []
        for other_player in self.players:
            if other_player is acting_player:
                continue
            for tile in sorted(other_player.hand):
                if low_bound < tile < played_tile:
                    skipped_tiles.append((tile, other_player))
        skipped_tiles.sort(key=lambda skipped_play: skipped_play[0])
        return skipped_tiles

    def resolve_skipped_plays(
        self,
        acting_player: Player,
        skipped_tiles: list[tuple[int, Player]],
        round_number: int,
    ) -> None:
        for tile, skipped_player in skipped_tiles:
            self.board.place_tile(tile)
            skipped_player.remove_tile(tile)
            if round_number == 1:
                steal_amount = self.config.points.first_round_leapfrog_steal
            else:
                steal_amount = self.config.points.second_round_leapfrog_steal
            skipped_player.points += steal_amount
            skipped_player.leapfrogged += 1
            acting_player.points -= steal_amount
            acting_player.leapfrogs += 1
