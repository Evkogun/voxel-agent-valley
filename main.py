import pygame
import sys

import Render
import LevelLoader
import Movement
import Vision
import Sense
import Level
from Config import * # Didn't want every constant to be preceded by Config.

import argparse
Movement.setup(sys.modules[__name__])
Level.setup(sys.modules[__name__])
Sense.setup(sys.modules[__name__])
Vision.setup(sys.modules[__name__])

# TODO: 
# FIX DOOR DETECTED AS DEAD END

checkpoint_tracking_iterator = 0
checkpoint_start = 0
keys_start = False

# Agent state
agent = {
    "x": 0,
    "y": 0,
    "z": 0,
    "inventory": [],
    "alive": True,
}

agent_vision = []

last_agent_step = 0
goal = "Find the goal at the end of the level"

# Timed hazard state
toggleable_hazard_safe_until = 0

checkpoint_location = None

# Reads command line flags for AI mode, checkpoint starting and key starting
# Called at the start of main
def get_launch_options():
    global checkpoint_start, keys_start

    parser = argparse.ArgumentParser()
    parser.add_argument("--ai", action="store_true", help="Run with OpenAI agent")
    parser.add_argument("--checkpoint", type=int, default=0, help="Starting checkpoint")
    parser.add_argument("--keys", action="store_true", help="Start with keys in inventory")

    args = parser.parse_args()
    checkpoint_start = args.checkpoint
    keys_start = args.keys

    return args

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

# Runs an action based on the input string
def run_action(action, cubes, cube_map, goal_cube=None):

    if action in MOVE_ACTION_TO_DIRECTION:
        Movement.move_in_direction(MOVE_ACTION_TO_DIRECTION[action], cubes, cube_map)
    elif action == "take":
        Movement.take_around_current_tile(cubes, cube_map)
    else:
        print(f"Unknown action: {action}")

    Sense.print_senses(cube_map)

    if goal_cube is not None:
        Vision.update_agent_vision(cubes)
        observation = Vision.get_observations(cube_map, goal_cube)
        print(f"Goal distance: {observation['goal']['distance']}, direction: {observation['goal']['direction']['general_direction']}")

    if goal_completed(goal_cube):
        print("Goal reached!")
        print(Vision.get_observations(cube_map, goal_cube))
        pygame.quit()
        sys.exit(0)

# This is in a seperate function in case goal changes or gets more complicated
def goal_completed(goal_cube):
    if goal_cube is None: # Safety
        return False
    if (agent["x"] == goal_cube["x"] and agent["y"] == goal_cube["y"] and agent["z"] == goal_cube["z"] + 1):
        return True
    return False

# Runs the main pygame window
def main():
    global last_agent_step, checkpoint_location, agent_vision, checkpoint_start, checkpoint_tracking_iterator
    agent_vision = Vision.create_empty_agent_vision()
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
    Level.store_original_colours(cubes)

    if checkpoint_location is None: # Safety check, every level should have a spawn point
        print("No spawn point found")
        pygame.quit()
        sys.exit(1)

    if keys_start:
        for key_location, matching_key_location in KEY_LOCATION_ADJACENT.items():
            agent["x"] = key_location[0]
            agent["y"] = key_location[1]
            agent["z"] = key_location[2] + 1
            run_action("take", cubes, cube_map)

            matching_key_cube = cube_map.get(matching_key_location)

            if matching_key_cube is not None and matching_key_cube["type"] in KEY_TYPES:
                Movement.remove_cube(cubes, cube_map, matching_key_cube)

    if checkpoint_start:
        if checkpoint_start > 5: checkpoint_start = 5
        checkpoint_tracking_iterator = 0
        for i in range(checkpoint_start):
            agent["x"] = CHECKPOINT_LOCATIONS[i][0]
            agent["y"] = CHECKPOINT_LOCATIONS[i][1]
            agent["z"] = CHECKPOINT_LOCATIONS[i][2] + 1
            Movement.move_in_direction("stay", cubes, cube_map)
    else:
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
    Sense.print_senses(cube_map)

    # Game loop
    # Taken from one of my other projects, will likely be refactored as the project develops but it works for now
    while True:
        current_time = pygame.time.get_ticks()
        
        if args.ai and current_time - last_agent_step > AGENT_STEP_TIME:
            Vision.update_agent_vision(cubes)
            observation = Vision.get_observations(cube_map, goal_cube)
            screenshot_path = None

            if observation["goal_reached"]:
                print("Goal reached!")
                print(observation)
                pygame.quit()
                sys.exit(0)
            
            action = Agent.choose_action(observation, goal, screenshot_path)

            if action is None:
                print("Agent did not choose an action. Skipping this step.")
            else:
                print(f"Agent chose : {action}")
                run_action(action, cubes, cube_map, goal_cube)

            agent_step_count += 1
            last_agent_step = current_time

        Level.update_toggleable_hazard_colours(cubes)
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

                if event.key == pygame.K_m:
                    Vision.print_agent_text_vision(cubes)

        screen.fill(Render.BACKGROUND)
        Level.draw_scene(screen, cubes)
        pygame.display.flip()
        clock.tick(60)

# Taken from other thing
# Allows module to be imported but also run directly
if __name__ == "__main__": main()