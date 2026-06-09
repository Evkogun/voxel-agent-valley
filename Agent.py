import json
import time
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError

client = OpenAI()

DEBUG_MEMORY = True
MEMORY = 12
SPECIAL_CONTINUATION_MEMORY = 5
OBJECTIVE_WEIGHT = 2
KEY_BONUS = 10
UNLOCKED_DOOR_BONUS = 25
SPECIAL_CONTINUATION_BONUS = 15
PRESSURE_PLATE_BONUS = 30
TOGGLEABLE_HAZARD_BONUS = 35

# This is meant to speed up the prompting
# Removing these allows the systematic abstraction of the agenst observation format
SEND_GOAL_TO_AI = True
SEND_POSITION_TO_AI = True
SEND_SURROUNDINGS_TO_AI = True
SEND_INVENTORY_TO_AI = True
SEND_GOAL_INFO_TO_AI = True
SEND_VALID_ACTIONS_TO_AI = True
SEND_BRANCH_ANALYSIS_TO_AI = True
SEND_POSSIBLE_MOVES_TO_AI = True
SEND_RECENT_POSITIONS_TO_AI = False
SEND_TEXT_VISION_TO_AI = False
SEND_OTHER_TO_AI = False

VALID_ACTIONS = {
    "move_north",
    "move_west",
    "move_south",
    "move_east",
    "take"
}

recent_positions = []
visited_counts = {}

ACTION_TO_DELTA = {
    "move_north": (0, -1, 0),
    "move_east": (1, 0, 0),
    "move_south": (0, 1, 0),
    "move_west": (-1, 0, 0),
}

SAFE_TILES = {
    "path",
    "spawn",
    "checkpoint",
    "goal",
    "stairs",
    "ladder",
    "ledge",
    "timed_pressure_plate",
    "toggleable_hazard_safe",
    "safe_fall",
    "door"
}

KEY_TILES = {
    "key1",
    "key2",
}

def print_move_memory_analysis(observation):
    if not DEBUG_MEMORY:
        return

    print("")
    print("Move memory analysis")
    print(
        f"{'action':<12} "
        f"{'tile':<24} "
        f"{'recent':<7} "
        f"{'visits':<6} "
        f"{'result':<22} "
        f"{'steps':<5} "
        f"{'br_rec':<6} "
        f"{'br_len':<6} "
        f"{'score':<5}"
    )
    print("-" * 105)

    for action, move in observation["possible_moves"].items():
        branch = observation["branch_analysis"].get(action, {})
        result = branch.get("result", "unknown")
        steps = branch.get("steps", "-")

        print(
            f"{action:<12} "
            f"{str(move['target_tile']):<24} "
            f"{str(move['target_recent']):<7} "
            f"{move['target_visit_count']:<6} "
            f"{result:<22} "
            f"{str(steps):<5} "
            f"{move['branch_recent_count']:<6} "
            f"{move['branch_length']:<6} "
            f"{move['exploration_score']:<5}"
        )

    print("")


def print_final_move_memory(action, possible_moves):
    if not DEBUG_MEMORY or action not in possible_moves:
        return

    move = possible_moves[action]

    print(
        f"Final memory choice: {action} | "
        f"tile={move['target_tile']} | "
        f"recent={move['target_recent']} | "
        f"visits={move['target_visit_count']} | "
        f"branch_recent={move['branch_recent_count']} | "
        f"branch_length={move['branch_length']} | "
        f"score={move['exploration_score']}"
    )


def build_ai_observation(observation):
    ai_observation = {}
    used_keys = set()

    if SEND_POSITION_TO_AI and "position" in observation:
        ai_observation["position"] = observation["position"]
        used_keys.add("position")

    if SEND_SURROUNDINGS_TO_AI and "surroundings" in observation:
        ai_observation["surroundings"] = observation["surroundings"]
        used_keys.add("surroundings")

    if SEND_INVENTORY_TO_AI and "inventory" in observation:
        ai_observation["inventory"] = observation["inventory"]
        used_keys.add("inventory")

    if SEND_GOAL_INFO_TO_AI and "goal" in observation:
        ai_observation["goal"] = observation["goal"]
        used_keys.add("goal")

    if SEND_VALID_ACTIONS_TO_AI and "valid_actions" in observation:
        ai_observation["valid_actions"] = observation["valid_actions"]
        used_keys.add("valid_actions")

    if SEND_BRANCH_ANALYSIS_TO_AI and "branch_analysis" in observation:
        ai_observation["branch_analysis"] = observation["branch_analysis"]
        used_keys.add("branch_analysis")

    if SEND_POSSIBLE_MOVES_TO_AI and "possible_moves" in observation:
        ai_observation["possible_moves"] = observation["possible_moves"]
        used_keys.add("possible_moves")

    if SEND_RECENT_POSITIONS_TO_AI and "recent_positions" in observation:
        ai_observation["recent_positions"] = observation["recent_positions"]
        used_keys.add("recent_positions")

    if SEND_TEXT_VISION_TO_AI and "text_vision" in observation:
        ai_observation["text_vision"] = observation["text_vision"]
        used_keys.add("text_vision")

    if SEND_OTHER_TO_AI:
        for key, value in observation.items():
            if key not in used_keys and key != "text_vision":
                ai_observation[key] = value

    return ai_observation


def choose_action(observation, goal, screenshot_path=None):
    global recent_positions, visited_counts

    observation["recent_positions"] = recent_positions[-MEMORY:]

    current_position_key = (
        observation["position"]["x"],
        observation["position"]["y"],
    )

    visited_counts[current_position_key] = visited_counts.get(current_position_key, 0) + 1

    x = observation["position"]["x"]
    y = observation["position"]["y"]
    z = observation["position"]["z"]

    recent_xy_positions = {
        (pos["x"], pos["y"])
        for pos in recent_positions[-MEMORY:]
    }

    recent_special_positions = {
        (pos["x"], pos["y"])
        for pos in recent_positions[-SPECIAL_CONTINUATION_MEMORY:]
    }

    def count_recent_tiles_in_branch(branch):
        recent_count = 0

        for tile in branch.get("path_preview", []):
            tile_key = (tile["x"], tile["y"])

            if tile_key in recent_xy_positions:
                recent_count += 1

        return recent_count

    observation["possible_moves"] = {}

    for action, delta in ACTION_TO_DELTA.items():
        dx, dy, dz = delta
        direction = action.replace("move_", "")
        target_tile = observation["surroundings"].get(direction)

        target_position = {
            "x": x + dx,
            "y": y + dy,
            "z": z + dz,
        }

        target_position_key = (
            target_position["x"],
            target_position["y"],
        )

        branch = observation["branch_analysis"].get(action, {})
        branch_recent_count = count_recent_tiles_in_branch(branch)
        branch_length = len(branch.get("path_preview", []))

        branch_result = branch.get("result")
        exploration_score = 0

        for tile in branch.get("path_preview", []):
            tile_key = (tile["x"], tile["y"])

            if tile_key not in visited_counts:
                exploration_score += 1

        goal_direction = observation["goal"]["direction"]["general_direction"]
        # Meant more as a tiebreaker and to mildly steer
        if target_tile in SAFE_TILES:
            if direction == goal_direction.get("east_west"):
                exploration_score += OBJECTIVE_WEIGHT

            if direction == goal_direction.get("north_south"):
                exploration_score += OBJECTIVE_WEIGHT

            if goal_direction.get("east_west") == "west" and direction == "east":
                exploration_score -= OBJECTIVE_WEIGHT

            if goal_direction.get("east_west") == "east" and direction == "west":
                exploration_score -= OBJECTIVE_WEIGHT

            if goal_direction.get("north_south") == "north" and direction == "south":
                exploration_score -= OBJECTIVE_WEIGHT

            if goal_direction.get("north_south") == "south" and direction == "north":
                exploration_score -= OBJECTIVE_WEIGHT

        if branch_result == "key":
            exploration_score += KEY_BONUS

        if branch_result == "door":
            exploration_score += UNLOCKED_DOOR_BONUS

        if branch_result == "special_continuation":
            exploration_score += SPECIAL_CONTINUATION_BONUS

        if branch_result == "pressure_plate":
            exploration_score += PRESSURE_PLATE_BONUS

        if branch_result == "needs_pressure_plate":
            exploration_score -= 5

        if target_tile == "toggleable_hazard_safe":
            exploration_score += TOGGLEABLE_HAZARD_BONUS

        if branch_result in {"unsafe", "blocked", "empty"}:
            exploration_score = -999

        if branch_result == "dead_end":
            exploration_score -= 10

        if branch_result == "special_continuation" and target_position_key in recent_special_positions:
            exploration_score -= 10

        observation["possible_moves"][action] = {
            "direction": direction,
            "target_position": target_position,
            "target_tile": target_tile,
            "target_visit_count": visited_counts.get(target_position_key, 0),
            "target_recent": target_position_key in recent_xy_positions,
            "branch_recent_count": branch_recent_count,
            "branch_length": branch_length,
            "branch_result": branch_result,
            "exploration_score": exploration_score,
        }

    print_move_memory_analysis(observation)

    ai_observation = build_ai_observation(observation)
    goal_for_ai = goal if SEND_GOAL_TO_AI else "Not sent"

    prompt = f"""
You are an agent in a small voxel world.

Goal:
{goal_for_ai}

Observation:
{json.dumps(ai_observation)}

Choose exactly one action:
move_north, move_east, move_south, move_west, take.

Action mapping:
move_north -> surroundings.north
move_east -> surroundings.east
move_south -> surroundings.south
move_west -> surroundings.west

Rules:
1. Safety is absolute.
2. Only move into: path, spawn, checkpoint, goal, stairs, ladder, ledge, safe_fall, timed_pressure_plate, toggleable_hazard_safe, door.
3. Never move into: death_tile, hazard, empty, toggleable_hazard_active, door_blocked, unknown.
4. If an adjacent tile is goal, move into it.
5. Else if an adjacent tile is checkpoint, move into it.
6. Use observation.branch_analysis as the main navigation guide.
Prefer branch results in this order:
goal, checkpoint, key, door, pressure_plate, toggleable_hazard_safe, safe non-recent moves, special_continuation, junction, scan_limit_reached, then lowest target_visit_count.
8. A move with target_recent true is usually backtracking.
9. Do not choose a target_recent move if there is another safe move with target_recent false.
10. special_continuation does not override target_recent.
11. Avoid branch results: dead_end, empty, blocked, unsafe unless no better safe branch exists.
12. Stairs, ladders, and ledges are useful only when they lead to new progress. If recently visited and another safe route exists, avoid them.
13. goal.direction is only a hint, not a command.
14. It is allowed to temporarily increase goal distance to avoid a dead end or return to a junction.
15. safe_fall means the adjacent space is empty, but the current ladder or ledge allows a controlled safe fall. Treat safe_fall as a valid special_continuation.

Pressure plate and toggleable hazard rules:
1. timed_pressure_plate activates toggleable hazards temporarily.
2. If a branch reaches pressure_plate, strongly prefer it unless a goal, checkpoint, key, or door is clearly better.
3. If a branch reaches needs_pressure_plate, avoid trying to cross that branch until a pressure plate has been activated.
4. If an adjacent tile is toggleable_hazard_safe, crossing it is valuable and should be prioritised.
5. Never move onto toggleable_hazard_active.

Memory and branch rules:
1. Use possible_moves[action].branch_recent_count to detect loops.
2. Prefer branches with fewer recent tiles.
3. exploration_score means how much of the branch seems new.
4. When no goal or checkpoint is visible, prefer the safe branch with the highest exploration_score.
5. If a branch has many recent tiles, treat it as already explored unless it reaches a goal, checkpoint, key, door, pressure_plate, or necessary special continuation.
6. Do not choose a special_continuation branch if it mostly revisits recent tiles and another safe branch is newer.

Key and door rules:
1. If any adjacent tile is key1 or key2, choose take immediately.
2. Branches that reach keys are valuable and should be prioritised.
3. Avoid door_blocked; it means the agent is missing the required key or keys.
4. door means the agent has all required keys, so it is very valuable and should be prioritised highly.
5. Moving into a door may open it rather than moving through it immediately.

Backtracking and junction rules:
1. Do not prefer a branch just because it reaches a junction in fewer steps.
2. A junction after 1 step is only bad if that move returns to a recent position.
3. If the 1-step junction is not in recent_positions, it is a valid forward move.
4. Never choose a recent-position move just because its branch has more steps.
5. Treat a 1-step junction as backtracking if its target position is in recent_positions.
6. Prefer a branch that reaches a new or further junction over a branch that immediately returns to a recent junction.
7. If two branches both lead to junctions, prefer the one with lower target_visit_count unless it is clearly just backtracking.
8. If a branch is dead_end, do not choose it while another safe branch reaches a junction, checkpoint, goal, stairs, ladder, ledge, pressure_plate, door, or scan_limit_reached.

Direction sanity:
- north decreases y.
- south increases y.
- east increases x.
- west decreases x.
- Never claim north helps with a south target.
- Never claim west helps with an east target.

Return JSON only in this exact format:
{{
    "safe_actions": ["move_north", "move_east"],
    "unsafe_actions": ["move_south", "move_west"],
    "action": "move_north",
    "chosen_direction": "north",
    "chosen_tile": "path",
    "reason": "brief reason using surroundings, branch_analysis, target_visit_count, target_recent, branch_recent_count, exploration_score, and whether the move is backtracking"
}}

Final check:
- action must be in safe_actions unless action is take.
- chosen_tile must match surroundings[chosen_direction].
- never choose an unsafe tile.
- do not choose a dead_end branch if there is a safe junction, checkpoint, goal, stairs, ladder, ledge, pressure_plate, door, or scan_limit_reached branch.
- do not choose a one-step junction backtrack if there is another safe branch leading to a further junction.
- if the chosen action has possible_moves[action].target_recent true and another safe action has target_recent false, choose the non-recent action instead.
- do not choose recently visited stairs, ladders, or ledges unless every other safe action is worse or unsafe.
- if two safe branches are otherwise similar, choose the one with the higher exploration_score.
"""

    content = [{"type": "input_text", "text": prompt}]

    start_time = time.perf_counter()

    # Crashing led to me implementing API safety
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            temperature=0,
            timeout=20,
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )
        decision_time = time.perf_counter() - start_time
        print(f"AI decision request took {decision_time:.2f}s")
        raw = response.output_text.strip()
    except APITimeoutError:
        decision_time = time.perf_counter() - start_time
        print(f"OpenAI API timed out after {decision_time:.2f}s")
        return None

    except APIConnectionError as error:
        decision_time = time.perf_counter() - start_time
        print(f"OpenAI API connection error after {decision_time:.2f}s: {error}")
        return None

    except RateLimitError as error:
        decision_time = time.perf_counter() - start_time
        print(f"OpenAI API rate limit after {decision_time:.2f}s: {error}")
        return None

    except APIError as error:
        decision_time = time.perf_counter() - start_time
        print(f"OpenAI API error after {decision_time:.2f}s: {error}")
        return None

    except Exception as error:
        decision_time = time.perf_counter() - start_time
        print(f"Unexpected AI error after {decision_time:.2f}s: {error}")
        return None

    try:
        decision = extract_json(raw)
    except json.JSONDecodeError:
        print(f"Bad AI response: {raw!r}")
        return None
    action = decision.get("action")

    possible_moves = observation.get("possible_moves", {})
    branch_analysis = observation.get("branch_analysis", {})

    chosen_move = possible_moves.get(action, {})
    chosen_recent = chosen_move.get("target_recent", False)
    chosen_score = chosen_move.get("exploration_score", 0)
    chosen_branch = branch_analysis.get(action, {})
    chosen_result = chosen_branch.get("result")

    if chosen_recent or chosen_score <= 0:
        best_alternative_action = None
        best_alternative_score = -1

        for alternative_action, alternative_move in possible_moves.items():
            alternative_tile = alternative_move.get("target_tile")
            alternative_recent = alternative_move.get("target_recent", False)
            alternative_score = alternative_move.get("exploration_score", 0)
            alternative_branch = branch_analysis.get(alternative_action, {})
            alternative_result = alternative_branch.get("result")

            if alternative_tile not in SAFE_TILES:
                continue

            if alternative_recent:
                continue

            if alternative_result in {"unsafe", "blocked", "empty", "dead_end"}:
                continue

            if alternative_score > best_alternative_score:
                best_alternative_action = alternative_action
                best_alternative_score = alternative_score

        if best_alternative_action is not None and chosen_result not in {"goal", "checkpoint"}:
            print(f"Prevented recent/low-exploration loop. Overriding {action} with {best_alternative_action}")
            action = best_alternative_action

    chosen_tile = decision.get("chosen_tile", "")
    reason = decision.get("reason", "")

    if action in possible_moves:
        chosen_tile = possible_moves[action].get("target_tile", chosen_tile)

    print_final_move_memory(action, possible_moves)

    print(f"AI chosen tile: {chosen_tile}")
    print(f"AI reason: {reason}")
    print(f"AI action: {action}")

    if action not in observation["valid_actions"]:
        print(f"Invalid AI action: {action}")
        return observation["valid_actions"][0]

    recent_positions.append(observation["position"])

    return action


def extract_json(raw):
    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        raise json.JSONDecodeError("No JSON object found", raw, 0)

    return json.loads(raw[start:end + 1])