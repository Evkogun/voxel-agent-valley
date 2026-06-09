from Config import *
import pygame
import Movement
import Render
import Vision


def setup(main_module):
    global main
    main = main_module

# Checks if toggleable hazards are currently safe against a global variable
# Not safe until pressure plate funciton triggered
def toggleable_hazards_are_safe():
    return pygame.time.get_ticks() < toggleable_hazard_safe_until

# Toggleable hazard colour change function
def update_toggleable_hazard_colours(cubes):

    safe = toggleable_hazards_are_safe()

    for cube in cubes:
        if cube["type"] == "toggleable_hazard":
            if safe: cube["colour"] = (195, 195, 144) # To distiguish it from other walkable tiles
            else: cube["colour"] = cube["original_colour"]

# Activates pressure plate effect
def activate_pressure_plate(cubes):

    global toggleable_hazard_safe_until

    current_time = pygame.time.get_ticks()
    toggleable_hazard_safe_until = current_time + TOGGLE_HAZARD_SAFE_TIME

    update_toggleable_hazard_colours(cubes)
    print("Pressure plate activated. Toggleable hazards are safe for 10 seconds")

# Door logic, checks for keys above the door and if not opens it by removing the cube
def get_door_required_keys(cube_map, door_cube):

    required_keys = []
    door_stack = Movement.get_cube_at_xy(cube_map, door_cube["x"], door_cube["y"], top_count=5)

    for cube in door_stack:
        if cube["type"] in KEY_TYPES and cube["type"] not in required_keys:
            required_keys.append(cube["type"])
    return required_keys

def get_missing_door_keys(cube_map, door_cube):

    missing_keys = []

    for key in get_door_required_keys(cube_map, door_cube):
        if key not in main.agent["inventory"]:
            missing_keys.append(key)
    return missing_keys

def has_required_door_keys(cube_map, door_cube):
    return len(get_missing_door_keys(cube_map, door_cube)) == 0

def handle_door(cubes, cube_map, door_cube):

    door_x = door_cube["x"]
    door_y = door_cube["y"]

    door_stack = Movement.get_cube_at_xy(cube_map, door_x, door_y, top_count=5)

    missing_keys = get_missing_door_keys(cube_map, door_cube)

    if missing_keys:
        print(f"Door blocked. Missing keys: {missing_keys}")
        return

    print("Door opened")

    for cube in door_stack:
        if cube["type"] in KEY_TYPES:
            Movement.remove_cube(cubes, cube_map, cube)
    Movement.remove_cube(cubes, cube_map, door_cube)

# Gets the camera origin so the agent is centred
def get_camera_origin():
    origin_x = Render.MIDDLE_X - (main.agent["x"] - main.agent["y"]) * (Render.TILE_W // 2)
    origin_y = Render.MIDDLE_Y - (main.agent["x"] + main.agent["y"]) * (Render.TILE_H // 2) + main.agent["z"] * Render.CUBE_HEIGHT
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
def draw_scene(screen, cubes):
    global agent_vision
    agent_vision = Vision.create_empty_agent_vision()

    origin_x, origin_y = get_camera_origin()
    render_items = []
    offset = LEVEL_SIZE // 2

    # Adds all cubes to the render list
    for cube in cubes:
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
            "x": main.agent["x"],
            "y": main.agent["y"],
            "z": main.agent["z"] - 1,
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
            if main.agent["alive"]:
                Render.draw_agent(
                    screen,
                    main.agent["x"],
                    main.agent["y"],
                    main.agent["z"],
                    origin_x=origin_x,
                    origin_y=origin_y,
                )

# Adds original colours to cubes so toggleable hazards can reset
# This may be later changed to customise level look without changing the underlying logic colours
def store_original_colours(cubes):
    for cube in cubes:
        cube["original_colour"] = cube["colour"]
