import pygame
import sys
from pathlib import Path

import Render
import LevelLoader
import argparse

from PIL import Image

# TODO: 
# add agent
# finalise action space
# add clear goal
# add logging file
# add proper README
# create scoring system
# finalise real level
# reduce visual clutter further
# find method of feeding visual data to ai
# Add discord between visual and sensory input, make 1 more accurate than other at times

# TODO Planning to expand this to potentially include:
#  - Height difference
#  - Move Possibility
#  - Wider radius/reach or line of sight sensing
#  - Objectives
#  - Fall consequences


# File Name
VOX_FILE = Path("TestBench.vox")
LEVEL_SIZE = 32 # The expected size of the level in cubes. Used for scaling the render and centering the camera

# Generic init values
WIDTH = 600
HEIGHT = 600

# Timed hazard settings
TOGGLE_HAZARD_SAFE_TIME = 10000 # 10s

# Direction vectors used by the agent
DIRECTION_TO_VECTOR = {
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0),
}

MOVE_ACTION_TO_DIRECTION = {
    "move_north": "north",
    "move_west": "west",
    "move_south": "south",
    "move_east": "east",
}

# Tiles the agent can normally stand on
WALKABLE_TYPES = {
    "spawn",
    "checkpoint",
    "path",
    "stairs",
    "ladder",
    "ledge",
    "timed_pressure_plate",
    "goal",
}

# Tiles that can be picked up
KEY_TYPES = {
    "key1",
    "key2",
}

AGENT_STEP_TIME = 1000

# List of checkpoints as well as the goal for tracking
CHECKPOINT_LOCATIONS = [
[-15, -7, 1],
[3, -7, 1],
[22, -7, 1],
[6, 3, 1],
[-2, 1, 1],

[-15, 3, 1], # goal
]

checkpoint_tracking_iterator = 0

# Agent state
agent = {
    "x": 0,
    "y": 0,
    "z": 0,
    "inventory": [],
    "alive": True,
}

last_agent_step = 0
goal = "Find the goal at the end of the level"

# Timed hazard state
toggleable_hazard_safe_until = 0

checkpoint_location = None

def get_launch_options():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai", action="store_true", help="Run with OpenAI agent")
    return parser.parse_args()

# Gets the highest cube at a x y position
# Used for finding the tile the agent is trying to move to and for top of ladder
# Potentially will be used to implement door key sensing logic
def get_cube_at_xy(cube_map, x, y, top_count=None):

    matching_cubes = []
    # Horrifically inefficient, levels are small but if given time this will be optimised
    for cube_position in cube_map:

        cube_x = cube_position[0]
        cube_y = cube_position[1]

        if cube_x == x and cube_y == y: matching_cubes.append(cube_map[cube_position])

    matching_cubes.sort(
        key=lambda cube: cube["z"],
        reverse=True
    )

    # Gets cubes at same level or 1 below agent
    if top_count is None:
        for cube in matching_cubes:
            if cube["z"] == agent["z"]:
                if matching_cubes and matching_cubes[0]["type"] == "ladder" and cube["type"] == "ladder":
                    return matching_cubes[0] # Finds tops of ladders, check is in edge case of scanning a tile below a ladder
                return cube

        for cube in matching_cubes:
            if cube["z"] == agent["z"] - 1:
                return cube
            if cube["z"] == agent["z"] - 2:
                return cube # for stairs going downward
        return None
    return matching_cubes[:top_count]

# Removes a cube from both the list and the map
# Future function for door and other temporary tiles
def remove_cube(cubes, cube_map, cube):

    if cube in cubes: cubes.remove(cube)

    cube_position = (cube["x"], cube["y"], cube["z"])

    if cube_position in cube_map: del cube_map[cube_position]

# Checks if toggleable hazards are currently safe against a global variable
# Not safe until pressure plate funciton triggered
# Repeated a bit so function is used
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


# Sets the respawn point
# Looks neater this way, may be used more in the future for multi level design
def set_respawn_point(x, y, z):
    global checkpoint_location
    checkpoint_location[0] = x
    checkpoint_location[1] = y
    checkpoint_location[2] = z


# Respawns the agent at the most recent checkpoint or spawn point
def respawn_agent():
    global checkpoint_location

    agent["x"] = checkpoint_location[0]
    agent["y"] = checkpoint_location[1]
    agent["z"] = checkpoint_location[2]
    agent["alive"] = True

    print(f"Respawned at ({agent['x']}, {agent['y']}, {agent['z']})")


# Kills the agent + respawn
def kill_agent(reason):

    agent["alive"] = False

    print("")
    print("Agent died")
    print(reason)

    respawn_agent()
    print("")


# Prevents the agent from moving onto tiles it cannot enter
# Thought to merge this and the next function, however this would impact specificity of messages
def can_enter_cube(cube):

    if cube is None: return False
    if cube["type"] == "hazard" or cube["type"] == "death_tile": return False

    if cube["type"] == "toggleable_hazard":
        if toggleable_hazards_are_safe():
            return True
        return False

    if cube["type"] in WALKABLE_TYPES:
        return True
    return False

# At target, find the highest cube below agent
# Used in ledge logic
def get_fall_target(cube_map, x, y):
    fall_target = None
    # Again, very inefficient
    for cube_position in cube_map:

        cube_x = cube_position[0]
        cube_y = cube_position[1]
        cube_z = cube_position[2]

        if cube_x == x and cube_y == y and cube_z < agent["z"]:
            cube = cube_map[cube_position]
            if fall_target is None or cube_z > fall_target["z"]:
                fall_target = cube

    return fall_target

# Moves the agent onto a cube, heavily used in movement functions and respawn
def move_agent_to_cube(cube):

    agent["x"] = cube["x"]
    agent["y"] = cube["y"]
    agent["z"] = cube["z"] + 1 # Agents z has to be adjusted as it defaults to a height 1 off where it should

    print(f"Moved onto {cube['type']}")

# Moves the agent forward off a ledge or ladder
def fall_from_ledge(cube_map, target_x, target_y):

    fall_target = get_fall_target(cube_map, target_x, target_y)
    # Safety first
    if fall_target is None:
        kill_agent("There was no tile below the ledge")
        return

    if fall_target["type"] == "hazard" or fall_target["type"] == "death_tile":
        kill_agent(f"The agent landed on a {fall_target['type']}")
        return

    if fall_target["type"] == "toggleable_hazard":
        # Edge cases
        if toggleable_hazards_are_safe():
            move_agent_to_cube(fall_target)
            print("Landed on disabled toggleable hazard")
        else:
            kill_agent("The agent landed on an active toggleable hazard")
        return

    if not can_enter_cube(fall_target):
        kill_agent(f"The agent landed on {fall_target['type']}")
        return

    move_agent_to_cube(fall_target)
    print("Fell from ledge safely")


# Door logic, checks for keys above the door and if not opens it by removing the cube
def handle_door(cubes, cube_map, door_cube):

    door_x = door_cube["x"]
    door_y = door_cube["y"]

    door_stack = get_cube_at_xy(cube_map, door_x, door_y, top_count=5)

    for cube in door_stack:
        if cube["type"] in KEY_TYPES:
            if cube["type"] not in agent["inventory"]:
                print("Door blocked. You do not have all the keys")
                return

    print("Door opened")

    for cube in door_stack:
        if cube["type"] in KEY_TYPES:
            remove_cube(cubes, cube_map, cube)

    remove_cube(cubes, cube_map, door_cube)

# Moves the agent in an absolute direction
# Initially used turn system but this was clunky for testing
def move_in_direction(direction, cubes, cube_map):

    dx, dy = DIRECTION_TO_VECTOR[direction]

    target_x = agent["x"] + dx
    target_y = agent["y"] + dy

    current_tile = cube_map.get((agent["x"], agent["y"], agent["z"] - 1))
    target_cube = get_cube_at_xy(cube_map, target_x, target_y)

    # Moving into empty space
    # Trigger fall logic, if not death
    if target_cube is None:
        if current_tile is not None and current_tile["type"] in {"ledge", "ladder"}:
            fall_from_ledge(cube_map, target_x, target_y)
        else:
            kill_agent("The agent stepped into empty space")
        return

    # Door logic
    if target_cube["type"] == "door":
        handle_door(cubes, cube_map, target_cube)
        return

    # Ladder logic
    if target_cube["type"] == "ladder":

        ladder_top = get_cube_at_xy(cube_map, target_x, target_y)

        if ladder_top is None:
            print("Move blocked. Ladder finding exception")
            return

        move_agent_to_cube(ladder_top)
        print("Climbed ladder")
        return

    # Hazard logic
    if target_cube["type"] == "hazard" or target_cube["type"] == "death_tile":
        kill_agent("The agent died")
        return

    # Toggleable hazard logic
    if target_cube["type"] == "toggleable_hazard":
        if toggleable_hazards_are_safe():
            move_agent_to_cube(target_cube)
            print("Crossed disabled toggleable hazard")
        else:
            kill_agent("The agent walked onto an active toggleable hazard")
        return

    # Prevents moving directly between white path cubes at different heights
    if current_tile and target_cube:
        if current_tile["type"] == "path" and target_cube["type"] == "path" and current_tile["z"] != target_cube["z"]:
            print("Move blocked. Cannot move directly between path cubes at different heights")
            return
    
    # Stairs logic
    if target_cube["type"] == "stairs":
        move_agent_to_cube(target_cube)
        print("Walked onto stairs")
        return

    # Pressure plate logic
    if target_cube["type"] == "timed_pressure_plate":
        move_agent_to_cube(target_cube)
        activate_pressure_plate(cubes)
        return

    # Normal movement and checkpoint update logic
    if target_cube["type"] in WALKABLE_TYPES:
        move_agent_to_cube(target_cube)

        if target_cube["type"] == "checkpoint":
            global checkpoint_location, checkpoint_tracking_iterator

            old_checkpoint_cube = get_cube_at_xy(cube_map, checkpoint_location[0], checkpoint_location[1])
            old_checkpoint_cube["colour"] = (238, 238, 238)
            old_checkpoint_cube["type"] = "path"

            set_respawn_point(agent["x"], agent["y"], agent["z"])
            target_cube["colour"] = (238, 0, 0)
            target_cube["type"] = "spawn"

            checkpoint_tracking_iterator += 1

            print("Checkpoint updated")
        return

    print(f"Move blocked. Target is {target_cube['type']}")


# Takes the object on the current tile if it can be taken
def take_around_current_tile(cubes, cube_map):

    for dx, dy in DIRECTION_TO_VECTOR.values():
        current_tile = cube_map.get((agent["x"] + dx, agent["y"] + dy, agent["z"]))
        if current_tile is not None and current_tile["type"] in KEY_TYPES:
            # Agent inventory is just a list of strings for now
            agent["inventory"].append(current_tile["type"])
            print(f"Took {current_tile['type']}")
            remove_cube(cubes, cube_map, current_tile)
            return

    print("There is nothing to take")


def sense_direction(cube_map, direction):

    dx, dy = DIRECTION_TO_VECTOR[direction]

    target_x = agent["x"] + dx
    target_y = agent["y"] + dy

    target_cube = get_cube_at_xy(cube_map, target_x, target_y)

    if target_cube is None:
        return "empty"

    if target_cube["type"] == "toggleable_hazard":
        if toggleable_hazards_are_safe():
            return "toggleable_hazard_safe"
        return "toggleable_hazard_active"
    return target_cube["type"]


# Prints the object type one tile in each direction
# TODO expand
def print_senses(cube_map):

    print("")
    print("Agent state")
    print(f"Position: ({agent['x']}, {agent['y']}, {agent['z']})")
    print(f"Alive: {agent['alive']}")
    print(f"Inventory: {agent['inventory']}")

    print("")
    print("Sense")

    for direction in DIRECTION_TO_VECTOR:
        tile_type = sense_direction(cube_map, direction)
        print(f"{direction}: {tile_type}")

    print("")


# Gets the camera origin so the agent is centred
def get_camera_origin():
    origin_x = Render.MIDDLE_X - (agent["x"] - agent["y"]) * (Render.TILE_W // 2)
    origin_y = Render.MIDDLE_Y - (agent["x"] + agent["y"]) * (Render.TILE_H // 2) + agent["z"] * Render.CUBE_HEIGHT
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

    origin_x, origin_y = get_camera_origin()
    render_items = []

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
            "x": agent["x"],
            "y": agent["y"],
            "z": agent["z"] - 1,
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
            if agent["alive"]:
                Render.draw_agent(
                    screen,
                    agent["x"],
                    agent["y"],
                    agent["z"],
                    origin_x=origin_x,
                    origin_y=origin_y,
                )


# Runs an action based on the input string
def run_action(action, cubes, cube_map, goal_cube=None):

    if action in MOVE_ACTION_TO_DIRECTION:
        move_in_direction(MOVE_ACTION_TO_DIRECTION[action], cubes, cube_map)
    elif action == "take":
        take_around_current_tile(cubes, cube_map)
    else:
        print(f"Unknown action: {action}")

    print_senses(cube_map)

    if goal_cube is not None:
        observation = get_observations(cube_map, goal_cube)
        print(f"Goal distance: {observation['goal']['distance']}, direction: {observation['goal']['direction']['general_direction']}")
    
    print(f"Goal cube found: {goal_cube}")

    if goal_completed(goal_cube):
        print("Goal reached!")
        print(get_observations(cube_map, goal_cube))
        pygame.quit()
        sys.exit(0)

# Adds original colours to cubes so toggleable hazards can reset
# This may be later changed to customise level look without changing the underlying logic colours
def store_original_colours(cubes):
    for cube in cubes:
        cube["original_colour"] = cube["colour"]

def save_screenshot(screen, path="game_view.jpg"):
    pygame.image.save(screen, path)

def save_small_screenshot(screen, path = "game_view.png"):
    pygame.image.save(screen, path)

    image = Image.open(path)
    image = image.resize((300, 300))
    image.save(path, optimize = True)

# This is in a seperate function in case goal changes or gets more complicated
def goal_completed(goal_cube):
    if goal_cube is None: # Safety
        return False
    if (agent["x"] == goal_cube["x"] and agent["y"] == goal_cube["y"] and agent["z"] == goal_cube["z"] + 1):
        return True
    return False

def distance_to_goal():

    goal_x = CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][0]
    goal_y = CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][1]
    goal_z = CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][2] + 1
    # Giving the agent absolute distance should help it out
    return abs(agent["x"] - goal_x) + abs(agent["y"] - goal_y) + abs(agent["z"] - goal_z)

def direction_to_goal():

    dx = CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][0] - agent["x"]
    dy = CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][1] - agent["y"]
    dz = (CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][2] + 1) - agent["z"]

    return {
        "x_difference": dx,
        "y_difference": dy,
        "z_difference": dz,

        "general_direction": {
            "east_west": "east" if dx > 0 else "west" if dx < 0 else "same",
            "north_south": "south" if dy > 0 else "north" if dy < 0 else "same",
            "vertical": "up" if dz > 0 else "down" if dz < 0 else "same",
        }
    }

def get_observations(cube_map, goal_cube):

    senses = {}

    for direction in DIRECTION_TO_VECTOR:
        senses[direction] = sense_direction(cube_map, direction)

    observation = {
        "position": {
            "x": agent["x"],
            "y": agent["y"],
            "z": agent["z"],
        },

        "alive": agent["alive"],
        "inventory": agent["inventory"],
        "surroundings": senses,
        
        "goal": {
            "position": None if goal_cube is None else {
                "x": CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][0],
                "y": CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][1],
                "z": CHECKPOINT_LOCATIONS[checkpoint_tracking_iterator][2] + 1,
            },

            "distance": distance_to_goal(),
            "direction": direction_to_goal(),
        },

        "valid_actions": [
            "move_north",
            "move_east",
            "move_south",
            "move_west",
            "take",
        ],
        
        "goal_reached": goal_completed(goal_cube),
    }

    return observation

# Runs the main pygame window
def main():
    global last_agent_step, checkpoint_location
    # Setup and ai flag
    args = get_launch_options()
    Agent = None
    if args.ai:
        import Agent


    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("LLM Valley")
    clock = pygame.time.Clock()

    # Stops the program if the level file cannot be found
    # Not big on error handling for this project but this is a common issue when including multiple levels or level switching (thinking ahead)
    if not VOX_FILE.exists():
        print(f"Could not find {VOX_FILE}")
        pygame.quit()
        sys.exit(1)

    cubes, cube_map, checkpoint_location = LevelLoader.load_vox_cubes(VOX_FILE, LEVEL_SIZE)
    store_original_colours(cubes)

    if checkpoint_location is None: # Safety check, every level should have a spawn point
        print("No spawn point found")
        pygame.quit()
        sys.exit(1)


    agent["x"] = checkpoint_location[0]
    agent["y"] = checkpoint_location[1]
    agent["z"] = checkpoint_location[2]
    agent["alive"] = True

    agent_step_count = 0
    goal_cube = None


    for cube in cubes:
        if cube["type"] == "goal":
            goal_cube = cube

    set_respawn_point(agent["x"], agent["y"], agent["z"])
    print(f"Loaded {len(cubes)} cubes from {VOX_FILE}")
    print_senses(cube_map)

    # Game loop
    # Taken from one of my other projects, will likely be refactored as the project develops but it works for now
    while True:
        current_time = pygame.time.get_ticks()
        
        if args.ai and current_time - last_agent_step > AGENT_STEP_TIME:
            observation = get_observations(cube_map, goal_cube)
            screenshot_path = None

            if agent_step_count % 5 == 0:
                save_small_screenshot(screen, "game_view.png")
                screenshot_path = "game_view.png"

            if observation["goal_reached"]:
                print("Goal reached!")
                print(observation)
                pygame.quit()
                sys.exit(0)
            
            action = Agent.choose_action(observation, goal, screenshot_path)

            print(f"Agent chose : {action}")
            run_action(action, cubes, cube_map, goal_cube)

            agent_step_count += 1
            last_agent_step = current_time

        update_toggleable_hazard_colours(cubes)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                if event.key == pygame.K_w:
                    run_action("move_north", cubes, cube_map, goal_cube)

                if event.key == pygame.K_a:
                    run_action("move_west", cubes, cube_map, goal_cube)

                if event.key == pygame.K_s:
                    run_action("move_south", cubes, cube_map, goal_cube)

                if event.key == pygame.K_d:
                    run_action("move_east", cubes, cube_map, goal_cube)

                if event.key == pygame.K_e:
                    run_action("take", cubes, cube_map)

        screen.fill(Render.BACKGROUND)
        draw_scene(screen, cubes)
        pygame.display.flip()
        clock.tick(60)

# Taken from other thing
# Allows module to be imported but also run directly
if __name__ == "__main__": main()