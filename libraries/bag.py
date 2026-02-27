import random

class TileBag:
    def __init__(self):
        self.tiles = []

    def fill_bag(self):
        for i in range(1, 101):
            self.tiles.append(i)
        print("Tile bag filled with tiles:", self.tiles)

    def draw_tile(self):
        if self.tiles:
            random_tile = random.choice(self.tiles)
            self.tiles.remove(random_tile)
            return random_tile
        else:
            print("The tile bag is empty!")
            return None