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
                if player.engine.decide_to_start(player.hand, waiting_cycles):
                    print(f"{player.name} decided to play first after waiting {waiting_cycles} cycles.")
                    self.leading_player = player
                    self._execute_play(player, round_number=1, forced=True)
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
    
        print(f"{forced_player.name} should have played a tile.")

        forced_player.points -= self.config.points.forced_play_penalty
        self._execute_play(forced_player, round_number=2, forced=True)
        self.leading_player = forced_player

    def _play_round(self, turn_order: list[Player], round_number: int) -> Player | None:
        for player in turn_order:
            if not player.has_tiles():
                continue
            tile = player.engine.choose_tile_to_play(
                player.hand,
                self.game_board.last_tile,
                round_number,
                self._other_player_hand_sizes(player),
            )
            if tile is None:
                print(f"{player.name} chose not to play a tile in round {round_number}.")
                continue
            self._execute_play(player, round_number)
            return player
        return None

    def _execute_play(self, player: Player, round_number: int, forced: bool = False) -> None:
        last_tile_before_play = self.game_board.last_tile
        tile = player.engine.choose_tile_to_play(
            player.hand,
            last_tile_before_play,
            round_number,
            other_player_hand_sizes=self._other_player_hand_sizes(player),
            forced=forced
        )
        if tile is None:
            return
        
        print(f"{player.name} placed {tile}.")

        skipped_plays = self._collect_skipped_tiles(player, last_tile_before_play, tile)
        
        self._resolve_skipped_plays(player, skipped_plays)

        self.game_board.place_tile(tile)
        player.remove_tile(tile)

        if not forced or self.turn_count == 1:
            if round_number == 1:
                player.points += self.config.points.first_round_play
            else:
                player.points += self.config.points.second_round_play

    def _collect_skipped_tiles(
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
                    print(f"{other_player.name} had {tile} and was leapfrogged by {acting_player.name}'s play of {played_tile}.")
                    skipped_tiles.append((tile, other_player))
        skipped_tiles.sort(key=lambda skipped_play: skipped_play[0])
        return skipped_tiles

    def _resolve_skipped_plays(
        self,
        acting_player: Player,
        skipped_tiles: list[tuple[int, Player]],
    ) -> None:
        for tile, skipped_player in skipped_tiles:
            self.game_board.place_tile(tile)
            skipped_player.remove_tile(tile)
            skipped_player.points += self.config.points.first_round_leapfrog_steal
            acting_player.points -= self.config.points.first_round_leapfrog_steal

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

    def _other_player_hand_sizes(self, acting_player: Player) -> list[int]:
        return [len(player.hand) for player in self.players if player is not acting_player]

    def _game_over(self) -> bool:
        if len(self.game_board.placed_tiles) >= self.config.board_size:
            return True
        if all(not player.has_tiles() for player in self.players):
            return True
        return False

    def _print_final_scores(self) -> None:
        print("Final scores")
        for player in self.players:
            print(f"- {player.name}: {player.points} points!")
