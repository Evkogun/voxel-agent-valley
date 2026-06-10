from collections import deque
from Config import *
from level import Movement
from level import Level
from ai import Sense

last_agent_position = None
previous_agent_position = None

# Finds nearby reachable tiles from a simulated position
# Similar to get_safe_directions_from_position but with different returns
# Used by analyse_action_with_bfs to explore routes beyond a single branch
def get_bfs_neighbours(state, x, y, standing_z):

    neighbours = []
    current_cube = state.cube_map.get((x, y, standing_z - 1))
    # For the edge case where an agent is standing on top of a ladder and needs to detect a way down
    if current_cube is not None and current_cube["type"] == "ladder":
        lower_cube = state.cube_map.get((x, y, standing_z - 2))

        if lower_cube is not None and lower_cube["type"] == "ladder":
            neighbours.append({
                "direction": "down",
                "tile": "ladder",
                "position": {
                    "x": x,
                    "y": y,
                    "z": lower_cube["z"] + 1,
                },
                "cube": lower_cube,
            })

        elif lower_cube is not None and Movement.can_enter_cube(state, lower_cube):
            neighbours.append({
                "direction": "down",
                "tile": Sense.get_scan_tile_type(state, lower_cube),
                "position": {
                    "x": x,
                    "y": y,
                    "z": lower_cube["z"] + 1,
                },
                "cube": lower_cube,
            })

    for direction, delta in DIRECTION_TO_VECTOR.items():

        if direction == "stay": continue # Don't want to treat own tile as neighbor

        dx, dy = delta
        target_x = x + dx
        target_y = y + dy

        target_cube = Movement.get_cube_at_xy(state, target_x, target_y, standing_z = standing_z)
        target_type = Sense.get_scan_tile_type(state, target_cube)

        if target_cube is None:
            if current_cube is not None and current_cube["type"] in {"ledge", "ladder"}:
                fall_target = Movement.get_fall_target(state, target_x, target_y, standing_z)
                # Handle ledges and tops of ladders as they are tecnically "None"
                if fall_target is not None and Movement.can_enter_cube(state, fall_target):
                    neighbours.append({
                        "direction": direction,
                        "tile": "safe_fall",
                        "position": {
                            "x": target_x,
                            "y": target_y,
                            "z": fall_target["z"] + 1,
                        },
                        "cube": fall_target,
                    })
            continue

        can_move = Movement.can_move_between(state, current_cube, target_cube)
        if target_type == "door": can_move = True
        if target_type == "toggleable_hazard_safe": can_move = True

        if can_move:
            neighbours.append({
                "direction": direction,
                "tile": target_type,
                "position": {
                    "x": target_x,
                    "y": target_y,
                    "z": target_cube["z"] + 1,
                },
                "cube": target_cube,
            })

    return neighbours

# Scores useful tiles found by bfs
# Used by analyse_action_with_bfs to decide what the best reachable result is
def get_bfs_result_priority(tile_type):
    # Seperate to agent values
    if tile_type == "goal": return 100
    if tile_type == "checkpoint": return 90
    if tile_type in KEY_TYPES: return 80
    if tile_type == "door": return 70
    if tile_type == "timed_pressure_plate": return 60
    if tile_type == "toggleable_hazard_safe": return 50
    if tile_type == "safe_fall": return 40
    if tile_type in SPECIAL_CONTINUATION_TYPES: return 10
    if tile_type in WALKABLE_TYPES: return 10
    if tile_type == "scan_limit_reached": return 5 # open path should be higher than dead end
    if tile_type == "dead_end": return -10
    if tile_type == "door_blocked": return -30
    return 0

# Converts some specific tile names to more general result names for the AI
def get_bfs_result_name(tile_type):
    if tile_type in KEY_TYPES:
        return "key"
    return tile_type

# Stores useful things seen during bfs without adding duplicates
# In analyse_action_with_bfs so the AI can see more than just the single best result
def add_bfs_finding(findings, tile_type, steps, path):

    priority = get_bfs_result_priority(tile_type)
    if priority <= 10: return
    result = get_bfs_result_name(tile_type)

    for finding in findings:
        if finding["result"] == result:
            if steps < finding["steps"]:
                finding["steps"] = steps
                finding["path_preview"] = path
            return

    findings.append({
        "result": result,
        "tile": tile_type,
        "priority": priority,
        "steps": steps,
        "path_preview": path,
    })

# Checks if a BFS position is next to a key that can be taken
# Similar to helper in BranchScan, very inefficient
def get_reachable_key_from_position(state, x, y, standing_z):
    for direction, delta in DIRECTION_TO_VECTOR.items():
        if direction == "stay": continue

        dx, dy = delta

        # Keys may be stored at standing height or tile height depending on your voxel setup
        key_cube = state.cube_map.get((x + dx, y + dy, standing_z))

        if key_cube is None:
            key_cube = state.cube_map.get((x + dx, y + dy, standing_z - 1))

        if key_cube is not None and key_cube["type"] in KEY_TYPES:
            return key_cube

    return None

# Looks at all reachable tiles after taking one action and returns best result
# Used by get_bfs_analysis to give the AI deeper route information than branch_analysis
def analyse_action_with_bfs(state, action, depth_limit=32): # Max distance between checkpoint and relevent objective
    # Action to direction conversion
    direction = MOVE_ACTION_TO_DIRECTION[action]
    dx, dy = DIRECTION_TO_VECTOR[direction]

    start_x = state.agent["x"] + dx
    start_y = state.agent["y"] + dy

    current_cube = state.cube_map.get((state.agent["x"], state.agent["y"], state.agent["z"] - 1))
    start_cube = Movement.get_cube_at_xy(state, start_x, start_y, standing_z = state.agent["z"])
    start_type = Sense.get_scan_tile_type(state, start_cube)

    if start_cube is None:
        # Also check for ladders
        if current_cube is not None and current_cube["type"] in {"ledge", "ladder"}:
            fall_target = Movement.get_fall_target(state, start_x, start_y)

            if fall_target is not None and Movement.can_enter_cube(state, fall_target):
                start_cube = fall_target
                start_type = "safe_fall"
            else:
                return {
                    "safe": False,
                    "result": "empty",
                    "tile": start_type,
                    "reason": "initial tile is empty",
                }
        else:
            return {
                "safe": False,
                "result": "empty",
                "tile": start_type,
                "reason": "initial tile is empty",
            }

    can_start = Movement.can_move_between(state, current_cube, start_cube)
    if start_type == "door": can_start = True # Old function doesn't have cases for door/hazard
    if start_type == "toggleable_hazard_safe": can_start = True

    if not can_start:
        return {
            "safe": False,
            "result": "blocked",
            "tile": start_type,
            "reason": f"initial move is blocked by {start_type}",
        }

    # Generic BFS setup
    start_position = (start_cube["x"], start_cube["y"], start_cube["z"] + 1)
    current_position = (state.agent["x"], state.agent["y"], state.agent["z"])
    if previous_agent_position is not None and start_position == previous_agent_position:
        return {
            "safe": False,
            "result": "backtrack",
            "tile": start_type,
            "reason": "initial move goes back to previous tile",
        }
    
    queue = deque()
    visited = set() # Prevents duplication

    queue.append((
        start_position, 1,
        [
            {
                "x": start_cube["x"],
                "y": start_cube["y"],
                "z": start_cube["z"] + 1,
                "tile": start_type,
            }
        ]
    ))

    visited.add(start_position)
    visited.add(current_position) # Prevents the ai backtracking through current tiles

    best_result = start_type
    best_priority = get_bfs_result_priority(start_type)
    best_steps = 1
    best_path = [
        {
            "x": start_cube["x"],
            "y": start_cube["y"],
            "z": start_cube["z"] + 1,
            "tile": start_type,
        }
    ]

    findings = []
    add_bfs_finding(findings, start_type, 1, best_path)

    hit_depth_limit = False

    while queue:

        position, steps, path = queue.popleft()

        x, y, standing_z = position
        current_cube = state.cube_map.get((x, y, standing_z - 1))
        current_type = Sense.get_scan_tile_type(state, current_cube)

        reachable_key = get_reachable_key_from_position(state, x, y, standing_z)

        if reachable_key is not None:
            key_type = reachable_key["type"]
            key_priority = get_bfs_result_priority(key_type)

            add_bfs_finding(findings, key_type, steps, path)

            if key_priority > best_priority:
                best_result = key_type
                best_priority = key_priority
                best_steps = steps
                best_path = path

        current_priority = get_bfs_result_priority(current_type)
        add_bfs_finding(findings, current_type, steps, path)

        if current_priority > best_priority:
            best_result = current_type
            best_priority = current_priority
            best_steps = steps
            best_path = path

        if current_type in {"goal", "checkpoint"}: break

        if steps >= depth_limit:
            hit_depth_limit = True
            continue

        neighbours = get_bfs_neighbours(state, x, y, standing_z)

        for neighbour in neighbours:
            next_position = (
                neighbour["position"]["x"],
                neighbour["position"]["y"],
                neighbour["position"]["z"],
            )

            if next_position in visited: continue
            visited.add(next_position)

            queue.append((
                next_position,
                steps + 1,
                path + [
                    {
                        "x": neighbour["position"]["x"],
                        "y": neighbour["position"]["y"],
                        "z": neighbour["position"]["z"],
                        "tile": neighbour["tile"],
                    }
                ]
            ))

    if best_priority <= 10:
        if hit_depth_limit:
            result = "scan_limit_reached"
        else:
            result = "dead_end"
    else:
        result = get_bfs_result_name(best_result)

    findings.sort(key=lambda finding: finding["priority"], reverse=True)

    return {
        "safe": True,
        "result": result,
        "steps": best_steps,
        "reachable_tiles": len(visited),
        "findings": findings[:3],
        "path_preview": best_path,
        "reason": f"{action} can reach {result} within bfs depth",
    }

# Builds bfs route analysis for each movement action
# Used by Vision.get_observations to give the AI deeper route context
# This returns the best result in each direction and up to 3 useful findings
def get_bfs_analysis(state):
    global last_agent_position, previous_agent_position

    current_position = (
        state.agent["x"],
        state.agent["y"],
        state.agent["z"],
    )

    if last_agent_position is None:
        last_agent_position = current_position

    elif current_position != last_agent_position:
        previous_agent_position = last_agent_position
        last_agent_position = current_position

    bfs_analysis = {}

    for action in MOVE_ACTION_TO_DIRECTION:
        bfs_analysis[action] = analyse_action_with_bfs(state, action)

    return bfs_analysis