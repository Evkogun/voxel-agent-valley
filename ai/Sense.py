from Config import *
from level import Movement
from level import Level

# Returns what the agent can sense one tile away in a given direction
# print_senses and Vision.get_observations use this
def sense_direction(state, direction):

    dx, dy = DIRECTION_TO_VECTOR[direction]

    target_x = state.agent["x"] + dx
    target_y = state.agent["y"] + dy

    current_tile = state.cube_map.get((state.agent["x"], state.agent["y"], state.agent["z"] - 1))
    target_cube = Movement.get_cube_at_xy(state, target_x, target_y)

    if target_cube is None:
        if Movement.can_safely_fall_from_current_tile(state, target_x, target_y):
            return "safe_fall"
        return "empty"

    if target_cube["type"] in KEY_TYPES:
        return target_cube["type"]

    if target_cube["type"] == "door":
        if Level.has_required_door_keys(state, target_cube):
            return "door"
        return "door_blocked"

    if not Movement.can_move_between(state, current_tile, target_cube):
        return "blocked_height_change"

    if target_cube["type"] == "toggleable_hazard":
        if Level.toggleable_hazards_are_safe(state):
            return "toggleable_hazard_safe"
        return "toggleable_hazard_active"
    return target_cube["type"]

# Prints the agent state and immediate surroundings to the terminal (on button press)
# Mentioned after player actions and AI actions in main.run_action
def print_senses(state):

    print("")
    print("Agent state")
    print(f"Position: ({state.agent['x']}, {state.agent['y']}, {state.agent['z']})")
    print(f"Alive: {state.agent['alive']}")
    print(f"Inventory: {state.agent['inventory']}")

    print("")
    print("Sense")

    for direction in DIRECTION_TO_VECTOR:
        tile_type = sense_direction(state, direction)
        print(f"{direction}: {tile_type}")

    print("")

# Used to classify ambiguous tiles into format that informs the ai better
def get_scan_tile_type(state, cube):

    if cube is None:
        return "empty"

    if cube["type"] in KEY_TYPES:
        return cube["type"]

    if cube["type"] == "door":
        if Level.has_required_door_keys(state, cube):
            return "door"
        return "door_blocked"

    if cube["type"] == "toggleable_hazard":
        if Level.toggleable_hazards_are_safe(state):
            return "toggleable_hazard_safe"
        return "toggleable_hazard_active"

    return cube["type"]