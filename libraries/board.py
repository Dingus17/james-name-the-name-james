class GameBoard:
    def __init__(self):
        self.board_squares = {}
        for i in range(1, 101):
            self.board_squares[i] = None  # Initialize all squares as empty

    def _next_free_square(self):
        for square, tile in self.board_squares.items():
            if tile is None:
                return square
        return None  # No free squares available
        
    def last_tile_placed(self):
        for square in sorted(self.board_squares.keys(), reverse=True):
            if self.board_squares[square] is not None:
                return self.board_squares[square]
        return None  # No tiles placed yet
    
    def place_next_time(self, tile):
        next_square = self._next_free_square()
        if next_square is not None:
            self.board_squares[next_square] = tile