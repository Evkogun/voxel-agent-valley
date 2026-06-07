import json
from openai import OpenAI
import base64

client = OpenAI()

VALID_ACTIONS = {
    "move_north",
    "move_west",
    "move_south",
    "move_east",
    "take"
}

def encode_image(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def choose_action(observation, goal, screenshot_path=None):
    prompt = f"""
    You are an agent in a small isometric voxel world.

    Your goal:
    {goal}

    Observation:
    {json.dumps(observation, indent=2)}

    Choose exactly one action from:
    move_north, move_east, move_south, move_west, take.
    
    Rules:
        - Your position in the image is represented by the red sphere
        - You should prioritise reaching the closest checkpoint tile
        - The final goal is the dark green cube
        - White path tiles are the main route. Prefer continuing along connected path tiles
        - The goal direction is only a rough hint, not a command
        - If the direct goal direction is blocked or unsafe, follow the available white path instead
        - It is allowed to temporarily increase distance to the goal if that keeps you on the white path
        - Do not repeat a blocked action

    Tile meanings:
        - path: normal walkable white cube
        - checkpoint: green walkable cube
        - goal: dark green final target cube
        - stairs: walkable cube that changes height
        - ladder: climbable cube
        - ledge: walkable cube that may allow falling safely
        - hazard: dangerous cube, avoid
        - death_tile: dangerous boundary/water, avoid
        - toggleable_hazard_active: dangerous, avoid
        - toggleable_hazard_safe: temporarily safe to walk on
        - timed_pressure_plate: walkable cube that disables toggleable hazards for a short time
        - key1/key2: pick up with take when adjacent
        - door: blocks movement unless required keys are collected
        - empty: no cube there, usually unsafe unless moving off a ledge/ladder

        Return only the action name. No explanation.

    """
    content = [{"type": "input_text", "text": prompt,}]

    if screenshot_path is not None:
        image_base64 = encode_image(screenshot_path)

        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{image_base64}",
            }
        )

    response = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
    )

    action = response.output_text.strip()

    if action not in VALID_ACTIONS:
        return "move_east"
    
    return action