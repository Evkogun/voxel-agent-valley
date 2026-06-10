from Config import *
import pygame
from level import Movement
from level import Render
from ai import Vision

# Checks if toggleable hazards are currently safe against a global variable
# Not safe until pressure plate funciton triggered
def toggleable_hazards_are_safe(state):
    return pygame.time.get_ticks() < state.toggleable_hazard_safe_until

# Toggleable hazard colour change function
def update_toggleable_hazard_colours(state):

    safe = toggleable_hazards_are_safe(state)

    for cube in state.cubes:
        if cube["type"] == "toggleable_hazard":
            if safe: cube["colour"] = (195, 195, 144) # To distiguish it from other walkable tiles
            else: cube["colour"] = cube["original_colour"]

# Activates pressure plate effect
def activate_pressure_plate(state):

    current_time = pygame.time.get_ticks()
    state.toggleable_hazard_safe_until = current_time + TOGGLE_HAZARD_SAFE_TIME

    update_toggleable_hazard_colours(state)
    print("Pressure plate activated. Toggleable hazards are safe for 10 seconds")

# Door logic, checks for keys above the door and if not opens it by removing the cube
def get_door_required_keys(state, door_cube):

    required_keys = []
    door_stack = Movement.get_cube_at_xy(state, door_cube["x"], door_cube["y"], top_count=5)

    for cube in door_stack:
        if cube["type"] in KEY_TYPES and cube["type"] not in required_keys:
            required_keys.append(cube["type"])
    return required_keys

# Checks which required door keys are not currently in the agent inventory
# Used by door sensing, branch scanning and handle_door
def get_missing_door_keys(state, door_cube):

    missing_keys = []

    for key in get_door_required_keys(state, door_cube):
        if key not in state.agent["inventory"]:
            missing_keys.append(key)
    return missing_keys

# Can a door be opened?
# Mentioned by sense_direction and get_scan_tile_type when classifying doors
def has_required_door_keys(state, door_cube):
    return len(get_missing_door_keys(state, door_cube)) == 0

# Opens a door once the agent has the required keys, otherwise blocks movement
# Used by Movement.move_in_direction when the target tile is a door
def handle_door(state, door_cube):

    door_x = door_cube["x"]
    door_y = door_cube["y"]

    door_stack = Movement.get_cube_at_xy(state, door_x, door_y, top_count=5)

    missing_keys = get_missing_door_keys(state, door_cube)

    if missing_keys:
        print(f"Door blocked. Missing keys: {missing_keys}")
        return

    print("Door opened")

    for cube in door_stack:
        if cube["type"] in KEY_TYPES:
            Movement.remove_cube(state, cube)
    Movement.remove_cube(state, door_cube)

# Gets the camera origin so the agent is centred
def get_camera_origin(state):
    origin_x = Render.MIDDLE_X - (state.agent["x"] - state.agent["y"]) * (Render.TILE_W // 2)
    origin_y = Render.MIDDLE_Y - (state.agent["x"] + state.agent["y"]) * (Render.TILE_H // 2) + state.agent["z"] * Render.CUBE_HEIGHT
    return origin_x, origin_y

# Draws all cubes in the level
# Gets draw depth for isometric rendering
def get_draw_depth(item):
    # Higher x + y means visually further forward in the isometric scene
    # z is included so higher objects are drawn slightly later
    # This is to prevent cubes visually overlapping in the wrong order when they are at the same x + y but different heights
    return item["x"] + item["y"] + item["z"]

# Draws all cubes and the agent in depth order
# Most of this was moved to the Render module but the draw_scene function is still responsible for sorting everything in the correct order
def draw_scene(state, screen):
    state.agent_vision = Vision.create_empty_agent_vision()

    origin_x, origin_y = get_camera_origin(state)
    render_items = []
    offset = LEVEL_SIZE // 2

    # Adds all cubes to the render list
    for cube in state.cubes:
        render_items.append(
            {
                "kind": "cube",
                "x": cube["x"],
                "y": cube["y"],
                "z": cube["z"],
                "cube": cube,
            }
        )

    # Adds the agent to the render list
    # Agent z is stored as standing height, 1 below
    render_items.append(
        {
            "kind": "agent",
            "x": state.agent["x"],
            "y": state.agent["y"],
            "z": state.agent["z"] - 1,
        }
    )

    # Sorts everything together so further forward objects draw over earlier ones
    render_items.sort(key = get_draw_depth)

    for item in render_items:
        if item["kind"] == "cube":
            cube = item["cube"]
            Render.draw_cube(
                screen,
                cube["x"],
                cube["y"],
                cube["z"],
                top_colour=cube["colour"],
                origin_x=origin_x,
                origin_y=origin_y,
            )

        elif item["kind"] == "agent":
            if state.agent["alive"]:
                Render.draw_agent(
                    screen,
                    state.agent["x"],
                    state.agent["y"],
                    state.agent["z"],
                    origin_x=origin_x,
                    origin_y=origin_y,
                )

# Adds original colours to cubes so toggleable hazards can reset
# This may be later changed to customise level look without changing the underlying logic colours
def store_original_colours(cubes):
    for cube in cubes:
        cube["original_colour"] = cube["colour"]
