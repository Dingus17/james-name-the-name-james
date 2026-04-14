from __future__ import annotations

import argparse

from libraries.config_overrides import apply_player_overrides, parse_player_override_specs
from libraries.game_config import load_config
from libraries.game_orchestrator import GameOrchestrator
from libraries.player import Player
from libraries.player_engines.engine_factory import create_player_engine


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Leapfrog games and print aggregate results.")
    parser.add_argument("--config", default="config/game_rules.json", help="Path to the game config.")
    parser.add_argument("--games", type=int, default=1, help="Number of games to run.")
    parser.add_argument(
        "--player-engine",
        action="append",
        default=[],
        metavar="INDEX=ENGINE",
        help="Override a player's engine for this run.",
    )
    parser.add_argument(
        "--player-model",
        action="append",
        default=[],
        metavar="INDEX=PATH",
        help="Override a player's model zip path for this run.",
    )
    parser.add_argument(
        "--human-player",
        action="append",
        type=int,
        default=[],
        metavar="INDEX",
        help="Mark a player index as human-controlled for command-line play.",
    )
    return parser


def run_game_set(
    num_games: int,
    config_path: str,
    player_engine_specs: list[str],
    player_model_specs: list[str],
    human_players: list[int],
) -> None:
    engine_overrides = parse_player_override_specs(player_engine_specs, "engine")
    model_overrides = parse_player_override_specs(player_model_specs, "model")

    results_list = []
    for game_index in range(num_games):
        print(f"\n=== Starting Game {game_index + 1} ===")
        results_list.append(
            run_game(
                config_path=config_path,
                player_engine_overrides=engine_overrides,
                player_model_overrides=model_overrides,
                human_players=human_players,
            )
        )
    compute_statistics(results_list)


def compute_statistics(results: list[dict[str, dict[str, int]]]) -> None:
    stats: dict[str, dict[str, float]] = {}

    for final_scores in results:
        winner = max(final_scores, key=lambda player: final_scores[player]["points"])

        for player_name, metrics in final_scores.items():
            if player_name not in stats:
                stats[player_name] = {
                    "wins": 0,
                    "total_points": 0,
                    "total_leapfrogs": 0,
                    "total_leapfrogged": 0,
                    "total_penalties": 0,
                    "games_played": 0,
                }

            if player_name == winner:
                stats[player_name]["wins"] += 1

            stats[player_name]["total_points"] += metrics["points"]
            stats[player_name]["total_leapfrogs"] += metrics["leapfrogs"]
            stats[player_name]["total_leapfrogged"] += metrics["leapfrogged"]
            stats[player_name]["total_penalties"] += metrics["penalties"]
            stats[player_name]["games_played"] += 1

    print(
        f"\n{'Player':<15} {'Wins':<10} {'Avg Points':<15} "
        f"{'Avg Leapfrogs':<15} {'Avg Leapfrogged':<15} {'Avg Penalties':<15}"
    )
    print("=" * 90)

    for name, data in stats.items():
        games_played = data["games_played"]
        avg_points = data["total_points"] / games_played if games_played > 0 else 0
        avg_leapfrogs = data["total_leapfrogs"] / games_played if games_played > 0 else 0
        avg_leapfrogged = data["total_leapfrogged"] / games_played if games_played > 0 else 0
        avg_penalties = data["total_penalties"] / games_played if games_played > 0 else 0

        print(
            f"{name:<15} {int(data['wins']):<10} {avg_points:<15.2f} {avg_leapfrogs:<15.2f} "
            f"{avg_leapfrogged:<15.2f} {avg_penalties:<15.2f}"
        )


def run_game(
    config_path: str,
    player_engine_overrides: dict[int, str] | None = None,
    player_model_overrides: dict[int, str] | None = None,
    human_players: list[int] | None = None,
) -> dict[str, dict[str, int]]:
    config = load_config(config_path)
    config = apply_player_overrides(
        config,
        engine_overrides=player_engine_overrides,
        model_path_overrides=player_model_overrides,
    )
    human_players = human_players or []

    engine_overrides = dict(player_engine_overrides or {})
    for index in human_players:
        engine_overrides[index] = "human"

    if engine_overrides:
        config = apply_player_overrides(config, engine_overrides=engine_overrides)

    players = []
    num_players = len(config.players)

    for player_config in config.players:
        engine = create_player_engine(player_config, config, num_players)
        players.append(Player(player_config.name, engine, config.points.start_points))

    game = GameOrchestrator(players, config)
    if not human_players:
        return game.play()

    if any(index < 0 or index >= len(players) for index in human_players):
        raise ValueError(f"Invalid --human-player index in {human_players}")

    while game.step():
        if game.started:
            print(game.last_event)
            if game.turn_count > 0:
                game._print_scores()

        pending = game.pending_human_decision()
        if pending is None:
            continue

        player = players[pending["player_index"]]
        print(f"\n{player.name}'s turn (human control)")
        print(f"- Turn {pending['turn_count']} Round {pending['round_number']}")
        print(f"- Last tile: {pending['last_tile'] if pending['last_tile'] is not None else '-'}")
        print(f"- Your hand: {sorted(player.hand)}")
        print(f"- Other hand sizes: {game.turn_manager.other_player_hand_sizes(player)}")
        print(
            f"- Lowest legal tile: {pending['playable_tile'] if pending['playable_tile'] is not None else '-'}"
        )

        while True:
            response = input("Play lowest legal tile? [y/n]: ").strip().lower()
            if response in {"y", "yes"}:
                game.submit_human_decision(play=True)
                break
            if response in {"n", "no"}:
                game.submit_human_decision(play=False)
                break
            print("Please enter 'y' or 'n'.")

    game._print_final_scores()
    return game.results()


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    run_game_set(
        num_games=args.games,
        config_path=args.config,
        player_engine_specs=args.player_engine,
        player_model_specs=args.player_model,
        human_players=args.human_player,
    )
