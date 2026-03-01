from libraries.game_config import load_config
from libraries.game_orchestrator import GameOrchestrator
from libraries.player import Player
from libraries.player_engines.engine_factory import create_player_engine

def run_game_set(num_games: int) -> None:
    results_list = []
    for i in range(num_games):
        print(f"\n=== Starting Game {i + 1} ===")
        results_list.append(run_game())
    compute_statistics(results_list)

def compute_statistics(results: list[dict[str, dict[str, int]]]) -> None:
    # Initialize statistics storage
    stats = {}

    # Process each game's results
    for final_scores in results:
        # Determine the winner
        winner = max(final_scores, key=lambda player: final_scores[player]['points'])

        # Update statistics for each player
        for player_name, metrics in final_scores.items():
            if player_name not in stats:
                stats[player_name] = {
                    'wins': 0,
                    'total_points': 0,
                    'total_leapfrogs': 0,
                    'total_leapfrogged': 0,
                    'total_penalties': 0,
                    'games_played': 0,
                }

            # Update wins and totals
            if player_name == winner:
                stats[player_name]['wins'] += 1
            
            stats[player_name]['total_points'] += metrics['points']
            stats[player_name]['total_leapfrogs'] += metrics['leapfrogs']
            stats[player_name]['total_leapfrogged'] += metrics['leapfrogged']
            stats[player_name]['total_penalties'] += metrics['penalties']
            stats[player_name]['games_played'] += 1

    # Print the statistics in a table format
    print(f"\n{'Player':<15} {'Wins':<10} {'Avg Points':<15} {'Avg Leapfrogs':<15} {'Avg Leapfrogged':<15} {'Avg Penalties':<15}")
    print("=" * 90)

    for name, data in stats.items():
        avg_points = data['total_points'] / data['games_played'] if data['games_played'] > 0 else 0
        avg_leapfrogs = data['total_leapfrogs'] / data['games_played'] if data['games_played'] > 0 else 0
        avg_leapfrogged = data['total_leapfrogged'] / data['games_played'] if data['games_played'] > 0 else 0
        avg_penalties = data['total_penalties'] / data['games_played'] if data['games_played'] > 0 else 0

        print(f"{name:<15} {data['wins']:<10} {avg_points:<15.2f} {avg_leapfrogs:<15.2f} {avg_leapfrogged:<15.2f} {avg_penalties:<15.2f}")


def run_game() -> None:
    config = load_config("config/game_rules.json")
    players = []
    num_players = len(config.players)

    for player_config in config.players:
        engine = create_player_engine(player_config, config, num_players)
        players.append(Player(player_config.name, engine, config.points.start_points))

    game = GameOrchestrator(players, config)
    results = game.play()
    return results


if __name__ == "__main__":
    run_game_set(1000)
