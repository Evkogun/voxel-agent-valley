from Config import *
from level import Level

# Gets the highest cube at a x y position
# Used for finding the tile the agent is trying to move to and for top of ladder
# Used heavily in its get_top_cube form for ladders and sensing
# Used in its alternative format for door unlocking logic
def get_cube_at_xy(state, x, y, top_count = None, standing_z = None):

    if standing_z is None: standing_z = state.agent["z"]

    matching_cubes = []
    # Linear scan is acceptable for the current level size
    for cube_position in state.cube_map:

        cube_x = cube_position[0]
        cube_y = cube_position[1]

        if cube_x == x and cube_y == y: matching_cubes.append(state.cube_map[cube_position])

    matching_cubes.sort(
        key=lambda cube: cube["z"],
        reverse=True
    )

    # Gets cubes at same level or 1 below agent
    if top_count is None:
        for cube in matching_cubes:
            if cube["z"] == standing_z:
                if matching_cubes and matching_cubes[0]["type"] == "ladder" and cube["type"] == "ladder":
                    return matching_cubes[0] # Finds tops of ladders, check is in edge case of scanning a tile below a ladder
                return cube

        for cube in matching_cubes:
            if cube["z"] == standing_z - 1:
                return cube
            if cube["z"] == standing_z - 2:
                return cube # for stairs going downward
        return None
    return matching_cubes[:top_count]

# Removes a cube from both the list and the map
# Used to remove door and key tiles
def remove_cube(state, cube):

    if cube in state.cubes: state.cubes.remove(cube)

    cube_position = (cube["x"], cube["y"], cube["z"])

    if cube_position in state.cube_map: del state.cube_map[cube_position]


# Prevents the agent from moving onto tiles it cannot enter
# Thought to merge this and the next function, however this would impact specificity of messages
# Used in fall, block and kill logic
def can_enter_cube(state, cube):

    if cube is None: return False

    if cube["type"] == "hazard" or cube["type"] == "death_tile": return False

    if cube["type"] == "toggleable_hazard":
        if Level.toggleable_hazards_are_safe(state):
            return True
        return False

    if cube["type"] in WALKABLE_TYPES:
        return True
    return False


# Checks if movement from one tile to another is valid
# This fixes the pathing issues with walkable tiles of different elevations
def can_move_between(state, current_tile, target_cube):

    if target_cube is None: return False

    if not can_enter_cube(state, target_cube): return False

    if current_tile is None: return True

    if current_tile["type"] == "path" and target_cube["type"] == "path" and current_tile["z"] != target_cube["z"]:
        return False
    return True


# At target, find the highest cube below agent
# Used in ledge/sensing logic
def get_fall_target(state, x, y, standing_z = None):

    if standing_z is None: standing_z = state.agent["z"]

    fall_target = None

    # Again, very inefficient
    for cube_position in state.cube_map:

        cube_x = cube_position[0]
        cube_y = cube_position[1]
        cube_z = cube_position[2]

        if cube_x == x and cube_y == y and cube_z < standing_z:
            cube = state.cube_map[cube_position]

            if fall_target is None or cube_z > fall_target["z"]:
                fall_target = cube

    return fall_target


# Moves the agent onto a cube
# Heavily used in movement functions and respawn
def move_agent_to_cube(state, cube):

    state.agent["x"] = cube["x"]
    state.agent["y"] = cube["y"]
    state.agent["z"] = cube["z"] + 1 # Agents z has to be adjusted as it defaults to a height 1 off where it should

    print(f"Moved onto {cube['type']}")


# Moves the agent forward off a ledge or ladder
# Used in main movement function
def fall_from_ledge(state, target_x, target_y):

    fall_target = get_fall_target(state, target_x, target_y)

    # Safety first
    if fall_target is None:
        state.kill_agent("There was no tile below the ledge")
        return

    if fall_target["type"] == "hazard" or fall_target["type"] == "death_tile":
        state.kill_agent(f"The agent landed on a {fall_target['type']}")
        return

    if fall_target["type"] == "toggleable_hazard":
        # Edge cases
        if Level.toggleable_hazards_are_safe(state):
            move_agent_to_cube(state, fall_target)
            print("Landed on disabled toggleable hazard")
        else:
            state.kill_agent("The agent landed on an active toggleable hazard")
        return

    if not can_enter_cube(state, fall_target):
        state.kill_agent(f"The agent landed on {fall_target['type']}")
        return

    move_agent_to_cube(state, fall_target)
    print("Fell from ledge safely")


# Moves the agent in an absolute direction
# Initially used turn system but this was too clunky for testing
# Also later used in logic to start at later checkpoints through teleporting
def move_in_direction(state, direction):

    dx, dy = DIRECTION_TO_VECTOR[direction]

    target_x = state.agent["x"] + dx
    target_y = state.agent["y"] + dy

    current_tile = state.cube_map.get((state.agent["x"], state.agent["y"], state.agent["z"] - 1))
    target_cube = get_cube_at_xy(state, target_x, target_y)

    # Moving into empty space
    # Trigger fall logic, if not death
    if target_cube is None:
        if current_tile is not None and current_tile["type"] in {"ledge", "ladder"}:
            fall_from_ledge(state, target_x, target_y)
        else:
            state.kill_agent("The agent stepped into empty space")
        return

    # Door logic
    if target_cube["type"] == "door":
        Level.handle_door(state, target_cube)
        return

    # Ladder logic
    if target_cube["type"] == "ladder":

        ladder_top = get_cube_at_xy(state, target_x, target_y)

        if ladder_top is None:
            print("Move blocked. Ladder finding exception")
            return

        move_agent_to_cube(state, ladder_top)
        print("Climbed ladder")
        return

    # Hazard logic
    if target_cube["type"] == "hazard" or target_cube["type"] == "death_tile":
        state.kill_agent("The agent died")
        return

    # Toggleable hazard logic
    if target_cube["type"] == "toggleable_hazard":
        if Level.toggleable_hazards_are_safe(state):
            move_agent_to_cube(state, target_cube)
            print("Crossed disabled toggleable hazard")
        else:
            state.kill_agent("The agent walked onto an active toggleable hazard")
        return

    # Prevents moving directly between white path cubes at different heights
    if not can_move_between(state, current_tile, target_cube):
        print("Move blocked. Cannot move directly between path cubes at different heights")
        return

    # Stairs logic
    if target_cube["type"] == "stairs":
        move_agent_to_cube(state, target_cube)
        print("Walked onto stairs")
        return

    # Pressure plate logic
    if target_cube["type"] == "timed_pressure_plate":
        move_agent_to_cube(state, target_cube)
        Level.activate_pressure_plate(state)
        return

    # Normal movement and checkpoint update logic
    if target_cube["type"] in WALKABLE_TYPES:
        move_agent_to_cube(state, target_cube)

        if target_cube["type"] == "checkpoint":
            old_checkpoint_cube = get_cube_at_xy(
                state,
                state.checkpoint_location[0],
                state.checkpoint_location[1]
            )

            if old_checkpoint_cube is not None:
                old_checkpoint_cube["colour"] = (238, 238, 238)
                old_checkpoint_cube["type"] = "path"

            state.set_respawn_point(state.agent["x"], state.agent["y"], state.agent["z"])
            target_cube["colour"] = (238, 0, 0)
            target_cube["type"] = "spawn"

            state.checkpoint_tracking_iterator += 1
            print("Checkpoint updated")
        return
    
    print(f"Move blocked. Target is {target_cube['type']}")


# Action for taking keys
def take_around_current_tile(state):

    for dx, dy in DIRECTION_TO_VECTOR.values():
        current_tile = state.cube_map.get((state.agent["x"] + dx, state.agent["y"] + dy, state.agent["z"]))

        if current_tile is not None and current_tile["type"] in KEY_TYPES:
            # Agent inventory is just a list of strings for now
            state.agent["inventory"].append(current_tile["type"])
            print(f"Took {current_tile['type']}")
            remove_cube(state, current_tile)
            return

    print("There is nothing to take")

# Used for ladder and ledge sensing for sense_directions
def can_safely_fall_from_current_tile(state, target_x, target_y):

    current_tile = state.cube_map.get((state.agent["x"], state.agent["y"], state.agent["z"] - 1))

    if current_tile is None: return False

    if current_tile["type"] not in {"ledge", "ladder"}: return False

    fall_target = get_fall_target(state, target_x, target_y)

    if fall_target is None: return False

    return can_enter_cube(state, fall_target)