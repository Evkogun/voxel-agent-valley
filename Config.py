from pathlib import Path

# File Name
VOX_FILE = Path("TestBench.vox")
LEVEL_SIZE = 40 # The expected size of the level in cubes. Used for scaling the render and centering the camera

# Generic init values
WIDTH = 600
HEIGHT = 600

# Timed hazard settings
TOGGLE_HAZARD_SAFE_TIME = 50000 # 50s, the ai is slow
PRESSURE_PLATE_BONUS = 30
TOGGLEABLE_HAZARD_BONUS = 35

temporary_objective = None

# Direction vectors used by the agent
DIRECTION_TO_VECTOR = {
    "stay": (0, 0), # Allows teleporting
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0),
}

MOVE_ACTION_TO_DIRECTION = {
    "move_north": "north",
    "move_west": "west",
    "move_south": "south",
    "move_east": "east",
}

BRANCH_SCAN_LIMIT = 30

SPECIAL_CONTINUATION_TYPES = {
    "stairs",
    "ladder",
    "ledge",
}

# Tiles the agent can normally stand on
WALKABLE_TYPES = {
    "spawn",
    "checkpoint",
    "path",
    "stairs",
    "ladder",
    "ledge",
    "timed_pressure_plate",
    "goal",
}

# Tiles that can be picked up
KEY_TYPES = {
    "key1",
    "key2",
}

KEY_LOCATION_ADJACENT = {
    (8, -4, 1): (5, -1, 3),
    (5, 2, 1): (5, -1, 4),
}

TYPE_TO_SYMBOL = {
    "spawn": "S",
    "checkpoint": "C",
    "path": ".",
    "stairs": "^",
    "ladder": "L",
    "key1": "1",
    "key2": "2",
    "door": "D",
    "ledge": "_",
    "hazard": "H",
    "toggleable_hazard": "T",
    "timed_pressure_plate": "P",
    "death_tile": "~",
    "goal": "G",
    "empty": "#",
    "unknown": "?",
    "agent": "A",
}

AGENT_STEP_TIME = 1000
AGENT_VISION_RADIUS = 12
AGENT_Z_VISION = 0
AGENT_MAX_Z = 8

# List of checkpoints as well as the goal for tracking
CHECKPOINT_LOCATIONS = [
    (-19, -11, 1),
    (-1, -11, 1),
    (18, -11, 1),
    (2, -1, 1),
    (-6, -3, 1),

    (-19, -1, 1), # goal
]