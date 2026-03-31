from __future__ import annotations

from libraries.game_config import GameConfig
from libraries.game_session import GameSession
from libraries.player import Player


class GameOrchestrator(GameSession):
    def __init__(self, players: list[Player], config: GameConfig):
        super().__init__(players, config)
        for player in self.players:
            print("{}'s starting hand: {}".format(player.name, sorted(player.hand)))

    def play(self) -> dict[str, dict[str, int]]:
        if not self.players:
            return {}

        while self.step():
            if self.started:
                print(self.last_event)
                if self.turn_count > 0:
                    self._print_scores()

        self._print_final_scores()
        return self.results()

    def _print_final_scores(self) -> None:
        print("Final scores")
        for player in self.players:
            print(f"- {player.name}: {player.points} points!")

    def _print_scores(self) -> None:
        print(f"Turn {self.turn_count} scores")
        for player in self.players:
            print(f"- {player.name}: {player.points} points!")
