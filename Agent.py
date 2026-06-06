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

    Your goal is to reach the final green checkpoint.

    Observations
    {json.dumps(observation, indent=2)}

    Choose exactly one action from:
    move_north, move_east, move_south, move_west, take.
    
    Return only the action name. No explanation.

    The agent primarily receives a structured JSON observation.
    Screenshots are optional visual context and are only sent periodically.
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
        return "take"
    
    return action