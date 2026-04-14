from __future__ import annotations

from libraries.bag import TileBag
from libraries.board import GameBoard
from libraries.game_config import GameConfig
from libraries.player import Player
from libraries.turn_manager import TurnManager


class GameSession:
    """Stateful, step-driven game runner suitable for visual playback."""

    def __init__(self, players: list[Player], config: GameConfig):
        self.players = players
        self.config = config
        self.tile_bag = TileBag(config.min_tile, config.max_tile)
        self.game_board = GameBoard(config.board_size)
        self.turn_manager = TurnManager(self.players, self.config, self.game_board)
        self.started = False
        self.finished = False
        self.last_event = "Waiting to start"
        self.move_log: list[str] = []
        self.awaiting_human_index: int | None = None
        self._set_up_game()

    def pending_human_decision(self) -> dict[str, int | str | None] | None:
        if self.awaiting_human_index is None or self.turn_manager.turn_state is None:
            return None

        player = self.players[self.awaiting_human_index]
        playable = player.lowest_playable_tile(self.game_board.last_tile)
        return {
            "player_index": self.awaiting_human_index,
            "player_name": player.name,
            "round_number": self.turn_manager.turn_state.round_number,
            "turn_count": self.turn_count,
            "last_tile": self.game_board.last_tile,
            "playable_tile": playable,
            "hand_size": len(player.hand),
        }

    def submit_human_decision(self, play: bool) -> None:
        if self.awaiting_human_index is None:
            raise RuntimeError("No human action is pending")

        current_index = self.awaiting_human_index
        self.awaiting_human_index = None

        player = self.players[current_index]
        round_number = self.turn_manager.turn_state.round_number
        tile = player.lowest_playable_tile(self.game_board.last_tile)
        self.turn_manager.apply_action(current_index, play=play)

        if play and tile is not None:
            placement = self.game_board.placements[-1]
            self._record_event(
                f"T{placement.turn_count} R{placement.round_number} {placement.kind}: "
                f"{player.name} -> {tile} (human)"
            )
        elif play and tile is None:
            self._record_event(
                f"T{self.turn_count} R{round_number}: {player.name} wanted to play but had no legal tile"
            )
        else:
            if tile is None:
                self._record_event(
                    f"T{self.turn_count} R{round_number}: {player.name} passed (human, no legal tile)"
                )
            else:
                self._record_event(
                    f"T{self.turn_count} R{round_number}: {player.name} passed on {tile} (human)"
                )

        self.finished = self.turn_manager.game_over()

    @property
    def turn_count(self) -> int:
        return self.turn_manager.turn_count

    @property
    def round_number(self) -> int:
        if self.turn_manager.turn_state is None:
            return 1
        return self.turn_manager.turn_state.round_number

    def _set_up_game(self) -> None:
        for player in self.players:
            for _ in range(self.config.hand_size):
                player.draw_tile(self.tile_bag)

    def results(self) -> dict[str, dict[str, int]]:
        return {
            player.name: {
                "points": player.points,
                "leapfrogs": player.leapfrogs,
                "leapfrogged": player.leapfrogged,
                "penalties": player.penalties,
            }
            for player in self.players
        }

    def _record_event(self, message: str) -> None:
        self.last_event = message
        self.move_log.append(message)
        if len(self.move_log) > 18:
            self.move_log = self.move_log[-18:]

    def step(self) -> bool:
        if self.finished:
            return False

        if not self.started:
            self._first_turn()
            self.started = True
            self.finished = self.turn_manager.game_over()
            return True

        if self.turn_manager.game_over():
            self.finished = True
            self._record_event("Game over")
            return False

        if self.turn_manager.turn_state is None:
            self.turn_manager.start_turn()
            self._record_event(f"T{self.turn_count} started")
            return True

        if self.awaiting_human_index is not None:
            return True

        current_index = self.turn_manager.current_player_index()
        if current_index is None:
            forced_index = self.turn_manager.advance_round_or_turn()
            if forced_index is not None:
                forced_player = self.players[forced_index]
                placement = self.game_board.placements[-1]
                self._record_event(
                    f"T{placement.turn_count} R{placement.round_number} forced: "
                    f"{forced_player.name} -> {placement.tile}"
                )
            else:
                self._record_event(f"T{self.turn_count} advanced to R{self.round_number}")
            self.finished = self.turn_manager.game_over()
            return True

        player = self.players[current_index]
        if player.engine.__class__.__name__ == "HumanPlayerEngine":
            self.awaiting_human_index = current_index
            decision = self.pending_human_decision()
            playable_text = decision["playable_tile"] if decision is not None else None
            self._record_event(
                f"T{self.turn_count} R{self.round_number}: waiting for {player.name} "
                f"(human) decision; lowest legal tile: {playable_text if playable_text is not None else '-'}"
            )
            return True

        if not player.has_tiles():
            self.turn_manager.apply_action(current_index, play=False)
            self._record_event(f"T{self.turn_count} R{self.round_number}: {player.name} had no playable tiles")
            self.finished = self.turn_manager.game_over()
            return True

        round_number = self.turn_manager.turn_state.round_number
        tile, confidence, threshold = player.engine.choose_tile_to_play(
            player.hand,
            self.game_board.last_tile,
            round_number,
            self.turn_manager.other_player_hand_sizes(player),
        )

        if tile is None:
            candidate = player.sorted_hand()[0] if player.hand else "-"
            self.turn_manager.apply_action(current_index, play=False)
            if confidence is None or threshold is None:
                self._record_event(f"T{self.turn_count} R{round_number}: {player.name} passed")
            else:
                self._record_event(
                    f"T{self.turn_count} R{round_number}: {player.name} passed on {candidate} "
                    f"({confidence:.2f}/{threshold:.2f})"
                )
            self.finished = self.turn_manager.game_over()
            return True

        self.turn_manager.apply_action(current_index, play=True)
        placement = self.game_board.placements[-1]
        skipped_tiles = [
            str(entry.tile)
            for entry in reversed(self.game_board.placements[:-1])
            if entry.turn_count == placement.turn_count and entry.kind == "skipped"
        ]
        skipped_text = f" | skipped in: {', '.join(reversed(skipped_tiles))}" if skipped_tiles else ""
        if confidence is None or threshold is None:
            self._record_event(
                f"T{placement.turn_count} R{placement.round_number} {placement.kind}: "
                f"{player.name} -> {tile}{skipped_text}"
            )
        else:
            self._record_event(
                f"T{placement.turn_count} R{placement.round_number} {placement.kind}: "
                f"{player.name} -> {tile} ({confidence:.2f}/{threshold:.2f}){skipped_text}"
            )
        self.finished = self.turn_manager.game_over()
        return True

    def _first_turn(self) -> None:
        self.turn_manager.start_turn()
        if all(not player.has_tiles() for player in self.players):
            self._record_event("No opening move possible because every hand is empty")
            return

        waiting_cycles = 0

        while True:
            for index, player in enumerate(self.players):
                if player.engine.decide_to_start(player.hand, waiting_cycles):
                    self.turn_manager.leading_player_index = index
                    self.turn_manager.execute_play(player, round_number=1, forced=True)
                    self.turn_manager.start_turn()
                    opening_tile = self.game_board.last_tile
                    self._record_event(
                        f"T1 R1 forced-open: {player.name} -> {opening_tile} "
                        f"after {waiting_cycles} waits"
                    )
                    return
            waiting_cycles += 1
