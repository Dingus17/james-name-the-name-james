from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from libraries.game_config import GameConfig, PlayerConfig


def parse_player_override_specs(specs: list[str] | None, value_name: str) -> dict[int, str]:
    overrides: dict[int, str] = {}
    for spec in specs or []:
        if "=" not in spec:
            raise ValueError(f"Invalid {value_name} override '{spec}'. Expected INDEX=VALUE.")

        player_index_text, value = spec.split("=", 1)
        try:
            player_index = int(player_index_text)
        except ValueError as exc:
            raise ValueError(
                f"Invalid {value_name} override '{spec}'. Player index must be an integer."
            ) from exc

        overrides[player_index] = value

    return overrides


def apply_player_overrides(
    config: GameConfig,
    engine_overrides: dict[int, str] | None = None,
    model_path_overrides: dict[int, str | None] | None = None,
    deterministic_overrides: dict[int, bool] | None = None,
) -> GameConfig:
    engine_overrides = engine_overrides or {}
    model_path_overrides = model_path_overrides or {}
    deterministic_overrides = deterministic_overrides or {}

    players: list[PlayerConfig] = []
    for index, player in enumerate(config.players):
        updated_player = player

        if index in engine_overrides:
            updated_player = replace(updated_player, engine=engine_overrides[index])

        if index in model_path_overrides:
            model_path = model_path_overrides[index]
            if model_path is not None:
                model_path = str(Path(model_path))
            updated_player = replace(updated_player, model_path=model_path)

        if index in deterministic_overrides:
            updated_player = replace(updated_player, deterministic=deterministic_overrides[index])

        players.append(updated_player)

    return replace(config, players=tuple(players))
