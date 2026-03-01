from __future__ import annotations

from libraries.bag import TileBag
from libraries.board import GameBoard
from libraries.game_config import GameConfig
from libraries.player import Player
from libraries.turn_manager import TurnManager


class GameOrchestrator:
    def __init__(self, players: list[Player], config: GameConfig):
        self.players = players
        self.config = config
        self.tile_bag = TileBag(config.min_tile, config.max_tile)
        self.game_board = GameBoard(config.board_size)
        self.turn_manager = TurnManager(self.players, self.config, self.game_board)
        self._set_up_game()

    @property
    def turn_count(self) -> int:
        return self.turn_manager.turn_count

    def _set_up_game(self) -> None:
        for player in self.players:
            for _ in range(self.config.hand_size):
                player.draw_tile(self.tile_bag)
            print("{}'s starting hand: {}".format(player.name, sorted(player.hand)))

    def _get_final_scores(self) -> dict[str, int]:
        results = {}
        for player in self.players:
            results[player.name] = {
                "points": player.points,
                "leapfrogs": player.leapfrogs,
                "leapfrogged": player.leapfrogged,
                "penalties": player.penalties,
            }
        return results

    def play(self) -> None:
        if not self.players:
            return

        self._first_turn()

        while not self.turn_manager.game_over():
            print("\n--- Turn {} ---".format(self.turn_count))
            self._next_structured_turn()
            self._print_scores()

        self._print_final_scores()
        return self._get_final_scores()

    def _first_turn(self) -> None:
        self.turn_manager.start_turn()
        waiting_cycles = 0

        while True:
            for index, player in enumerate(self.players):
                if player.engine.decide_to_start(player.hand, waiting_cycles):
                    print(f"{player.name} decided to play first after waiting {waiting_cycles} cycles.")
                    self.turn_manager.leading_player_index = index
                    self.turn_manager.execute_play(player, round_number=1, forced=True)
                    self.turn_manager.start_turn()
                    return
            waiting_cycles += 1

    def _next_structured_turn(self) -> None:
        if self.turn_manager.turn_state is None:
            self.turn_manager.start_turn()

        while self.turn_manager.turn_state is not None:
            current_index = self.turn_manager.current_player_index()

            if current_index is None:
                forced_index = self.turn_manager.advance_round_or_turn()
                if forced_index is not None:
                    forced_player = self.players[forced_index]
                    next_tile = forced_player.lowest_playable_tile(self.game_board.last_tile)
                    if next_tile is None:
                        print(f"{forced_player.name} made a forced play.")
                    else:
                        print(f"{forced_player.name} should have played {next_tile}.")
                    return
                if self.turn_manager.turn_state.round_number == 1:
                    return
                continue

            player = self.players[current_index]
            if not player.has_tiles():
                self.turn_manager.apply_action(current_index, play=False)
                continue

            round_number = self.turn_manager.turn_state.round_number
            tile, confidence, threshold = player.engine.choose_tile_to_play(
                player.hand,
                self.game_board.last_tile,
                round_number,
                self.turn_manager.other_player_hand_sizes(player),
            )

            if tile is None:
                print(
                    f"{player.name} chose not to play {player.sorted_hand()[0]} in round {round_number}. "
                    f"Confidence: {confidence:.2f} (threshold: {threshold:.2f})"
                )
                self.turn_manager.apply_action(current_index, play=False)
                continue

            print(
                f"{player.name} chose to play {tile} in round {round_number}. "
                f"Confidence: {confidence:.2f} (threshold: {threshold:.2f})"
            )
            self.turn_manager.apply_action(current_index, play=True)
            return

    def _print_final_scores(self) -> None:
        print("Final scores")
        for player in self.players:
            print(f"- {player.name}: {player.points} points!")

    def _print_scores(self) -> None:
        print(f"Turn {self.turn_count} scores")
        for player in self.players:
            print(f"- {player.name}: {player.points} points!")
