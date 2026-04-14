from __future__ import annotations

from pathlib import Path

import numpy as np

from libraries.player_engines.random_engine import RandomPlayerEngine


class MLPlayerEngine:
    """Engine powered by a trained Stable-Baselines3 policy."""

    def __init__(
        self,
        hand_size: int,
        num_players: int,
        max_tile: int,
        model_path: str | None = None,
        deterministic: bool = True,
    ):
        self.hand_size = hand_size
        self._encoded_hand_size = max(0, hand_size - 1)
        self.num_players = num_players
        self.max_tile = max_tile
        self.model_path = model_path
        self.deterministic = deterministic

        self._fallback_engine = RandomPlayerEngine()
        self._model = self._load_model(model_path)
        self._expects_box_observation = self._detect_box_observation_model()

    def _load_model(self, model_path: str | None):
        if not model_path:
            return None

        model_file = Path(model_path)
        if not model_file.exists():
            print(f"ML model not found at '{model_path}'. Falling back to random engine.")
            return None

        try:
            from stable_baselines3 import PPO
        except ImportError:
            print("stable_baselines3 is not installed. Falling back to random engine.")
            return None

        return PPO.load(model_file)
    
    def _detect_box_observation_model(self) -> bool:
        if self._model is None:
            return False

        observation_space = getattr(self._model, "observation_space", None)
        return observation_space is not None and observation_space.__class__.__name__ == "Box"

    def decide_to_start(self, hand: list[int], time_waited: int = 0) -> bool:
        return self._fallback_engine.decide_to_start(hand, time_waited)

    def choose_tile_to_play(
        self,
        hand: list[int],
        last_tile: int | None,
        round_number: int,
        other_player_hand_sizes: list[int],
        forced: bool = False,
    ):
        playable_tile = self._fallback_engine.choose_tile_to_play(
            hand,
            last_tile,
            round_number,
            other_player_hand_sizes,
            forced=True,
        )[0]

        if playable_tile is None:
            return None, None, None

        if forced:
            return playable_tile, None, None

        if self._model is None:
            return self._fallback_engine.choose_tile_to_play(
                hand,
                last_tile,
                round_number,
                other_player_hand_sizes,
                forced=False,
            )

        observation = self._build_observation(hand, last_tile, round_number, other_player_hand_sizes)
        prediction, _ = self._model.predict(observation, deterministic=self.deterministic)
        action = int(prediction)

        if action == 1:
            return playable_tile, 1.0, 0.5

        return None, 0.0, 0.5

    def _build_observation(
        self,
        hand: list[int],
        last_tile: int | None,
        round_number: int,
        other_player_hand_sizes: list[int],
    ) -> dict[str, list[int] | int] | np.ndarray:
        sorted_hand = sorted(hand)
        lowest_tile = sorted_hand[0] if sorted_hand else 0
        remaining_tiles = sorted_hand[1 : self.hand_size]
        padded_remaining = remaining_tiles + [0] * (self._encoded_hand_size - len(remaining_tiles))

        padded_other_hand_sizes = list(other_player_hand_sizes[: self.num_players - 1])
        padded_other_hand_sizes += [0] * (self.num_players - 1 - len(padded_other_hand_sizes))
        encoded_round = max(0, min(1, round_number - 1))

        if self._expects_box_observation:
            return np.asarray(padded_remaining, dtype=np.int32)

        return {
            "agent_lowest_tile": [lowest_tile],
            "agent_hand": padded_remaining,
            "other_player_tiles_left": padded_other_hand_sizes,
            "last_tile": [last_tile if last_tile is not None else 0],
            "game_round": encoded_round,
        }
