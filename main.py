from libraries.game_config import load_config
from libraries.game_orchestrator import GameOrchestrator
from libraries.player import Player
from libraries.player_engines.random_engine import RandomPlayerEngine


def run_game() -> None:
    config = load_config("config/game_rules.json")
    players = [
        Player("Dylan", RandomPlayerEngine(), config.points.start_points),
        Player("Jordan", RandomPlayerEngine(), config.points.start_points),
        Player("Albert", RandomPlayerEngine(), config.points.start_points),
        Player("Ferg", RandomPlayerEngine(), config.points.start_points),
    ]
    game = GameOrchestrator(players, config)
    game.play()


if __name__ == "__main__":
    run_game()
