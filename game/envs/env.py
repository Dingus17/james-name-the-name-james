from __future__ import annotations

import random
from typing import Any

import gymnasium as gym
import numpy as np

from libraries.bag import TileBag
from libraries.board import GameBoard
from libraries.config_overrides import apply_player_overrides
from libraries.game_config import GameConfig, load_config
from libraries.player import Player
from libraries.player_engines.engine_factory import create_player_engine
from libraries.turn_manager import TurnManager


class LeapFrogEnv(gym.Env):
    """Gymnasium environment for the tile leapfrog game.

    The environment reuses ``TurnManager`` so scoring and turn progression stay
    aligned with the core game rules.

    Actions are intentionally simple to keep learning approachable:
    - 0: pass
    - 1: play the lowest legal tile

    It supports either:
    - single-agent control (an ``int`` action and a single observation), or
    - multi-agent control (``dict[player_index, int]`` actions and per-player
      observations/rewards).
    """

    metadata = {"render_modes": ["human"]}

    ACTION_PASS = 0
    ACTION_PLAY = 1

    def __init__(
        self,
        config_path: str = "config/game_rules.json",
        num_players: int | None = None,
        controlled_player_indices: list[int] | None = None,
        player_engine_overrides: dict[int, str] | None = None,
        player_model_path_overrides: dict[int, str | None] | None = None,
        player_deterministic_overrides: dict[int, bool] | None = None,
    ):
        base_config = load_config(config_path)
        self.config: GameConfig = apply_player_overrides(
            base_config,
            engine_overrides=player_engine_overrides,
            model_path_overrides=player_model_path_overrides,
            deterministic_overrides=player_deterministic_overrides,
        )
        config_player_count = len(self.config.players)

        if num_players is None:
            num_players = config_player_count
        if num_players < 2:
            raise ValueError("num_players must be at least 2")
        if num_players > config_player_count:
            raise ValueError(
                f"num_players={num_players} exceeds configured players ({config_player_count})"
            )

        self.num_players = num_players
        self.controlled_player_indices = sorted(controlled_player_indices or [0])
        if not self.controlled_player_indices:
            raise ValueError("At least one controlled player index must be provided")

        for idx in self.controlled_player_indices:
            if idx < 0 or idx >= self.num_players:
                raise ValueError(f"Controlled player index {idx} is out of range")

        self.single_agent_mode = len(self.controlled_player_indices) == 1

        self._single_observation_space = gym.spaces.Dict(
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
                "game_round": gym.spaces.Discrete(2),
            }
        )

        self._single_action_space = gym.spaces.Discrete(2)

        if self.single_agent_mode:
            self.action_space = self._single_action_space
            self.observation_space = self._single_observation_space
        else:
            self.action_space = gym.spaces.Dict(
                {
                    str(player_idx): self._single_action_space
                    for player_idx in self.controlled_player_indices
                }
            )
            self.observation_space = gym.spaces.Dict(
                {
                    str(player_idx): self._single_observation_space
                    for player_idx in self.controlled_player_indices
                }
            )

        self.players: list[Player] = []
        self.tile_bag: TileBag | None = None
        self.game_board: GameBoard | None = None
        self.turn_manager: TurnManager | None = None

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        _ = options
        tile_rng = None
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            tile_rng = random.Random(seed)

        self.tile_bag = TileBag(self.config.min_tile, self.config.max_tile, rng=tile_rng)
        self.game_board = GameBoard(self.config.board_size)

        player_configs = self.config.players[: self.num_players]
        self.players = [
            Player(
                player_cfg.name,
                create_player_engine(player_cfg, self.config, self.num_players),
                self.config.points.start_points,
            )
            for player_cfg in player_configs
        ]

        for player in self.players:
            player.hand.clear()
            for _ in range(self.config.hand_size):
                player.draw_tile(self.tile_bag)

        self.turn_manager = TurnManager(self.players, self.config, self.game_board)
        self._run_opening_play_if_needed()
        self._simulate_until_controlled_turn()

        observation = self._get_observation()
        info = self._get_info()
        return observation, info

    def step(self, action: int | dict[str, int] | dict[int, int]):
        if self.turn_manager is None:
            raise RuntimeError("Environment not reset. Call reset() before step().")

        pre_points = {idx: self.players[idx].points for idx in self.controlled_player_indices}

        current_idx = self.turn_manager.current_player_index()
        if current_idx is None:
            self.turn_manager.advance_round_or_turn()
            self._simulate_until_controlled_turn()
        elif current_idx in self.controlled_player_indices:
            action_map = self._normalize_action_map(action)
            if current_idx not in action_map:
                raise ValueError(
                    f"Missing action for controlled player {current_idx}. "
                    f"Expected one of {self.controlled_player_indices}."
                )

            current_action = action_map[current_idx]
            if current_action not in (self.ACTION_PASS, self.ACTION_PLAY):
                raise ValueError(f"Invalid action: {current_action}")

            self.turn_manager.apply_action(current_idx, current_action == self.ACTION_PLAY)
            self._simulate_until_controlled_turn()
        else:
            raise RuntimeError("step() called when it is not a controlled player's turn")

        observation = self._get_observation()
        reward_map = {
            idx: float(self.players[idx].points - pre_points[idx]) for idx in self.controlled_player_indices
        }
        reward = (
            reward_map[self.controlled_player_indices[0]]
            if self.single_agent_mode
            else {str(idx): value for idx, value in reward_map.items()}
        )

        terminated = self.turn_manager.game_over()
        truncated = False
        info = self._get_info()
        return observation, reward, terminated, truncated, info

    def render(self):
        if self.game_board is None or self.turn_manager is None:
            return

        round_number = (
            self.turn_manager.turn_state.round_number if self.turn_manager.turn_state else 1
        )
        print(
            f"Turn {self.turn_manager.turn_count} | Last tile: {self.game_board.last_tile} | "
            f"Round: {round_number}"
        )
        for idx, player in enumerate(self.players):
            marker = "*" if idx in self.controlled_player_indices else " "
            print(
                f"{marker} [{idx}] {player.name}: points={player.points}, hand={sorted(player.hand)}"
            )

    def _run_opening_play_if_needed(self) -> None:
        """Apply the same opening-play rules used by GameOrchestrator."""
        if self.turn_manager is None:
            return

        self.turn_manager.start_turn()
        waiting_cycles = 0

        while True:
            for index, player in enumerate(self.players):
                if player.engine.decide_to_start(player.hand, waiting_cycles):
                    self.turn_manager.leading_player_index = index
                    self.turn_manager.execute_play(player, round_number=1, forced=True)
                    self.turn_manager.start_turn()
                    return
            waiting_cycles += 1

    def _simulate_until_controlled_turn(self) -> None:
        if self.turn_manager is None:
            return

        while not self.turn_manager.game_over():
            current_idx = self.turn_manager.current_player_index()
            if current_idx is None:
                self.turn_manager.advance_round_or_turn()
                continue

            if current_idx in self.controlled_player_indices:
                return

            self._apply_npc_turn(current_idx)

    def _apply_npc_turn(self, player_index: int) -> None:
        player = self.players[player_index]
        if not player.has_tiles():
            self.turn_manager.apply_action(player_index, play=False)
            return

        round_number = self.turn_manager.turn_state.round_number
        tile, _, _ = player.engine.choose_tile_to_play(
            player.hand,
            self.game_board.last_tile,
            round_number,
            self.turn_manager.other_player_hand_sizes(player),
        )
        action = self.ACTION_PLAY if tile is not None else self.ACTION_PASS
        self.turn_manager.apply_action(player_index, action == self.ACTION_PLAY)

    def _normalize_action_map(self, action: int | dict[str, int] | dict[int, int]) -> dict[int, int]:
        if self.single_agent_mode:
            if isinstance(action, np.integer):
                action = int(action)
            if not isinstance(action, int):
                raise ValueError("Single-agent mode expects an integer action")
            return {self.controlled_player_indices[0]: action}

        if not isinstance(action, dict):
            raise ValueError("Multi-agent mode expects dict actions keyed by player index")

        normalized: dict[int, int] = {}
        for key, value in action.items():
            if isinstance(key, str):
                key = int(key)
            normalized[int(key)] = int(value)
        return normalized

    def _single_player_observation(self, player_index: int) -> dict[str, np.ndarray | int]:
        player = self.players[player_index]
        sorted_hand = sorted(player.hand)

        lowest_tile = sorted_hand[0] if sorted_hand else 0
        remaining_tiles = sorted_hand[1 : self.config.hand_size]
        padded_remaining = remaining_tiles + [0] * (self.config.hand_size - 1 - len(remaining_tiles))

        last_tile = self.game_board.last_tile if self.game_board.last_tile is not None else 0
        round_number = self.turn_manager.turn_state.round_number if self.turn_manager.turn_state else 1
        encoded_round = max(0, min(1, round_number - 1))

        other_sizes = [
            len(other_player.hand)
            for idx, other_player in enumerate(self.players)
            if idx != player_index
        ]

        return {
            "agent_lowest_tile": np.array([lowest_tile], dtype=np.int32),
            "agent_hand": np.array(padded_remaining, dtype=np.int32),
            "other_player_tiles_left": np.array(other_sizes, dtype=np.int32),
            "last_tile": np.array([last_tile], dtype=np.int32),
            "game_round": encoded_round,
        }

    def _get_observation(self):
        if self.single_agent_mode:
            return self._single_player_observation(self.controlled_player_indices[0])

        return {
            str(player_idx): self._single_player_observation(player_idx)
            for player_idx in self.controlled_player_indices
        }

    def _single_player_info(self, player_index: int) -> dict[str, Any]:
        player = self.players[player_index]
        legal_play = player.lowest_playable_tile(self.game_board.last_tile) is not None

        return {
            "player_index": player_index,
            "player_name": player.name,
            "player_points": player.points,
            "legal_play": legal_play,
            "turn": self.turn_manager.turn_count,
            "round_reward_values": {
                "first_round_play": self.config.points.first_round_play,
                "first_round_leapfrog_steal": self.config.points.first_round_leapfrog_steal,
                "second_round_play": self.config.points.second_round_play,
                "second_round_leapfrog_steal": self.config.points.second_round_leapfrog_steal,
                "forced_play_penalty": self.config.points.forced_play_penalty,
            },
        }

    def _get_info(self):
        if self.single_agent_mode:
            return self._single_player_info(self.controlled_player_indices[0])

        return {
            str(player_idx): self._single_player_info(player_idx)
            for player_idx in self.controlled_player_indices
        }
