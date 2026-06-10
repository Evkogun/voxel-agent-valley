from Config import *
import core.Movement as Movement
import core.Level as Level

def setup(main_module):
    global main
    main = main_module

# Returns what the agent can sense one tile away in a given direction
# print_senses and Vision.get_observations use this
def sense_direction(cube_map, direction):

    dx, dy = DIRECTION_TO_VECTOR[direction]

    target_x = main.agent["x"] + dx
    target_y = main.agent["y"] + dy

    current_tile = cube_map.get((main.agent["x"], main.agent["y"], main.agent["z"] - 1))
    target_cube = Movement.get_cube_at_xy(cube_map, target_x, target_y)

    if target_cube is None:
        if Movement.can_safely_fall_from_current_tile(cube_map, target_x, target_y):
            return "safe_fall"
        return "empty"

    if target_cube["type"] in KEY_TYPES:
        return target_cube["type"]

    if target_cube["type"] == "door":
        if Level.has_required_door_keys(cube_map, target_cube):
            return "door"
        return "door_blocked"

    if not Movement.can_move_between(current_tile, target_cube):
        return "blocked_height_change"

    if target_cube["type"] == "toggleable_hazard":
        if Level.toggleable_hazards_are_safe():
            return "toggleable_hazard_safe"
        return "toggleable_hazard_active"
    return target_cube["type"]

# Prints the agent state and immediate surroundings to the terminal (on button press)
# Mentioned after player actions and AI actions in main.run_action
def print_senses(cube_map):

    print("")
    print("Agent state")
    print(f"Position: ({main.agent['x']}, {main.agent['y']}, {main.agent['z']})")
    print(f"Alive: {main.agent['alive']}")
    print(f"Inventory: {main.agent['inventory']}")

    print("")
    print("Sense")

    for direction in DIRECTION_TO_VECTOR:
        tile_type = sense_direction(cube_map, direction)
        print(f"{direction}: {tile_type}")

    print("")

# Used to classify ambiguous tiles into format that informs the ai better
def get_scan_tile_type(cube_map, cube):

    if cube is None:
        return "empty"

    if cube["type"] in KEY_TYPES:
        return cube["type"]

    if cube["type"] == "door":
        if Level.has_required_door_keys(cube_map, cube):
            return "door"
        return "door_blocked"

    if cube["type"] == "toggleable_hazard":
        if Level.toggleable_hazards_are_safe():
            return "toggleable_hazard_safe"
        return "toggleable_hazard_active"

    return cube["type"]