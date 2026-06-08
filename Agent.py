import json
from openai import OpenAI

client = OpenAI()

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
}

def choose_action(observation, goal, screenshot_path=None):
    global recent_positions, visited_counts

    observation["recent_positions"] = recent_positions[-6:]

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
        for pos in recent_positions[-6:]
    }

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

        observation["possible_moves"][action] = {
            "direction": direction,
            "target_position": target_position,
            "target_tile": target_tile,
            "target_visit_count": visited_counts.get(target_position_key, 0),
            "target_recent": target_position_key in recent_xy_positions,
        }

    prompt = f"""
You are an agent in a small voxel world.

Goal:
{goal}

Observation:
{json.dumps(observation, indent=2)}

Choose exactly one action:
move_north, move_east, move_south, move_west, take.

Action mapping:
move_north -> surroundings.north
move_east -> surroundings.east
move_south -> surroundings.south
move_west -> surroundings.west

Rules:
1. Safety is absolute.
2. Only move into: path, spawn, checkpoint, goal, stairs, ladder, ledge, timed_pressure_plate, toggleable_hazard_safe.
3. Never move into: death_tile, hazard, empty, toggleable_hazard_active, door, unknown.
4. If an adjacent tile is goal, move into it.
5. Else if an adjacent tile is checkpoint, move into it.
6. Use observation.branch_analysis as the main navigation guide.
7. Prefer branch results in this order:
goal, checkpoint, safe non-recent moves, special_continuation, junction, scan_limit_reached, then lowest target_visit_count.
8. A move with target_recent true is usually backtracking.
9. Do not choose a target_recent move if there is another safe move with target_recent false.
10. special_continuation does not override target_recent.
11. Avoid branch results: dead_end, empty, blocked, unsafe unless no better safe branch exists.
12. Stairs and ladders are useful only when they lead to new progress. If recently visited and another safe route exists, avoid them.
13. goal.direction is only a hint, not a command.
14. It is allowed to temporarily increase goal distance to avoid a dead end or return to a junction.

Backtracking and junction rules:
1. Do not prefer a branch just because it reaches a junction in fewer steps.
2. A junction after 1 step is only bad if that move returns to a recent position.
3. If the 1-step junction is not in recent_positions, it is a valid forward move.
4. Never choose a recent-position move just because its branch has more steps.
5. Treat a 1-step junction as backtracking if its target position is in recent_positions.
6. Prefer a branch that reaches a new or further junction over a branch that immediately returns to a recent junction.
7. If two branches both lead to junctions, prefer the one with lower target_visit_count unless it is clearly just backtracking.
8. If a branch is dead_end, do not choose it while another safe branch reaches a junction, checkpoint, goal, stairs, ladder, or scan_limit_reached.

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
    "reason": "brief reason using surroundings, branch_analysis, target_visit_count, and whether the move is backtracking"
}}

Final check:
- action must be in safe_actions unless action is take.
- chosen_tile must match surroundings[chosen_direction].
- never choose an unsafe tile.
- do not choose a dead_end branch if there is a safe junction, checkpoint, goal, stairs, ladder, or scan_limit_reached branch.
- do not choose a one-step junction backtrack if there is another safe branch leading to a further junction.
- if the chosen action has possible_moves[action].target_recent true and another safe action has target_recent false, choose the non-recent action instead.
- do not choose recently visited stairs or ladders unless every other safe action is worse or unsafe.
"""

    content = [{"type": "input_text", "text": prompt}]

    response = client.responses.create(
        model="gpt-4.1-mini",
        temperature=0,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
    )

    raw = response.output_text.strip()

    try:
        decision = extract_json(raw)
    except json.JSONDecodeError:
        print(f"Bad AI response: {raw!r}")
        return "take"

    action = decision.get("action")

    possible_moves = observation.get("possible_moves", {})
    branch_analysis = observation.get("branch_analysis", {})

    chosen_move = possible_moves.get(action, {})
    chosen_recent = chosen_move.get("target_recent", False)

    if chosen_recent:
        for alternative_action, alternative_move in possible_moves.items():
            alternative_tile = alternative_move.get("target_tile")
            alternative_recent = alternative_move.get("target_recent", False)
            alternative_branch = branch_analysis.get(alternative_action, {})
            alternative_result = alternative_branch.get("result")

            if alternative_tile not in SAFE_TILES:
                continue

            if alternative_recent:
                continue

            if alternative_result in {"unsafe", "blocked", "empty", "dead_end"}:
                continue

            print(f"Prevented recent-position loop. Overriding {action} with {alternative_action}")
            action = alternative_action
            break

    chosen_tile = decision.get("chosen_tile", "")
    reason = decision.get("reason", "")

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