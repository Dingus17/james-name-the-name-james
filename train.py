from __future__ import annotations

import argparse
from pathlib import Path

from libraries.config_overrides import parse_player_override_specs
from libraries.game_config import load_config


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a PPO agent for Leapfrog via Gymnasium.")
    parser.add_argument("--config", default="config/game_rules.json", help="Path to the game config.")
    parser.add_argument(
        "--output-dir",
        default="models",
        help="Directory for saved model checkpoints.",
    )
    parser.add_argument(
        "--model-name",
        default="leapfrog_ppo",
        help="Base filename for the saved model.",
    )
    parser.add_argument(
        "--timesteps-per-generation",
        type=int,
        default=50_000,
        help="PPO timesteps to train in each generation.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=5,
        help="Number of self-play generations to run.",
    )
    parser.add_argument(
        "--controlled-player",
        type=int,
        default=0,
        help="Player index controlled by the learning policy.",
    )
    parser.add_argument(
        "--num-envs",
        type=int,
        default=4,
        help="Number of parallel environments.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for PPO and environment resets.",
    )
    parser.add_argument(
        "--init-model",
        default=None,
        help="Optional existing PPO zip to continue training from.",
    )
    parser.add_argument(
        "--opponent-engine",
        action="append",
        default=[],
        metavar="INDEX=ENGINE",
        help="Override a non-controlled opponent engine during training.",
    )
    parser.add_argument(
        "--opponent-model",
        action="append",
        default=[],
        metavar="INDEX=PATH",
        help="Pin a specific opponent model path instead of self-play snapshots.",
    )
    return parser


def make_env_factory(
    config_path: str,
    controlled_player: int,
    seed: int,
    env_index: int,
    player_engine_overrides: dict[int, str],
    player_model_overrides: dict[int, str | None],
):
    def _factory():
        from stable_baselines3.common.monitor import Monitor

        from game.envs.env import LeapFrogEnv

        env = LeapFrogEnv(
            config_path=config_path,
            controlled_player_indices=[controlled_player],
            player_engine_overrides=player_engine_overrides,
            player_model_path_overrides=player_model_overrides,
        )
        env.reset(seed=seed + env_index)
        return Monitor(env)

    return _factory


def build_training_overrides(
    config_path: str,
    controlled_player: int,
    snapshot_path: str | None,
    opponent_engine_specs: list[str],
    opponent_model_specs: list[str],
) -> tuple[dict[int, str], dict[int, str | None]]:
    config = load_config(config_path)
    if controlled_player < 0 or controlled_player >= len(config.players):
        raise ValueError(
            f"controlled_player={controlled_player} is out of range for {len(config.players)} players."
        )

    engine_overrides = parse_player_override_specs(opponent_engine_specs, "engine")
    model_overrides = parse_player_override_specs(opponent_model_specs, "model")

    # The learning-controlled seat should not depend on a pre-existing model file.
    engine_overrides[controlled_player] = "random"
    model_overrides[controlled_player] = None

    if snapshot_path is not None:
        for index, player in enumerate(config.players):
            if index == controlled_player or index in model_overrides:
                continue
            if player.engine.strip().lower() == "ml":
                model_overrides[index] = snapshot_path
    else:
        for index, player in enumerate(config.players):
            if index == controlled_player or index in engine_overrides or index in model_overrides:
                continue
            if player.engine.strip().lower() == "ml":
                engine_overrides[index] = "random"
                model_overrides[index] = None

    return engine_overrides, model_overrides


def train() -> None:
    args = build_arg_parser().parse_args()

    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv
    except ImportError as exc:
        raise SystemExit(
            "stable_baselines3 is required for training. Install it before running train.py."
        ) from exc

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_snapshot: str | None = args.init_model
    model = None

    for generation in range(1, args.generations + 1):
        engine_overrides, model_overrides = build_training_overrides(
            config_path=args.config,
            controlled_player=args.controlled_player,
            snapshot_path=latest_snapshot,
            opponent_engine_specs=args.opponent_engine,
            opponent_model_specs=args.opponent_model,
        )

        env = DummyVecEnv(
            [
                make_env_factory(
                    config_path=args.config,
                    controlled_player=args.controlled_player,
                    seed=args.seed + generation * 1000,
                    env_index=env_index,
                    player_engine_overrides=engine_overrides,
                    player_model_overrides=model_overrides,
                )
                for env_index in range(args.num_envs)
            ]
        )

        if model is None:
            if args.init_model:
                model = PPO.load(args.init_model, env=env, seed=args.seed)
            else:
                model = PPO("MultiInputPolicy", env, verbose=1, seed=args.seed)
        else:
            model.set_env(env)

        print(
            f"Training generation {generation}/{args.generations} "
            f"for {args.timesteps_per_generation} timesteps."
        )
        model.learn(
            total_timesteps=args.timesteps_per_generation,
            reset_num_timesteps=(generation == 1 and args.init_model is None),
        )

        generation_stem = output_dir / f"{args.model_name}_gen{generation}"
        latest_stem = output_dir / args.model_name
        model.save(str(generation_stem))
        model.save(str(latest_stem))
        latest_snapshot = f"{generation_stem}.zip"
        env.close()

        print(f"Saved generation {generation} checkpoint to {generation_stem}.zip")

    print(f"Latest model available at {output_dir / (args.model_name + '.zip')}")


if __name__ == "__main__":
    train()
