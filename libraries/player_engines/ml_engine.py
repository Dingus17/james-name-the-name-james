from __future__ import annotations

from pathlib import Path

import numpy as np

from libraries.player_engines.random_engine import RandomPlayerEngine


class MLPlayerEngine:
    """Engine powered by a trained Stable-Baselines3 policy."""

    def __init__(
        self,
        hand_size: int,
        min_tile: int,
        num_players: int,
        max_tile: int,
        model_path: str | None = None,
        deterministic: bool = True,
    ):
        self.hand_size = hand_size
        self.min_tile = min_tile
        self.num_players = num_players
        self.max_tile = max_tile
        self._tile_feature_size = max_tile - min_tile + 1
        self.model_path = model_path
        self.deterministic = deterministic

        self._fallback_engine = RandomPlayerEngine()
        self._model = self._load_model(model_path)
        self._model_observation_mode = self._detect_model_observation_mode()

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

    def _detect_model_observation_mode(self) -> str | None:
        if self._model is None:
            return None

        observation_space = getattr(self._model, "observation_space", None)
        if observation_space is None:
            return None

        observation_type = observation_space.__class__.__name__
        if observation_type == "Box":
            expected_shape = (self._tile_feature_size,)
            if getattr(observation_space, "shape", None) != expected_shape:
                print(
                    f"ML model at '{self.model_path}' expects legacy Box observation shape "
                    f"{getattr(observation_space, 'shape', None)}, but the game now uses "
                    f"hand-size-invariant shape {expected_shape}. Falling back to random engine."
                )
                self._model = None
                return None
            return "box"

        if observation_type != "Dict":
            print(
                f"ML model at '{self.model_path}' uses unsupported observation type "
                f"'{observation_type}'. Falling back to random engine."
            )
            self._model = None
            return None

        spaces = getattr(observation_space, "spaces", {})
        expected_shapes = {
            "agent_lowest_tile": (1,),
            "agent_hand": (self._tile_feature_size,),
            "other_player_tiles_left": (self.num_players - 1,),
            "last_tile": (1,),
        }
        for key, expected_shape in expected_shapes.items():
            space = spaces.get(key)
            if space is None or getattr(space, "shape", None) != expected_shape:
                print(
                    f"ML model at '{self.model_path}' is incompatible with the current observation "
                    f"schema for '{key}'. Expected shape {expected_shape}, got "
                    f"{None if space is None else getattr(space, 'shape', None)}. "
                    "Falling back to random engine."
                )
                self._model = None
                return None

        return "dict"

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
    ) -> dict[str, np.ndarray | int] | np.ndarray:
        sorted_hand = sorted(hand)
        lowest_tile = sorted_hand[0] if sorted_hand else 0
        encoded_hand = np.zeros(self._tile_feature_size, dtype=np.int8)
        for tile in sorted_hand:
            tile_index = tile - self.min_tile
            if 0 <= tile_index < self._tile_feature_size:
                encoded_hand[tile_index] = 1

        padded_other_hand_sizes = list(other_player_hand_sizes[: self.num_players - 1])
        padded_other_hand_sizes += [0] * (self.num_players - 1 - len(padded_other_hand_sizes))
        encoded_round = max(0, min(1, round_number - 1))

        if self._model_observation_mode == "box":
            return encoded_hand

        return {
            "agent_lowest_tile": np.array([lowest_tile], dtype=np.int32),
            "agent_hand": encoded_hand,
            "other_player_tiles_left": np.array(padded_other_hand_sizes, dtype=np.int32),
            "last_tile": np.array([last_tile if last_tile is not None else 0], dtype=np.int32),
            "game_round": encoded_round,
        }
