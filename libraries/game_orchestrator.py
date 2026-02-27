from libraries.player import Player
from libraries.board import GameBoard
from libraries.bag import TileBag

class GameOrchestrator:
    def __init__(self, players: list[Player] = []):
        self.game_over = False
        self.turn_count = 0
        self.turn_round = 1
        self.players = players
        self.tile_bag = TileBag()
        self.game_board = GameBoard()
        self.set_up_game()
        self.leading_player = self.players[0] if self.players else None

    def _count_tiles_to_draw(self):
        return 10 # TODO: Implement logic to determine how many tiles to draw based on the game state

    def set_up_game(self):
        print("Setting up the game...")
        self.tile_bag.fill_bag()
        for player in self.players:
            for _ in range(self._count_tiles_to_draw()):
                player.draw_tile(self.tile_bag)

    def play(self):
        print("Starting the game!")
        print("Players:", [player.name for player in self.players])
        # while not self.game_over:
        self._next_turn()

    def end_game(self):
        self.game_over = True

    def _next_turn(self):
        self.turn_count += 1
        print(f"Turn {self.turn_count}")
        if self.turn_count == 1:
            self._first_game_turn()
        else:
            self._game_turn()

    def _first_game_turn(self):#
        print("Determining the starting player...")
        time_waited = 0
        starter_chosen = False
        while starter_chosen is False:
            for player in self.players:
                if player.choose_to_start(time_waited):
                    print(f"{player.name} has chosen to start the game!")
                    self.leading_player = player
                    starter_chosen = True
                    break
            time_waited += 1
        tile_placed = self.leading_player.place_tile(self.game_board)
        self._check_leap(tile_placed)

    def _check_leap(self, tile):
        

    def _game_turn(self):
        self.leading_player.take_turn(self.game_board)