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

    observation["recent_positions"] = recent_positions[-2:]

    current_position_key = (
        observation["position"]["x"],
        observation["position"]["y"],
        observation["position"]["z"],
    )

    visited_counts[current_position_key] = visited_counts.get(current_position_key, 0) + 1

    x = observation["position"]["x"]
    y = observation["position"]["y"]
    z = observation["position"]["z"]

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
            target_position["z"],
        )

        observation["possible_moves"][action] = {
            "direction": direction,
            "target_position": target_position,
            "target_tile": target_tile,
            "target_visit_count": visited_counts.get(target_position_key, 0),
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
   goal, checkpoint, special_continuation, junction, scan_limit_reached, then lowest target_visit_count.
8. Avoid branch results: dead_end, empty, blocked, unsafe unless no better safe branch exists.
9. Stairs and ladders appear as special_continuation and are useful, not dead ends.
10. goal.direction is only a hint, not a command.
11. It is allowed to temporarily increase goal distance to avoid a dead end or return to a junction.

Backtracking and junction rules:
1. Do not prefer a branch just because it reaches a junction in fewer steps.
2. A junction after 1 step is often just the junction you came from.
3. Treat a 1-step junction as backtracking if its target position is in recent_positions.
4. Prefer a branch that reaches a new or further junction over a branch that immediately returns to a recent junction.
5. If two branches both lead to junctions, prefer the one with lower target_visit_count unless it is clearly just backtracking.
6. If a branch is dead_end, do not choose it while another safe branch reaches a junction, checkpoint, goal, stairs, ladder, or scan_limit_reached.

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