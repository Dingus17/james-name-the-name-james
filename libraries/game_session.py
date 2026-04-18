from __future__ import annotations

import random

from libraries.bag import TileBag
from libraries.board import GameBoard
from libraries.game_config import GameConfig
from libraries.player import Player
from libraries.turn_manager import TurnManager


class GameSession:
    """Stateful, step-driven game runner suitable for visual playback."""

    def __init__(
        self,
        players: list[Player],
        config: GameConfig,
        human_player_indices: list[int] | None = None,
    ):
        self.players = players
        self.config = config
        self.human_player_indices = set(human_player_indices or [])
        self.tile_bag = TileBag(config.min_tile, config.max_tile)
        self.game_board = GameBoard(config.board_size)
        self.turn_manager = TurnManager(self.players, self.config, self.game_board)
        self.started = False
        self.finished = False
        self.last_event = "Waiting to start"
        self.move_log: list[str] = []
        self.awaiting_human_index: int | None = None
        self._set_up_game()

    def has_human_players(self) -> bool:
        return bool(self.human_player_indices)

    def is_human_player(self, player_index: int) -> bool:
        return player_index in self.human_player_indices

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
        points_before = player.points
        placements_before = len(self.game_board.placements)
        self.turn_manager.apply_action(current_index, play=play)

        if play and tile is not None:
            placement = self.game_board.placements[-1]
            self._record_event(
                self._build_play_event(
                    player_index=current_index,
                    played_tile=tile,
                    round_number=placement.round_number,
                    confidence=None,
                    threshold=None,
                    source="human",
                    points_before=points_before,
                    placements_before=placements_before,
                )
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
        if self.is_human_player(current_index):
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
            self._record_event(
                f"T{self.turn_count} R{self.round_number}: {player.name}'s turn, "
                f"{player.name} decided to pass (no tiles remaining)"
            )
            self.finished = self.turn_manager.game_over()
            return True

        round_number = self.turn_manager.turn_state.round_number
        points_before = player.points
        placements_before = len(self.game_board.placements)
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
                self._record_event(
                    f"T{self.turn_count} R{round_number}: {player.name}'s turn, "
                    f"{player.name} decided to pass on {candidate}"
                )
            else:
                self._record_event(
                    f"T{self.turn_count} R{round_number}: {player.name}'s turn, "
                    f"{player.name} decided to pass on {candidate} ({confidence:.2f}/{threshold:.2f})"
                )
            self.finished = self.turn_manager.game_over()
            return True

        self.turn_manager.apply_action(current_index, play=True)
        self._record_event(
            self._build_play_event(
                player_index=current_index,
                played_tile=tile,
                round_number=round_number,
                confidence=confidence,
                threshold=threshold,
                source="ai",
                points_before=points_before,
                placements_before=placements_before,
            )
        )
        self.finished = self.turn_manager.game_over()
        return True

    def _first_turn(self) -> None:
        if all(not player.has_tiles() for player in self.players):
            self.turn_manager.start_turn()
            self._record_event("No opening move possible because every hand is empty")
            return

        starting_index = random.randrange(len(self.players))
        self.turn_manager.leading_player_index = starting_index
        self.turn_manager.start_turn()

        starter = self.players[starting_index]
        self._record_event(f"T1 R1 starting player selected at random: {starter.name}")

    def _build_play_event(
        self,
        player_index: int,
        played_tile: int,
        round_number: int,
        confidence: float | None,
        threshold: float | None,
        source: str,
        points_before: int,
        placements_before: int,
    ) -> str:
        player = self.players[player_index]
        placements = self.game_board.placements[placements_before:]
        if not placements:
            return f"T{self.turn_count} R{round_number}: {player.name} attempted to play {played_tile}, but no tile was placed"

        played_placement = placements[-1]
        skipped_placements = [placement for placement in placements if placement.kind == "skipped"]

        decision_text = f"{player.name}'s turn, {player.name} decided to play tile {played_tile}"
        if confidence is not None and threshold is not None:
            decision_text += f" ({source}: {confidence:.2f}/{threshold:.2f})"
        elif source == "human":
            decision_text += " (human)"

        outcome_parts: list[str] = [decision_text]
        if skipped_placements:
            leapfroggers = ", ".join(
                self.players[placement.player_index].name for placement in skipped_placements
            )
            steal_amount = (
                self.config.points.first_round_leapfrog_steal
                if played_placement.round_number == 1
                else self.config.points.second_round_leapfrog_steal
            )
            outcome_parts.append(
                f"{player.name} was leapfrogged by {leapfroggers}; they each stole {steal_amount} points"
            )

        points_after = player.points
        net_delta = points_after - points_before
        if net_delta >= 0:
            outcome_parts.append(f"{player.name} was correct +{net_delta} points")
        else:
            outcome_parts.append(f"{player.name} lost {abs(net_delta)} points")

        return f"T{played_placement.turn_count} R{played_placement.round_number}: " + " | ".join(outcome_parts)
