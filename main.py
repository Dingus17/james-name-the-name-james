from libraries.game_orchestrator import GameOrchestrator
from libraries.player import Player
from libraries.player_engines.random_engine import RandomPlayerEngine

player1 = Player("Dylan", RandomPlayerEngine())
player2 = Player("Jordan", RandomPlayerEngine())
player3 = Player("Albert", RandomPlayerEngine())
player4 = Player("Ferg", RandomPlayerEngine())

players = [player1, player2, player3, player4]

def run_game():
    game = GameOrchestrator(players)
    game.play()
    
if __name__ == "__main__":
    run_game()