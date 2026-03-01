from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

import gymnasium as gym
import numpy as np

from libraries.bag import TileBag
from libraries.board import GameBoard
from libraries.game_config import GameConfig, load_config
from libraries.player import Player
from libraries.player_engines.cautious_engine import RandomPlayerEngine as CautiousPlayerEngine
from libraries.player_engines.confident_engine import RandomPlayerEngine as ConfidentPlayerEngine
from libraries.player_engines.random_engine import RandomPlayerEngine


@dataclass
class _TurnState:
    round_number: int
    pending_order: list[int]


class LeapFrogEnv(gym.Env):
    """Minimal Gymnasium environment for the tile leapfrog game.

    The learning agent controls player index 0 and may only choose between:
    - 0: pass
    - 1: play (attempt to play its lowest legal tile)

    Opponents are simulated with the existing rule-based engines.
    """

    metadata = {"render_modes": ["human"]}

    ACTION_PASS = 0
    ACTION_PLAY = 1

    def __init__(self, config_path: str = "config/game_rules.json", num_players: int = 4):
        if num_players < 2:
            raise ValueError("num_players must be at least 2")

        self.config: GameConfig = load_config(config_path)
        self.num_players = num_players
        self.agent_index = 0

        self.action_space = gym.spaces.Discrete(2)
        self.observation_space = gym.spaces.Dict(
            {
                "agent_lowest_tile": gym.spaces.Box(
                    low=0,
                    high=self.config.max_tile,
                    shape=(1,),
                    dtype=np.int32,
                ),
                "agent_hand": gym.spaces.Box(
                    low=0,
                    high=self.config.max_tile,
                    shape=(self.config.hand_size - 1,),
                    dtype=np.int32,
                ),
                "other_player_tiles_left": gym.spaces.Box(
                    low=0,
                    high=self.config.hand_size,
                    shape=(self.num_players - 1,),
                    dtype=np.int32,
                ),
                "last_tile": gym.spaces.Box(
                    low=0,
                    high=self.config.max_tile,
                    shape=(1,),
                    dtype=np.int32,
                ),
                "game_round": gym.spaces.Discrete(2, start=1),
            }
        )

        self.players: list[Player] = []
        self.tile_bag: TileBag | None = None
        self.game_board: GameBoard | None = None
        self.turn_count = 0
        self.leading_player_index = 0
        self.turn_state: _TurnState | None = None

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        _ = options
        if seed is not None:
            random.seed(seed)

        self.tile_bag = TileBag(self.config.min_tile, self.config.max_tile)
        self.game_board = GameBoard(self.config.board_size)
        self.turn_count = 1
        self.leading_player_index = 0

        self.players = [
            Player("Agent", RandomPlayerEngine(), self.config.points.start_points),
            Player("Cautious", CautiousPlayerEngine(), self.config.points.start_points),
            Player("Confident", ConfidentPlayerEngine(), self.config.points.start_points),
            Player("Random", RandomPlayerEngine(), self.config.points.start_points),
        ][: self.num_players]

        for player in self.players:
            player.hand.clear()
            for _ in range(self.config.hand_size):
                player.draw_tile(self.tile_bag)

        self.turn_state = _TurnState(round_number=1, pending_order=self._turn_order_from_leader())
        self._simulate_until_agent_turn()

        observation = self._get_observation()
        info = self._get_info()
        return observation, info

    def step(self, action: int):
        if self.turn_state is None or self.game_board is None:
            raise RuntimeError("Environment not reset. Call reset() before step().")

        if action not in (self.ACTION_PASS, self.ACTION_PLAY):
            raise ValueError(f"Invalid action: {action}")

        if not self.turn_state.pending_order or self.turn_state.pending_order[0] != self.agent_index:
            raise RuntimeError("step() called when it is not the agent's turn")

        agent = self.players[self.agent_index]
        pre_points = agent.points

        self._apply_action(self.agent_index, action)
        self._simulate_until_agent_turn()

        observation = self._get_observation()
        reward = float(agent.points - pre_points)
        terminated = self._game_over()
        truncated = False
        info = self._get_info()
        return observation, reward, terminated, truncated, info

    def render(self):
        if self.game_board is None:
            return
        print(f"Turn {self.turn_count} | Last tile: {self.game_board.last_tile} | Round: {self.turn_state.round_number}")
        for player in self.players:
            print(f"- {player.name}: points={player.points}, hand={sorted(player.hand)}")

    def _simulate_until_agent_turn(self) -> None:
        while not self._game_over() and self.turn_state is not None:
            if not self.turn_state.pending_order:
                self._advance_round_or_turn()
                continue

            current_idx = self.turn_state.pending_order[0]
            if current_idx == self.agent_index:
                return

            self._apply_npc_turn(current_idx)

    def _apply_npc_turn(self, player_index: int) -> None:
        player = self.players[player_index]
        if not player.has_tiles():
            self.turn_state.pending_order.pop(0)
            return

        tile, _, _ = player.engine.choose_tile_to_play(
            player.hand,
            self.game_board.last_tile,
            self.turn_state.round_number,
            self._other_player_hand_sizes(player),
        )
        action = self.ACTION_PLAY if tile is not None else self.ACTION_PASS
        self._apply_action(player_index, action)

    def _apply_action(self, player_index: int, action: int) -> None:
        player = self.players[player_index]
        round_number = self.turn_state.round_number
        can_play = player.lowest_playable_tile(self.game_board.last_tile) is not None
        played = action == self.ACTION_PLAY and can_play

        self.turn_state.pending_order.pop(0)

        if played:
            self._execute_play(player, round_number)
            self.leading_player_index = player_index
            self._start_new_turn()

    def _advance_round_or_turn(self) -> None:
        if self.turn_state.round_number == 1:
            self.turn_state.round_number = 2
            self.turn_state.pending_order = self._turn_order_from_leader()
            return

        forced_index = self._find_forced_player_index()
        if forced_index is not None:
            forced_player = self.players[forced_index]
            forced_player.points -= self.config.points.forced_play_penalty
            forced_player.penalties += 1
            self._execute_play(forced_player, round_number=2, forced=True)
            self.leading_player_index = forced_index

        self._start_new_turn()

    def _start_new_turn(self) -> None:
        self.turn_count += 1
        self.turn_state = _TurnState(round_number=1, pending_order=self._turn_order_from_leader())

    def _execute_play(self, player: Player, round_number: int, forced: bool = False) -> None:
        last_tile_before_play = self.game_board.last_tile
        tile = player.lowest_playable_tile(last_tile_before_play)
        if tile is None:
            return

        skipped_plays = self._collect_skipped_tiles(player, last_tile_before_play, tile)
        if skipped_plays:
            self._resolve_skipped_plays(player, skipped_plays, round_number)

        self.game_board.place_tile(tile)
        player.remove_tile(tile)

        if not forced:
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
                    skipped_tiles.append((tile, other_player))
        skipped_tiles.sort(key=lambda skipped_play: skipped_play[0])
        return skipped_tiles

    def _resolve_skipped_plays(
        self,
        acting_player: Player,
        skipped_tiles: list[tuple[int, Player]],
        round_number: int,
    ) -> None:
        for tile, skipped_player in skipped_tiles:
            self.game_board.place_tile(tile)
            skipped_player.remove_tile(tile)
            if round_number == 1:
                steal_amount = self.config.points.first_round_leapfrog_steal
            else:
                steal_amount = self.config.points.second_round_leapfrog_steal
            skipped_player.points += steal_amount
            skipped_player.leapfrogged += 1
            acting_player.points -= steal_amount
            acting_player.leapfrogs += 1

    def _find_forced_player_index(self) -> int | None:
        lowest_index: int | None = None
        lowest_tile: int | None = None
        for idx, player in enumerate(self.players):
            tile = player.lowest_playable_tile(self.game_board.last_tile)
            if tile is None:
                continue
            if lowest_tile is None or tile < lowest_tile:
                lowest_tile = tile
                lowest_index = idx
        return lowest_index

    def _turn_order_from_leader(self) -> list[int]:
        order = list(range(self.num_players))
        return order[self.leading_player_index :] + order[: self.leading_player_index]

    def _other_player_hand_sizes(self, acting_player: Player) -> list[int]:
        return [len(player.hand) for player in self.players if player is not acting_player]

    def _game_over(self) -> bool:
        if self.game_board is None:
            return True
        if len(self.game_board.placed_tiles) >= self.config.board_size:
            return True
        return all(not player.has_tiles() for player in self.players)

    def _get_observation(self) -> dict[str, np.ndarray | int]:
        agent = self.players[self.agent_index]
        sorted_hand = sorted(agent.hand)

        lowest_tile = sorted_hand[0] if sorted_hand else 0
        remaining_tiles = sorted_hand[1 : self.config.hand_size]
        padded_remaining = remaining_tiles + [0] * (self.config.hand_size - 1 - len(remaining_tiles))

        last_tile = self.game_board.last_tile if self.game_board.last_tile is not None else 0

        return {
            "agent_lowest_tile": np.array([lowest_tile], dtype=np.int32),
            "agent_hand": np.array(padded_remaining, dtype=np.int32),
            "other_player_tiles_left": np.array(
                [len(player.hand) for idx, player in enumerate(self.players) if idx != self.agent_index],
                dtype=np.int32,
            ),
            "last_tile": np.array([last_tile], dtype=np.int32),
            "game_round": self.turn_state.round_number,
        }

    def _get_info(self) -> dict[str, Any]:
        agent = self.players[self.agent_index]
        legal_play = agent.lowest_playable_tile(self.game_board.last_tile) is not None
        return {
            "agent_points": agent.points,
            "legal_play": legal_play,
            "turn": self.turn_count,
            "round_reward_values": {
                "first_round_play": self.config.points.first_round_play,
                "first_round_leapfrog_steal": self.config.points.first_round_leapfrog_steal,
                "second_round_play": self.config.points.second_round_play,
                "second_round_leapfrog_steal": self.config.points.second_round_leapfrog_steal,
                "forced_play_penalty": self.config.points.forced_play_penalty,
            },
        }
