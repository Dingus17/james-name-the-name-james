from __future__ import annotations

from libraries.bag import TileBag
from libraries.board import GameBoard
from libraries.game_config import GameConfig
from libraries.player import Player


class GameOrchestrator:
    def __init__(self, players: list[Player], config: GameConfig):
        self.players = players
        self.config = config
        self.tile_bag = TileBag(config.min_tile, config.max_tile)
        self.game_board = GameBoard(config.board_size)
        self.turn_count = 0
        self.leading_player: Player | None = self.players[0] if self.players else None
        self._set_up_game()

    def _set_up_game(self) -> None:
        for player in self.players:
            for _ in range(self.config.hand_size):
                player.draw_tile(self.tile_bag)

    def play(self) -> None:
        if not self.players:
            return

        self._first_turn()

        while not self._game_over():
            self._next_structured_turn()

        self._print_final_scores()

    def _first_turn(self) -> None:
        self.turn_count += 1
        waiting_cycles = 0

        while True:
            for player in self.players:
                if not player.has_tiles():
                    continue
                if player.engine.decide_to_start(player.hand, waiting_cycles):
                    self.leading_player = player
                    chosen_tile = player.engine.choose_tile_to_play(player.hand, self.game_board.last_tile)
                    self._execute_play(player, chosen_tile, round_number=1)
                    return
            waiting_cycles += 1

    def _next_structured_turn(self) -> None:
        self.turn_count += 1
        turn_order = self._turn_order_from_leader()

        played_player = self._play_round(turn_order, round_number=1)
        if played_player is not None:
            self.leading_player = played_player
            return

        played_player = self._play_round(turn_order, round_number=2)
        if played_player is not None:
            self.leading_player = played_player
            return

        forced_player = self._find_forced_player()
        if forced_player is None:
            return

        forced_player.points -= self.config.points.forced_play_penalty
        forced_tile = forced_player.lowest_playable_tile(self.game_board.last_tile)
        self._execute_play(forced_player, forced_tile, round_number=2)
        self.leading_player = forced_player

    def _play_round(self, turn_order: list[Player], round_number: int) -> Player | None:
        for player in turn_order:
            if not player.has_tiles():
                continue
            tile = player.engine.choose_tile_to_play(player.hand, self.game_board.last_tile)
            if tile is None:
                continue
            self._execute_play(player, tile, round_number)
            return player
        return None

    def _execute_play(self, player: Player, tile: int | None, round_number: int) -> None:
        if tile is None:
            return

        last_tile_before_play = self.game_board.last_tile

        skipped_tiles = self._collect_skipped_tiles(
            acting_player=player,
            low_bound=last_tile_before_play,
            high_bound=tile,
        )

        for skipped_tile, tile_owner in skipped_tiles:
            self.game_board.place_tile(skipped_tile)
            tile_owner.remove_tile(skipped_tile)
            if round_number == 1:
                tile_owner.points += self.config.points.first_round_leapfrog_steal
                player.points -= self.config.points.first_round_leapfrog_steal

        self.game_board.place_tile(tile)
        player.remove_tile(tile)

        if round_number == 1:
            player.points += self.config.points.first_round_play
        else:
            player.points += self.config.points.second_round_play

    def _collect_skipped_tiles(
        self,
        acting_player: Player,
        low_bound: int | None,
        high_bound: int,
    ) -> list[tuple[int, Player]]:
        lower = low_bound if low_bound is not None else 0
        skipped: list[tuple[int, Player]] = []

        for other_player in self.players:
            if other_player is acting_player:
                continue
            for tile in other_player.sorted_hand():
                if lower < tile < high_bound:
                    skipped.append((tile, other_player))

        skipped.sort(key=lambda item: item[0])
        return skipped

    def _find_forced_player(self) -> Player | None:
        lowest_player: Player | None = None
        lowest_tile = None
        for player in self.players:
            tile = player.lowest_playable_tile(self.game_board.last_tile)
            if tile is None:
                continue
            if lowest_tile is None or tile < lowest_tile:
                lowest_tile = tile
                lowest_player = player
        return lowest_player

    def _turn_order_from_leader(self) -> list[Player]:
        if self.leading_player not in self.players:
            return list(self.players)

        leader_index = self.players.index(self.leading_player)
        return self.players[leader_index:] + self.players[:leader_index]

    def _game_over(self) -> bool:
        return all(not player.has_tiles() for player in self.players)

    def _print_final_scores(self) -> None:
        print("Final scores")
        for player in self.players:
            print(f"- {player.name}: {player.points} points, remaining hand={sorted(player.hand)}")
