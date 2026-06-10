from Config import *
from level import Movement
from level import Level
from ai import Sense

# Finds which directions are safe from a scanned position rather than the agent position
# Mostly mentioned inside scan_branch to detect dead ends and junctions
def get_safe_directions_from_position(state, x, y, current_cube):

    safe_directions = []

    for direction, delta in DIRECTION_TO_VECTOR.items():
        
        if direction == "stay": continue

        dx, dy = delta
        target_x = x + dx
        target_y = y + dy

        target_cube = Movement.get_cube_at_xy(state, target_x, target_y)
        target_type = Sense.get_scan_tile_type(state, target_cube)

        if target_cube is None: continue

        can_move = Movement.can_move_between(state, current_cube, target_cube)

        if target_type == "door": can_move = True

        if can_move:
            safe_directions.append({
                "direction": direction,
                "tile": target_type,
                "position": {
                    "x": target_x,
                    "y": target_y,
                    "z": target_cube["z"] + 1,
                },
            })

    return safe_directions

# Checks if a path tile leads to a key that can be taken from that position
def get_reachable_key_from_position(state, x, y, standing_z):

    for dx, dy in DIRECTION_TO_VECTOR.values():
        key_cube = state.cube_map.get((x + dx, y + dy, standing_z))

        if key_cube is not None and key_cube["type"] in KEY_TYPES:
            return key_cube
    return None


# Looks ahead down one branch to classify whether it reaches a key, checkpoint, goal, door, junction or dead end
# Used by branch analysis for AI observations
def scan_branch(state, start_direction):

    dx, dy = DIRECTION_TO_VECTOR[start_direction]

    current_x = state.agent["x"]
    current_y = state.agent["y"]
    previous_x = state.agent["x"]
    previous_y = state.agent["y"]
    previous_cube = state.cube_map.get((state.agent["x"], state.agent["y"], state.agent["z"] - 1))
    path = []

    for step in range(1, BRANCH_SCAN_LIMIT + 1):

        current_x += dx
        current_y += dy
        current_cube = Movement.get_cube_at_xy(state, current_x, current_y)
        current_type = Sense.get_scan_tile_type(state, current_cube)

        path.append({"x": current_x, "y": current_y, "tile": current_type})

        if current_cube is None:
            return {
                "start_direction": start_direction,
                "result": "empty",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches empty space",
            }

        if current_type in KEY_TYPES:
            return {
                "start_direction": start_direction,
                "result": "key",
                "key_type": current_type,
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": f"branch reaches {current_type}",
            }
        
        if current_type == "timed_pressure_plate":
            return {
                "start_direction": start_direction,
                "result": "pressure_plate",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches a timed pressure plate",
            }
        
        if current_type == "toggleable_hazard_active":
            return {
                "start_direction": start_direction,
                "result": "needs_pressure_plate",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches an active toggleable hazard, so a pressure plate is needed",
            }

        reachable_key = get_reachable_key_from_position(
            state,
            current_x,
            current_y,
            current_cube["z"] + 1
        )

        if reachable_key is not None:
            return {
                "start_direction": start_direction,
                "result": "key",
                "key_type": reachable_key["type"],
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "key_position": {
                    "x": reachable_key["x"],
                    "y": reachable_key["y"],
                    "z": reachable_key["z"],
                },
                "path_preview": path,
                "reason": f"branch reaches a path tile next to {reachable_key['type']}",
            }

        if current_type == "door_blocked":
            return {
                "start_direction": start_direction,
                "result": "blocked",
                "blocked_by": current_type,
                "required_keys": Level.get_door_required_keys(state, current_cube),
                "missing_keys": Level.get_missing_door_keys(state, current_cube),
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches a door but the agent is missing required keys",
            }

        if current_type == "door":
            return {
                "start_direction": start_direction,
                "result": "door",
                "required_keys": Level.get_door_required_keys(state, current_cube),
                "missing_keys": [],
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches a door and the agent has all required keys",
            }

        if not Movement.can_move_between(state, previous_cube, current_cube):
            return {
                "start_direction": start_direction,
                "result": "blocked",
                "blocked_by": current_type,
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": f"branch is blocked by {current_type} or invalid height change",
            }

        if current_type == "checkpoint":
            return {
                "start_direction": start_direction,
                "result": "checkpoint",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches a checkpoint",
            }

        if current_type == "goal":
            return {
                "start_direction": start_direction,
                "result": "goal",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch reaches the goal",
            }

        if current_type in SPECIAL_CONTINUATION_TYPES:
            return {
                "start_direction": start_direction,
                "result": "special_continuation",
                "special_tile": current_type,
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": f"branch reaches {current_type}, which is a valid continuation",
            }

        safe_directions = get_safe_directions_from_position(state, current_x, current_y, current_cube)
        onward_directions = []

        for safe_direction in safe_directions:
            target_position = safe_direction["position"]

            if target_position["x"] == previous_x and target_position["y"] == previous_y: continue

            onward_directions.append(safe_direction)

        if len(onward_directions) == 0:
            return {
                "start_direction": start_direction,
                "result": "dead_end",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "path_preview": path,
                "reason": "branch has no safe onward moves",
            }

        if len(onward_directions) >= 2:
            return {
                "start_direction": start_direction,
                "result": "junction",
                "steps": step,
                "end_position": {"x": current_x, "y": current_y},
                "onward_directions": onward_directions,
                "path_preview": path,
                "reason": "branch reaches another junction",
            }

        next_direction = onward_directions[0]["direction"]
        dx, dy = DIRECTION_TO_VECTOR[next_direction]

        previous_x = current_x
        previous_y = current_y
        previous_cube = current_cube

    return {
        "start_direction": start_direction,
        "result": "scan_limit_reached",
        "steps": BRANCH_SCAN_LIMIT,
        "end_position": {"x": current_x, "y": current_y},
        "path_preview": path,
        "reason": "branch continued beyond scan limit",
    }

# Builds branch analysis for each movement action
# Used by Vision.get_observations to give the AI short lookahead context
def get_branch_analysis(state):

    branch_analysis = {}

    for action, direction in MOVE_ACTION_TO_DIRECTION.items():
        tile_type = Sense.sense_direction(state, direction)
        if tile_type == "safe_fall":
            dx, dy = DIRECTION_TO_VECTOR[direction]

            branch_analysis[action] = {
                "start_direction": direction,
                "result": "special_continuation",
                "tile": tile_type,
                "steps": 1,
                "end_position": {
                    "x": state.agent["x"] + dx,
                    "y": state.agent["y"] + dy,
                },
                "path_preview": [
                    {
                        "x": state.agent["x"] + dx,
                        "y": state.agent["y"] + dy,
                        "tile": "safe_fall",
                    }
                ],
                "reason": f"{direction} is a safe fall from the current ladder or ledge",
            }
            continue
        if tile_type in KEY_TYPES:
            dx, dy = DIRECTION_TO_VECTOR[direction]

            branch_analysis[action] = {
                "start_direction": direction,
                "result": "take_key_immediately",
                "tile": tile_type,
                "key_type": tile_type,
                "recommended_action": "take",
                "steps": 0,
                "end_position": {
                    "x": state.agent["x"],
                    "y": state.agent["y"],
                },
                "key_position": {
                    "x": state.agent["x"] + dx,
                    "y": state.agent["y"] + dy,
                    "z": state.agent["z"],
                },
                "path_preview": [
                    {
                        "x": state.agent["x"] + dx,
                        "y": state.agent["y"] + dy,
                        "tile": tile_type,
                    }
                ],
                "reason": f"{direction} has adjacent {tile_type}; choose take immediately, do not move",
            }
            continue

        if tile_type == "door_blocked":
            dx, dy = DIRECTION_TO_VECTOR[direction]
            door_cube = Movement.get_cube_at_xy(state, state.agent["x"] + dx, state.agent["y"] + dy)

            branch_analysis[action] = {
                "start_direction": direction,
                "result": "blocked",
                "tile": tile_type,
                "required_keys": Level.get_door_required_keys(state, door_cube),
                "missing_keys": Level.get_missing_door_keys(state, door_cube),
                "steps": 1,
                "reason": f"{direction} has a door but the agent is missing required keys",
            }
            continue

        if tile_type == "door":
            dx, dy = DIRECTION_TO_VECTOR[direction]
            door_cube = Movement.get_cube_at_xy(state, state.agent["x"] + dx, state.agent["y"] + dy)

            branch_analysis[action] = {
                "start_direction": direction,
                "result": "door",
                "tile": tile_type,
                "required_keys": Level.get_door_required_keys(state, door_cube),
                "missing_keys": [],
                "steps": 1,
                "end_position": {
                    "x": state.agent["x"] + dx,
                    "y": state.agent["y"] + dy,
                },
                "path_preview": [
                    {
                        "x": state.agent["x"] + dx,
                        "y": state.agent["y"] + dy,
                        "tile": tile_type,
                    }
                ],
                "reason": f"{direction} has a door and the agent has all required keys",
            }
            continue

        if tile_type not in WALKABLE_TYPES and tile_type != "toggleable_hazard_safe":
            branch_analysis[action] = {
                "start_direction": direction,
                "result": "unsafe",
                "tile": tile_type,
                "reason": f"cannot start branch because {direction} is {tile_type}",
            }
            continue

        branch_analysis[action] = scan_branch(state, direction)

    return branch_analysis