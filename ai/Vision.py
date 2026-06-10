from Config import *
import ai.Sense as Sense
import ai.BranchScan as BranchScan
import Planner

def setup(main_module):
    global main
    main = main_module

# Created to allow defaulting to empty tiles
# setup function mentioned once in update_agent_vision
def create_empty_agent_vision():
    return [[[
        "#" for z in range(AGENT_MAX_Z)]
        for y in range(LEVEL_SIZE)]
        for x in range(LEVEL_SIZE)
    ]

# Used to return a visual representation of the game space to the ai
# Used in the get_observations and print_agent_text_vision
def get_agent_text_vision():

    offset = LEVEL_SIZE // 2
    vision_layers = []

    min_z = max(0, main.agent["z"] - 1 - AGENT_Z_VISION)
    max_z = min(AGENT_MAX_Z - 1, main.agent["z"] - 1 + AGENT_Z_VISION)

    for z in range(max_z, min_z - 1, -1):
        vision_lines = []
        for y in range(main.agent["y"] + offset - AGENT_VISION_RADIUS, main.agent["y"] + offset + AGENT_VISION_RADIUS + 1):
            row = ""
            for x in range(main.agent["x"] + offset - AGENT_VISION_RADIUS, main.agent["x"] + offset + AGENT_VISION_RADIUS + 1):
                if x < 0 or x >= LEVEL_SIZE or y < 0 or y >= LEVEL_SIZE:
                    row += "#"
                else:
                    row += agent_vision[x][y][z]
            vision_lines.append(row)
        vision_layers.append({"z": z, "map": vision_lines})

    return vision_layers

# Primarily used to create a new map every time the charecter moves
def update_agent_vision(cubes):
    global agent_vision

    agent_vision = create_empty_agent_vision()
    offset = LEVEL_SIZE // 2

    for cube in cubes:
        x = cube["x"] + offset
        y = cube["y"] + offset
        z = cube["z"]

        if 0 <= x < LEVEL_SIZE and 0 <= y < LEVEL_SIZE and 0 <= z < AGENT_MAX_Z:
            agent_vision[x][y][z] = TYPE_TO_SYMBOL.get(cube["type"], "?")

    if 0 <= main.agent["x"] + offset < LEVEL_SIZE and 0 <= main.agent["y"] + offset < LEVEL_SIZE and 0 <= main.agent["z"] - 1 < AGENT_MAX_Z:
        agent_vision[main.agent["x"] + offset][main.agent["y"] + offset][main.agent["z"] - 1] = "A"

# Prints the map on keypress of M
def print_agent_text_vision(cubes):
    update_agent_vision(cubes)
    vision = get_agent_text_vision()

    print("")
    print("Agent text vision")
    print(f"Position: ({main.agent['x']}, {main.agent['y']}, {main.agent['z']})")
    print("")

    for layer in vision:
        print(f"z = {layer['z']}")
        for row in layer["map"]:
            print(row)
        print("")

# Used to pathfind to the closes checkpoint
def distance_to_goal():

    goal_x, goal_y, goal_z = CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator]
    goal_z += 1
    # Giving the agent absolute distance should help it out
    return abs(main.agent["x"] - goal_x) + abs(main.agent["y"] - goal_y) + abs(main.agent["z"] - goal_z)

# Also used to pathfind to the closes checkpoint
# Results factor into agent path weight calulations
def direction_to_goal():

    dx = CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator][0] - main.agent["x"]
    dy = CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator][1] - main.agent["y"]
    dz = (CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator][2] + 1) - main.agent["z"]

    return {
        "x_difference": dx,
        "y_difference": dy,
        "z_difference": dz,

        "general_direction": {
            "east_west": "east" if dx > 0 else "west" if dx < 0 else "same",
            "north_south": "south" if dy > 0 else "north" if dy < 0 else "same",
            "vertical": "up" if dz > 0 else "down" if dz < 0 else "same",
        }
    }

# Main information file to give the ai/transfer info to Agent.py
def get_observations(cube_map, goal_cube):

    senses = {}

    for direction in DIRECTION_TO_VECTOR:
        senses[direction] = Sense.sense_direction(cube_map, direction)

    observation = {
        "position": {
            "x": main.agent["x"],
            "y": main.agent["y"],
            "z": main.agent["z"],
        },

        "alive": main.agent["alive"],
        "inventory": main.agent["inventory"],
        "surroundings": senses,
        "branch_analysis": BranchScan.get_branch_analysis(cube_map),
        "bfs_analysis": Planner.get_bfs_analysis(cube_map),

        "text_vision": {
            "vision_radius": AGENT_VISION_RADIUS,
            "z_vision": AGENT_Z_VISION,
            "legend": {
                "A": "agent",
                "S": "spawn",
                "C": "checkpoint",
                ".": "path",
                "^": "stairs",
                "L": "ladder",
                "1": "key1",
                "2": "key2",
                "D": "door",
                "_": "ledge",
                "H": "hazard",
                "T": "toggleable hazard",
                "P": "timed pressure plate",
                "~": "death tile",
                "G": "goal",
                "#": "empty or outside vision",
                "?": "unknown",
            },
            "layers": get_agent_text_vision(),
        },

        "goal": {
            "position": None if goal_cube is None else {
                "x": CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator][0],
                "y": CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator][1],
                "z": CHECKPOINT_LOCATIONS[main.checkpoint_tracking_iterator][2] + 1,
            },

            "distance": distance_to_goal(),
            "direction": direction_to_goal(),
        },

        "valid_actions": [
            "move_north",
            "move_east",
            "move_south",
            "move_west",
            "take",
        ],
        
        "goal_reached": main.goal_completed(goal_cube),
    }

    return observation
