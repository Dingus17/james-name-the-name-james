from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlayerConfig:
    name: str
    engine: str
    model_path: str | None = None
    deterministic: bool = True


@dataclass(frozen=True)
class PointRules:
    start_points: int
    first_round_play: int
    first_round_leapfrog_steal: int
    second_round_play: int
    second_round_leapfrog_steal: int
    forced_play_penalty: int


@dataclass(frozen=True)
class GameConfig:
    board_size: int
    min_tile: int
    max_tile: int
    hand_size: int
    points: PointRules
    players: tuple[PlayerConfig, ...]


def load_config(config_path: str | Path) -> GameConfig:
    config_file = Path(config_path)
    payload = json.loads(config_file.read_text())

    points = PointRules(**payload["points"])
    players = tuple(PlayerConfig(**player_payload) for player_payload in payload.get("players", []))
    return GameConfig(
        board_size=payload["board_size"],
        min_tile=payload["min_tile"],
        max_tile=payload["max_tile"],
        hand_size=payload["hand_size"],
        points=points,
        players=players,
    )
