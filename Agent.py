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

SEND_GOAL_TO_AI = True
SEND_VALID_ACTIONS_TO_AI = True
SEND_POSITION_TO_AI = False
SEND_SURROUNDINGS_TO_AI = True
SEND_INVENTORY_TO_AI = False
SEND_GOAL_INFO_TO_AI = False
SEND_TEXT_VISION_TO_AI = False
SEND_BRANCH_ANALYSIS_TO_AI = False
SEND_POSSIBLE_MOVES_TO_AI = False
SEND_RECENT_POSITIONS_TO_AI = False
SEND_BFS_ANALYSIS_TO_AI = False
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

def set_observation_level_flags(observation_tier):
    global SEND_GOAL_TO_AI
    global SEND_VALID_ACTIONS_TO_AI
    global SEND_POSITION_TO_AI
    global SEND_SURROUNDINGS_TO_AI
    global SEND_INVENTORY_TO_AI
    global SEND_GOAL_INFO_TO_AI
    global SEND_TEXT_VISION_TO_AI
    global SEND_BRANCH_ANALYSIS_TO_AI
    global SEND_POSSIBLE_MOVES_TO_AI
    global SEND_RECENT_POSITIONS_TO_AI
    global SEND_BFS_ANALYSIS_TO_AI
    global SEND_OTHER_TO_AI

    # Reset everything first
    SEND_GOAL_TO_AI = True
    SEND_VALID_ACTIONS_TO_AI = True

    SEND_POSITION_TO_AI = False
    SEND_SURROUNDINGS_TO_AI = False
    SEND_INVENTORY_TO_AI = False
    SEND_GOAL_INFO_TO_AI = False

    SEND_TEXT_VISION_TO_AI = False

    SEND_BRANCH_ANALYSIS_TO_AI = False
    SEND_POSSIBLE_MOVES_TO_AI = False
    SEND_RECENT_POSITIONS_TO_AI = False

    SEND_BFS_ANALYSIS_TO_AI = False

    SEND_OTHER_TO_AI = False

    # Tier 0: task and action basics
    if observation_tier == 0:
        SEND_SURROUNDINGS_TO_AI = True
        return

    # Tier 1: immediate agent state
    if observation_tier == 1:
        SEND_POSITION_TO_AI = True
        SEND_SURROUNDINGS_TO_AI = True
        SEND_INVENTORY_TO_AI = True
        SEND_GOAL_INFO_TO_AI = True
        return

    # Tier 2: local symbolic map only
    if observation_tier == 2:
        SEND_INVENTORY_TO_AI = True
        SEND_GOAL_INFO_TO_AI = True
        SEND_TEXT_VISION_TO_AI = True
        return

    # Tier 3: branch/memory only
    if observation_tier == 3:
        SEND_INVENTORY_TO_AI = True
        SEND_GOAL_INFO_TO_AI = True
        SEND_BRANCH_ANALYSIS_TO_AI = True
        SEND_POSSIBLE_MOVES_TO_AI = True
        SEND_RECENT_POSITIONS_TO_AI = True
        return

    # Tier 4: BFS only
    if observation_tier == 4:
        SEND_INVENTORY_TO_AI = True
        SEND_GOAL_INFO_TO_AI = True
        SEND_BFS_ANALYSIS_TO_AI = True
        return

def print_move_memory_analysis(observation):
    if not DEBUG_MEMORY:
        return

    if not SEND_POSSIBLE_MOVES_TO_AI:
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
        if SEND_BRANCH_ANALYSIS_TO_AI:
            branch = observation.get("branch_analysis", {}).get(action, {})
            result = branch.get("result", "unknown")
            steps = branch.get("steps", "-")
        else:
            result = "-"
            steps = "-"

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
    if not DEBUG_MEMORY or not SEND_POSSIBLE_MOVES_TO_AI or action not in possible_moves:
        return

    move = possible_moves[action]

    print(
        f"Final memory choice: {action} | "
        f"tile = {move['target_tile']} | "
        f"recent = {move['target_recent']} | "
        f"visits = {move['target_visit_count']} | "
        f"branch_recent = {move['branch_recent_count']} | "
        f"branch_length = {move['branch_length']} | "
        f"score = {move['exploration_score']}"
    )

def print_bfs_analysis(observation):
    if not DEBUG_MEMORY: return
    if not SEND_BFS_ANALYSIS_TO_AI: return
    if "bfs_analysis" not in observation: return

    print("")
    print("BFS analysis")
    print(
        f"{'action':<12} "
        f"{'safe':<6} "
        f"{'result':<22} "
        f"{'steps':<5} "
        f"{'tiles':<6} "
        f"{'findings':<40}"
    )
    print("-" * 95)

    for action, analysis in observation.get("bfs_analysis", {}).items():
        findings_text = ""

        for finding in analysis.get("findings", []):
            findings_text += f"{finding['result']} ({finding['steps']}), "

        findings_text = findings_text.rstrip(", ")

        print(
            f"{action:<12} "
            f"{str(analysis.get('safe', '-')):<6} "
            f"{str(analysis.get('result', '-')):<22} "
            f"{str(analysis.get('steps', '-')):<5} "
            f"{str(analysis.get('reachable_tiles', '-')):<6} "
            f"{findings_text:<40}"
        )

    print("")

def get_take_analysis(observation):
    for direction, tile in observation.get("surroundings", {}).items():
        if tile in KEY_TILES:
            return {
                "available": True,
                "target": tile,
                "direction": direction,
                "recommended_action": "take",
                "reason": f"{tile} is adjacent at surroundings.{direction}, so choose take instead of moving"
            }

    return {
        "available": False
    }

def build_ai_observation(observation, observation_tier):
    ai_observation = {}

    if SEND_POSITION_TO_AI and "position" in observation:
        ai_observation["position"] = observation["position"]

    if SEND_SURROUNDINGS_TO_AI and "surroundings" in observation:
        ai_observation["surroundings"] = observation["surroundings"]

    if SEND_INVENTORY_TO_AI and "inventory" in observation:
        ai_observation["inventory"] = observation["inventory"]

    if SEND_GOAL_INFO_TO_AI and "goal" in observation:
        ai_observation["goal"] = observation["goal"]

    if SEND_VALID_ACTIONS_TO_AI and "valid_actions" in observation:
        ai_observation["valid_actions"] = observation["valid_actions"]

    if "take_analysis" in observation:
        ai_observation["take_analysis"] = observation["take_analysis"]

    if SEND_TEXT_VISION_TO_AI and "text_vision" in observation:
        ai_observation["text_vision"] = observation["text_vision"]

    if SEND_BRANCH_ANALYSIS_TO_AI and "branch_analysis" in observation:
        ai_observation["branch_analysis"] = observation["branch_analysis"]

    if SEND_POSSIBLE_MOVES_TO_AI and "possible_moves" in observation:
        ai_observation["possible_moves"] = observation["possible_moves"]

    if SEND_RECENT_POSITIONS_TO_AI and "recent_positions" in observation:
        ai_observation["recent_positions"] = observation["recent_positions"]

    if SEND_BFS_ANALYSIS_TO_AI and "bfs_analysis" in observation:
        ai_observation["bfs_analysis"] = observation["bfs_analysis"]

    if SEND_OTHER_TO_AI:
        for key in ["alive", "goal_reached"]:
            if key in observation:
                ai_observation[key] = observation[key]

    return ai_observation


def choose_action(observation, goal, screenshot_path=None, observation_tier=4):
    global recent_positions, visited_counts
    
    set_observation_level_flags(observation_tier)

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

        branch = observation.get("branch_analysis", {}).get(action, {})
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

    observation["take_analysis"] = get_take_analysis(observation)

    if SEND_POSSIBLE_MOVES_TO_AI:
        print_move_memory_analysis(observation)

    if SEND_BFS_ANALYSIS_TO_AI:
        print_bfs_analysis(observation)

    ai_observation = build_ai_observation(observation, observation_tier)
    goal_for_ai = goal if SEND_GOAL_TO_AI else "Not sent"

    prompt = f"""
        You are an agent in a small voxel world.

        Observation tier:
        {observation_tier}

        Goal:
        {goal_for_ai}

        Observation:
        {json.dumps(ai_observation)}

        {get_base_prompt_rules()}

        {get_tier_prompt_rules(observation_tier)}
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

    if SEND_POSSIBLE_MOVES_TO_AI and (chosen_recent or chosen_score <= 0):
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

def get_base_prompt_rules():
    return """
        Choose exactly one action:
        move_north, move_east, move_south, move_west, take.

        Action mapping:
        move_north -> surroundings.north
        move_east -> surroundings.east
        move_south -> surroundings.south
        move_west -> surroundings.west

        Universal rules:
        1. Safety is absolute.
        2. Only move into: path, spawn, checkpoint, goal, stairs, ladder, ledge, safe_fall, timed_pressure_plate, toggleable_hazard_safe, door.
        3. Never move into: death_tile, hazard, empty, toggleable_hazard_active, door_blocked, unknown.
        4. If observation.take_analysis.available is true, choose action "take".
        5. take is not a movement action. Do not choose move_north, move_east, move_south, or move_west to collect an adjacent key.
        6. If an adjacent tile is goal, move into it.
        7. Else if an adjacent tile is checkpoint, move into it.
        8. goal.direction is only a hint, not a command.
        9. It is allowed to temporarily increase goal distance to avoid a dead end or reach a useful objective.

        Direction sanity:
        - north decreases y.
        - south increases y.
        - east increases x.
        - west decreases x.
        - Never claim north helps with a south target.
        - Never claim west helps with an east target.

        Return JSON only in this exact format:
        {{
        "action": "move_north",
        "chosen_tile": "path",
        "reason": "brief reason"
        }}
"""


def get_tier_prompt_rules(observation_tier):
    if observation_tier == 0:
        return """
            Tier 0 rules:
            You only have immediate surroundings and take_analysis.
            take_analysis has priority over movement.
            If take_analysis.available is true, choose take.
            Otherwise choose the safest adjacent useful tile.
            Priority:
            take > goal > checkpoint > door > timed_pressure_plate > toggleable_hazard_safe > stairs/ladder/ledge/safe_fall > path/spawn.
            """

    if observation_tier == 1:
        return """
            Tier 1 rules:
            You have immediate surroundings, inventory, position, goal direction, and take_analysis.
            take_analysis has priority over movement.
            If take_analysis.available is true, choose take.
            Use surroundings first.
            Use goal direction only as a tie-breaker between equally safe and equally useful moves.
            Do not choose an unsafe tile just because it points toward the goal.
            Priority:
            take > goal > checkpoint > door > timed_pressure_plate > toggleable_hazard_safe > stairs/ladder/ledge/safe_fall > path/spawn.
            """

    if observation_tier == 2:
        return """
            Tier 2 rules:
            You have text_vision as local symbolic map context and take_analysis.
            take_analysis has priority over text_vision.
            If take_analysis.available is true, choose take.
            Use text_vision to avoid obvious dead ends and follow visible paths.
            Prefer visible objectives over goal direction.
            Priority:
            take > goal > checkpoint > door > timed_pressure_plate > toggleable_hazard_safe > stairs/ladder/ledge/safe_fall > unexplored path > spawn/recent path.
            """

    if observation_tier == 3:
        return """
            Tier 3 rules:
            You have branch_analysis, possible_moves, recent_positions, and take_analysis.
            take_analysis has priority over branch_analysis.
            If take_analysis.available is true, choose take.
            Use branch_analysis as the main route guide.
            Prefer branch results in this order:
            take_key_immediately > goal > checkpoint > key > door > pressure_plate/timed_pressure_plate > toggleable_hazard_safe > safe_fall > special_continuation > junction > scan_limit_reached > path/spawn > dead_end > empty/blocked/unsafe.

            Use possible_moves[action].target_recent and branch_recent_count to avoid loops.
            Do not choose a target_recent move if there is another safe move with target_recent false in the same or higher observation tier.
            Only use exploration_score and goal.direction as tie-breakers between actions with the same branch result tier.
            If branch_analysis contains result take_key_immediately, choose take immediately.
            """

    if observation_tier == 4:
        return """
            Tier 4 rules:
        Tier 4 rules:
        You have bfs_analysis as the main route guide and take_analysis.

        Absolute priority:
        1. If take_analysis.available is true, choose take.
        2. Otherwise, only consider actions where bfs_analysis[action].safe is true.
        3. Never choose an action where bfs_analysis[action].safe is false.

        BFS result priority order:
        goal > checkpoint > key > door > pressure_plate/timed_pressure_plate > toggleable_hazard_safe > safe_fall > scan_limit_reached > stairs/ladder/ledge > special_continuation > junction > path/spawn > backtrack > dead_end > empty/blocked/unsafe.

        Decision procedure:
        Step 1: Find the highest-priority bfs_analysis.result among safe actions.
        Step 2: Discard every safe action with a lower-priority result.
        Step 3: If more than one remaining action has the same result, choose the one with the lowest bfs_analysis.steps.
        Step 4: This step rule is strict. For the same result, lower steps always wins.
        Step 5: Only compare reachable_tiles if result and steps are exactly tied.
        Step 6: Only use goal direction if result, steps, and reachable_tiles are all tied.

        Do not choose a higher-step action when another safe action has the same result with fewer steps.
        Do not justify a higher-step action by saying it reaches the same objective.
            """

    return ""