import random

from libraries.bag import TileBag
from libraries.board import GameBoard

class Player:
    def __init__(self, name, engine):
        self.name = name
        self.engine = engine
        self.hand = []
        self.points = 10

    def draw_tile(self, tile_bag: TileBag):
        tile = tile_bag.draw_tile()
        if tile is not None:
            self.hand.append(tile)
            print(f"{self.name} drew tile {tile}. Current hand: {self.hand}")
        else:
            print(f"{self.name} could not draw a tile because the bag is empty.")

    def place_tile(self, board: GameBoard):
        tile_to_play = self.engine.select_tile_to_play(self.hand, board)
        board.place_next_time(tile_to_play)
        print(f"{self.name} placed tile {tile_to_play} on the board.")
        return tile_to_play

    def draw_tile(self, tile_bag: TileBag):
        tile = tile_bag.draw_tile()
        if tile is not None:
            self.hand.append(tile)
            print(f"{self.name} drew tile {tile}. Current hand: {self.hand}")
        else:
            print(f"{self.name} could not draw a tile because the bag is empty.")

    def choose_to_start(self, time_waited: int = 0):
        return self.engine.decide_to_start(self.hand, time_waited)
        

if __name__ == "__main__":
    main()