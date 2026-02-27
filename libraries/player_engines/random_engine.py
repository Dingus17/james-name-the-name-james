class RandomPlayerEngine():
    def decide_to_start(self, hand, time_waited: int = 0):
        sorted_hand = sorted(hand)
        confidence = 100 - sorted_hand[0] + time_waited
        if confidence >= 99:
            return True
        return False
    
    def select_tile_to_play(self, hand, board):
        sorted_hand = sorted(hand)
        return sorted_hand[0]