from __future__ import annotations

from libraries.game_config import GameConfig, PlayerConfig
from libraries.player_engines.cautious_engine import RandomPlayerEngine as CautiousPlayerEngine
from libraries.player_engines.confident_engine import RandomPlayerEngine as ConfidentPlayerEngine
from libraries.player_engines.human_engine import HumanPlayerEngine
from libraries.player_engines.ml_engine import MLPlayerEngine
from libraries.player_engines.random_engine import RandomPlayerEngine
from libraries.player_engines.very_cautious_engine import RandomPlayerEngine as VeryCautiousPlayerEngine
from libraries.player_engines.very_confident_engine import RandomPlayerEngine as VeryConfidentPlayerEngine
from libraries.player_engines.very_random_engine import RandomPlayerEngine as VeryRandomPlayerEngine


def create_player_engine(player_config: PlayerConfig, game_config: GameConfig, num_players: int):
    engine_name = player_config.engine.strip().lower()

    if engine_name == "random":
        return RandomPlayerEngine()
    if engine_name == "very_random":
        return VeryRandomPlayerEngine()
    if engine_name == "cautious":
        return CautiousPlayerEngine()
    if engine_name == "very_cautious":
        return VeryCautiousPlayerEngine()
    if engine_name == "confident":
        return ConfidentPlayerEngine()
    if engine_name == "very_confident":
        return VeryConfidentPlayerEngine()
    if engine_name == "ml":
        return MLPlayerEngine(
            hand_size=game_config.hand_size,
            min_tile=game_config.min_tile,
            num_players=num_players,
            max_tile=game_config.max_tile,
            model_path=player_config.model_path,
            deterministic=player_config.deterministic,
        )
    if engine_name == "human":
        return HumanPlayerEngine()

    raise ValueError(f"Unknown player engine '{player_config.engine}' for player '{player_config.name}'.")
