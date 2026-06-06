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
        - The goal is the dark green cube
        - Prefer actions that reduce distance to goal
        - Use goal.direction to choose the general direction of travel
        - If there is no immediate path that increases goal you may travel in a different direction
        - Try to find a path through the walkable tiles such as white cubes
        - If direction is blocked, choose another walkable direction to explore
        
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