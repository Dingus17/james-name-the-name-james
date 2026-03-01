from typing import Optional
import numpy as np
import gymnasium as gym

class LeapFrogEnv(gym.Env):
    def __init__(self, size: int = 100):
        # The size of the board
        self.size = size

        # Initialize positions - will be set randomly in reset()
        # Using -1,-1 as "uninitialized" state
        self._agent_location = np.array([-1, -1], dtype=np.int32)
        self._target_location = np.array([-1, -1], dtype=np.int32)

        # Define what the agent can observe
        # Dict space gives us structured, human-readable observations
        self.observation_space = gym.spaces.Dict(
            {
                "agent_hand": gym.spaces.Discrete(, dtype=int),
                "next_tile": gym.spaces.Box(0, size - 1, shape=(2,), dtype=int),
                "last_tile": gym.spaces.Box(0, size - 1, shape=(2,), dtype=int),
                "other_player_tiles_left": gym.spaces.Box(0, size - 1, shape=(2,), dtype=int),
            }
        )

        # Define what actions are available (4 directions)
        self.action_space = gym.spaces.Discrete(4)

        # Map action numbers to actual movements on the grid
        # This makes the code more readable than using raw numbers
        self._action_to_direction = {
            0: np.array([0, 1]),   # Move right (column + 1)
            1: np.array([-1, 0]),  # Move up (row - 1)
            2: np.array([0, -1]),  # Move left (column - 1)
            3: np.array([1, 0]),   # Move down (row + 1)
        }
