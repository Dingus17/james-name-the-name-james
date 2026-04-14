# Leapfrog Tile Game

A configurable tile game simulation with:
- command-line simulation/play,
- a Pygame visualizer,
- and PPO training via Gymnasium + Stable-Baselines3.

## Quick start

### 1) Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run a normal game from the CLI

```bash
python main.py --config config/game_rules.json --games 1
```

### 3) Play as a human in the CLI

Use one or more `--human-player` indices (zero-based):

```bash
python main.py --human-player 0
```

When it is your turn, the game prints:
- current turn/round,
- last tile,
- your hand,
- other player hand sizes,
- your lowest legal tile,

then asks if you want to play now.

### 4) Play in the Pygame GUI

```bash
python visual_play.py --games 1 --tick-ms 500
```

For human-controlled seats:

```bash
python visual_play.py --human-player 0
```

Controls:
- `SPACE`: pause/resume
- `P`: human plays lowest legal tile
- `O`: human passes
- `ESC`: quit

### 5) Train a model

```bash
python train.py --config config/game_rules.json --generations 5 --timesteps-per-generation 50000
```

Saved checkpoints are written to `models/` by default.

## Configuration notes

Edit `config/game_rules.json` to customize:
- tile range (`min_tile`, `max_tile`),
- board size,
- hand size,
- scoring,
- player lineup and engines.

The game now handles variable hand sizes, including cases where total requested dealt tiles exceed available tiles (players will simply draw what is available).
