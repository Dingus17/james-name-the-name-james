from __future__ import annotations

import argparse
import math

from libraries.config_overrides import apply_player_overrides, parse_player_override_specs
from libraries.game_config import load_config
from libraries.game_session import GameSession
from libraries.player import Player
from libraries.player_engines.engine_factory import create_player_engine


WINDOW_WIDTH = 1680
WINDOW_HEIGHT = 1020
BACKGROUND = (243, 238, 227)
PANEL_BG = (255, 252, 246)
PANEL_BORDER = (93, 82, 65)
TEXT = (38, 34, 28)
MUTED = (108, 96, 80)
EMPTY_TILE = (229, 221, 208)
GRID_LINE = (199, 189, 172)
SKIPPED_MARK = (255, 244, 166)
FORCED_MARK = (35, 35, 35)
LEGEND_BG = (244, 236, 224)
PLAYER_COLORS = [
    (205, 92, 92),
    (79, 129, 189),
    (111, 158, 96),
    (209, 145, 58),
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render up to four concurrent Leapfrog games with Pygame.")
    parser.add_argument("--config", default="config/game_rules.json", help="Path to the game config.")
    parser.add_argument("--games", type=int, default=1, help="Number of concurrent games to display (max 4).")
    parser.add_argument("--tick-ms", type=int, default=500, help="Milliseconds between game steps.")
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
        help="Override a player's model path for this run.",
    )
    return parser


def build_session(
    config_path: str,
    player_engine_specs: list[str],
    player_model_specs: list[str],
) -> GameSession:
    config = load_config(config_path)
    config = apply_player_overrides(
        config,
        engine_overrides=parse_player_override_specs(player_engine_specs, "engine"),
        model_path_overrides=parse_player_override_specs(player_model_specs, "model"),
    )
    players = []
    num_players = len(config.players)
    for player_config in config.players:
        engine = create_player_engine(player_config, config, num_players)
        players.append(Player(player_config.name, engine, config.points.start_points))
    return GameSession(players, config)


def fit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def draw_text(surface, font, text: str, color: tuple[int, int, int], x: int, y: int) -> None:
    surface.blit(font.render(text, True, color), (x, y))


def draw_badge(surface, font, text: str, fg: tuple[int, int, int], bg: tuple[int, int, int], x: int, y: int) -> None:
    text_surface = font.render(text, True, fg)
    width = text_surface.get_width() + 10
    height = text_surface.get_height() + 4
    surface.fill(bg, (x, y, width, height))
    surface.blit(text_surface, (x + 5, y + 2))


def draw_board(surface, session: GameSession, rect, fonts) -> None:
    body_font, small_font, tiny_font = fonts
    board_size = session.game_board.size
    columns = math.ceil(math.sqrt(board_size))
    rows = math.ceil(board_size / columns)
    cell_size = min(rect.width // columns, rect.height // rows)
    board_width = cell_size * columns
    board_height = cell_size * rows
    origin_x = rect.x + (rect.width - board_width) // 2
    origin_y = rect.y + (rect.height - board_height) // 2

    for index in range(board_size):
        row = index // columns
        column = index % columns
        x = origin_x + column * cell_size
        y = origin_y + row * cell_size
        tile_rect = (x, y, cell_size - 2, cell_size - 2)

        surface.fill(EMPTY_TILE, tile_rect)
        surface.fill(GRID_LINE, (x, y + cell_size - 2, cell_size - 2, 2))
        surface.fill(GRID_LINE, (x + cell_size - 2, y, 2, cell_size - 2))

        if index >= len(session.game_board.placements):
            continue

        placement = session.game_board.placements[index]
        color = PLAYER_COLORS[placement.player_index % len(PLAYER_COLORS)]
        surface.fill(color, tile_rect)

        if placement.kind == "skipped":
            stripe_height = max(4, cell_size // 6)
            surface.fill(SKIPPED_MARK, (x, y, cell_size - 2, stripe_height))
        elif placement.kind == "forced":
            border = max(3, cell_size // 10)
            surface.fill(FORCED_MARK, (x, y, cell_size - 2, border))
            surface.fill(FORCED_MARK, (x, y, border, cell_size - 2))
            surface.fill(FORCED_MARK, (x + cell_size - 2 - border, y, border, cell_size - 2))
            surface.fill(FORCED_MARK, (x, y + cell_size - 2 - border, cell_size - 2, border))

        value_font = body_font if cell_size >= 38 else small_font
        text_surface = value_font.render(str(placement.tile), True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(x + cell_size // 2, y + cell_size // 2 + 2))
        surface.blit(text_surface, text_rect)

        round_label = tiny_font.render(f"R{placement.round_number}", True, (255, 255, 255))
        surface.blit(round_label, (x + 4, y + 3))

        if placement.kind == "skipped":
            kind_label = tiny_font.render("SKIP", True, TEXT)
            surface.blit(kind_label, (x + 4, y + max(6, cell_size - 15)))
        elif placement.kind == "forced":
            kind_label = tiny_font.render("FORCED", True, (255, 255, 255))
            surface.blit(kind_label, (x + 4, y + max(6, cell_size - 15)))


def draw_player_row(surface, session: GameSession, player_index: int, x: int, y: int, width: int, fonts) -> int:
    body_font, small_font = fonts
    player = session.players[player_index]
    color = PLAYER_COLORS[player_index % len(PLAYER_COLORS)]
    placement_count = sum(1 for placement in session.game_board.placements if placement.player_index == player_index)

    surface.fill(color, (x, y + 3, 15, 15))
    draw_text(surface, body_font, fit_text(player.name, 22), TEXT, x + 22, y)
    draw_text(
        surface,
        small_font,
        f"Pts {player.points} | On board {placement_count} | Hand {len(player.hand)}",
        TEXT,
        x,
        y + 22,
    )
    draw_text(
        surface,
        small_font,
        f"Leapfrogs {player.leapfrogs} | Skipped by others {player.leapfrogged} | Pen {player.penalties}",
        MUTED,
        x,
        y + 40,
    )
    hand_text = " ".join(str(tile) for tile in sorted(player.hand)) or "-"
    draw_text(surface, small_font, fit_text(f"Hand: {hand_text}", max(24, width // 8)), MUTED, x, y + 58)
    return y + 82


def draw_legend(surface, rect, fonts) -> None:
    body_font, small_font = fonts
    surface.fill(LEGEND_BG, rect)
    draw_text(surface, body_font, "Board legend", TEXT, rect.x + 10, rect.y + 8)
    surface.fill(SKIPPED_MARK, (rect.x + 12, rect.y + 34, 20, 10))
    draw_text(surface, small_font, "Top stripe = leapfrog/skipped-in tile", TEXT, rect.x + 40, rect.y + 30)
    surface.fill((130, 130, 130), (rect.x + 12, rect.y + 56, 20, 20))
    surface.fill(FORCED_MARK, (rect.x + 12, rect.y + 56, 20, 3))
    surface.fill(FORCED_MARK, (rect.x + 12, rect.y + 56, 3, 20))
    surface.fill(FORCED_MARK, (rect.x + 29, rect.y + 56, 3, 20))
    surface.fill(FORCED_MARK, (rect.x + 12, rect.y + 73, 20, 3))
    draw_text(surface, small_font, "Dark border = forced play", TEXT, rect.x + 40, rect.y + 58)
    draw_text(surface, small_font, "Top-left badge shows round", TEXT, rect.x + 12, rect.y + 84)


def draw_log(surface, session: GameSession, rect, fonts) -> None:
    body_font, small_font = fonts
    surface.fill(LEGEND_BG, rect)
    draw_text(surface, body_font, "Move log", TEXT, rect.x + 10, rect.y + 8)
    line_y = rect.y + 34
    visible_lines = max(4, (rect.height - 42) // 18)
    for entry in session.move_log[-visible_lines:]:
        draw_text(surface, small_font, fit_text(entry, 70), TEXT, rect.x + 10, line_y)
        line_y += 18


def draw_session(surface, session: GameSession, panel_rect, game_index: int, fonts) -> None:
    title_font, body_font, small_font, tiny_font = fonts
    surface.fill(PANEL_BG, panel_rect)
    surface.fill(PANEL_BORDER, (panel_rect.x, panel_rect.y, panel_rect.width, 2))
    surface.fill(PANEL_BORDER, (panel_rect.x, panel_rect.bottom - 2, panel_rect.width, 2))
    surface.fill(PANEL_BORDER, (panel_rect.x, panel_rect.y, 2, panel_rect.height))
    surface.fill(PANEL_BORDER, (panel_rect.right - 2, panel_rect.y, 2, panel_rect.height))

    header_y = panel_rect.y + 12
    draw_text(surface, title_font, f"Game {game_index + 1}", TEXT, panel_rect.x + 16, header_y)
    state_text = (
        f"Turn {session.turn_count}   Round {session.round_number}   "
        f"Last tile {session.game_board.last_tile if session.game_board.last_tile is not None else '-'}"
    )
    draw_text(surface, body_font, state_text, TEXT, panel_rect.x + 118, header_y + 3)
    if session.finished:
        draw_badge(surface, small_font, "Finished", (255, 255, 255), PANEL_BORDER, panel_rect.right - 96, header_y)

    board_rect = surface.get_rect().copy()
    board_rect.x = panel_rect.x + 16
    board_rect.y = panel_rect.y + 58
    board_rect.width = min(panel_rect.width * 11 // 20, panel_rect.height - 110)
    board_rect.height = panel_rect.height - 78
    draw_board(surface, session, board_rect, (body_font, small_font, tiny_font))

    sidebar_x = board_rect.right + 18
    sidebar_width = panel_rect.right - sidebar_x - 14
    draw_text(surface, small_font, fit_text(session.last_event, 54), MUTED, sidebar_x, board_rect.y)

    stats_y = board_rect.y + 26
    for player_index in range(len(session.players)):
        stats_y = draw_player_row(
            surface,
            session,
            player_index,
            sidebar_x,
            stats_y,
            sidebar_width,
            (body_font, small_font),
        )

    legend_height = 108
    log_rect = surface.get_rect().copy()
    log_rect.x = sidebar_x
    log_rect.width = sidebar_width
    log_rect.y = max(stats_y + 8, panel_rect.bottom - 210)
    log_rect.height = panel_rect.bottom - log_rect.y - 14

    legend_rect = surface.get_rect().copy()
    legend_rect.x = sidebar_x
    legend_rect.width = sidebar_width
    legend_rect.y = log_rect.y - legend_height - 10
    legend_rect.height = legend_height

    if legend_rect.y < stats_y + 8:
        legend_rect.y = stats_y + 8
        log_rect.y = legend_rect.bottom + 10
        log_rect.height = panel_rect.bottom - log_rect.y - 14

    draw_legend(surface, legend_rect, (body_font, small_font))
    draw_log(surface, session, log_rect, (body_font, small_font))


def run_visualizer() -> None:
    args = build_arg_parser().parse_args()
    if args.games < 1 or args.games > 4:
        raise SystemExit("--games must be between 1 and 4.")

    try:
        import pygame
    except ImportError as exc:
        raise SystemExit("pygame is required for visual playback. Install it before running visual_play.py.") from exc

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Leapfrog Visual Runner")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 24, bold=True)
    body_font = pygame.font.SysFont("arial", 18)
    small_font = pygame.font.SysFont("arial", 13)
    tiny_font = pygame.font.SysFont("arial", 11, bold=True)
    fonts = (title_font, body_font, small_font, tiny_font)

    sessions = [
        build_session(args.config, args.player_engine, args.player_model)
        for _ in range(args.games)
    ]

    paused = False
    last_tick = pygame.time.get_ticks()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.key == pygame.K_SPACE:
                    paused = not paused

        now = pygame.time.get_ticks()
        if not paused and now - last_tick >= args.tick_ms:
            for session in sessions:
                session.step()
            last_tick = now

        screen.fill(BACKGROUND)
        header = f"SPACE pause/resume  ESC quit  Tick {args.tick_ms}ms"
        draw_text(screen, body_font, header, TEXT, 18, 12)

        columns = 1 if len(sessions) == 1 else 2
        rows = math.ceil(len(sessions) / columns)
        gap = 18
        top = 42
        panel_width = (WINDOW_WIDTH - gap * (columns + 1)) // columns
        panel_height = (WINDOW_HEIGHT - top - gap * (rows + 1)) // rows

        for index, session in enumerate(sessions):
            row = index // columns
            column = index % columns
            panel_rect = pygame.Rect(
                gap + column * (panel_width + gap),
                top + gap + row * (panel_height + gap),
                panel_width,
                panel_height,
            )
            draw_session(screen, session, panel_rect, index, fonts)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    run_visualizer()
