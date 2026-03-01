from __future__ import annotations

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
from libraries.turn_manager import TurnManager


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
        self.turn_manager: TurnManager | None = None

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        _ = options
        if seed is not None:
            random.seed(seed)

        self.tile_bag = TileBag(self.config.min_tile, self.config.max_tile)
        self.game_board = GameBoard(self.config.board_size)

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

        self.turn_manager = TurnManager(self.players, self.config, self.game_board)
        self.turn_manager.start_turn()
        self._simulate_until_agent_turn()

        observation = self._get_observation()
        info = self._get_info()
        return observation, info

    def step(self, action: int):
        if self.turn_manager is None:
            raise RuntimeError("Environment not reset. Call reset() before step().")

        if action not in (self.ACTION_PASS, self.ACTION_PLAY):
            raise ValueError(f"Invalid action: {action}")

        if self.turn_manager.current_player_index() != self.agent_index:
            raise RuntimeError("step() called when it is not the agent's turn")

        agent = self.players[self.agent_index]
        pre_points = agent.points

        self.turn_manager.apply_action(self.agent_index, action == self.ACTION_PLAY)
        self._simulate_until_agent_turn()

        observation = self._get_observation()
        reward = float(agent.points - pre_points)
        terminated = self.turn_manager.game_over()
        truncated = False
        info = self._get_info()
        return observation, reward, terminated, truncated, info

    def render(self):
        if self.game_board is None or self.turn_manager is None:
            return
        round_number = self.turn_manager.turn_state.round_number if self.turn_manager.turn_state else 1
        print(f"Turn {self.turn_manager.turn_count} | Last tile: {self.game_board.last_tile} | Round: {round_number}")
        for player in self.players:
            print(f"- {player.name}: points={player.points}, hand={sorted(player.hand)}")

    def _simulate_until_agent_turn(self) -> None:
        if self.turn_manager is None:
            return

        while not self.turn_manager.game_over():
            current_idx = self.turn_manager.current_player_index()
            if current_idx is None:
                self.turn_manager.advance_round_or_turn()
                continue

            if current_idx == self.agent_index:
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

    def _get_observation(self) -> dict[str, np.ndarray | int]:
        agent = self.players[self.agent_index]
        sorted_hand = sorted(agent.hand)

        lowest_tile = sorted_hand[0] if sorted_hand else 0
        remaining_tiles = sorted_hand[1 : self.config.hand_size]
        padded_remaining = remaining_tiles + [0] * (self.config.hand_size - 1 - len(remaining_tiles))

        last_tile = self.game_board.last_tile if self.game_board.last_tile is not None else 0
        round_number = self.turn_manager.turn_state.round_number if self.turn_manager.turn_state else 1

        return {
            "agent_lowest_tile": np.array([lowest_tile], dtype=np.int32),
            "agent_hand": np.array(padded_remaining, dtype=np.int32),
            "other_player_tiles_left": np.array(
                [len(player.hand) for idx, player in enumerate(self.players) if idx != self.agent_index],
                dtype=np.int32,
            ),
            "last_tile": np.array([last_tile], dtype=np.int32),
            "game_round": round_number,
        }

    def _get_info(self) -> dict[str, Any]:
        agent = self.players[self.agent_index]
        legal_play = agent.lowest_playable_tile(self.game_board.last_tile) is not None
        return {
            "agent_points": agent.points,
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
