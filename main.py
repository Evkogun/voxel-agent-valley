import pygame
import sys

from level import Render
from level import LevelLoader
from level import Movement
from ai import Vision
from ai import Sense
from level import Level
from Config import * # Didn't want every constant to be preceded by Config.
from GameState import GameState
import argparse

# TODO: 
# Finalise README

goal = "Find the goal at the end of the level"

# Reads command line flags for AI mode, checkpoint starting and key starting
# Called at the start of main
def get_launch_options(state):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai", action="store_true", help="Run with OpenAI agent")
    parser.add_argument("--checkpoint", type=int, default=0, help="Starting checkpoint")
    parser.add_argument("--keys", action="store_true", help="Start with keys in inventory")
    parser.add_argument("--tier", type=int, default=4, choices=range(0, 5), help="AI observation tier 0-4")
    args = parser.parse_args()
    state.print_observation_tier = "--tier" in sys.argv and not args.ai
    state.checkpoint_start = args.checkpoint
    state.keys_start = args.keys

    return args
# Allows printing of logic when ai is off
def print_observation_tier(state, observation):
    from ai import Agent

    tier = state.ai_observation_tier

    Agent.set_observation_level_flags(tier)

    print("")
    print(f"Observation tier {tier}")

    if tier == 0:
        print(
            f"{'direction':<12} "
            f"{'tile':<24}"
        )
        print("-" * 20)
        for direction, tile in observation.get("surroundings", {}).items():
            print(
                f"{direction:<12} "
                f"{str(tile):<24}"
            )

        print("")
        return

    if tier == 1:
        print(f"Position: ({observation['position']['x']}, {observation['position']['y']}, {observation['position']['z']})")
        print(f"Inventory: {observation['inventory']}")
        print(f"Goal distance: {observation['goal']['distance']}")
        print("")
        print(
            f"{'direction':<12} "
            f"{'tile':<24}"
        )
        print("-" * 20)

        for direction in DIRECTION_TO_VECTOR:
            tile = Sense.sense_direction(state, direction)
            print(
                f"{direction:<12} "
                f"{str(tile):<24}"
            )

        print("")
        return

    if tier == 2:
        Vision.print_agent_text_vision(state)
        return

    if tier == 3:
        print(
            f"{'action':<12} "
            f"{'result':<24} "
            f"{'steps':<5} "
            f"{'reason':<40}"
        )
        print("-" * 90)

        for action, analysis in observation.get("branch_analysis", {}).items():
            print(
                f"{action:<12} "
                f"{str(analysis.get('result', '-')):<24} "
                f"{str(analysis.get('steps', '-')):<5} "
                f"{str(analysis.get('reason', '-')):<40}"
            )

        print("")
        return

    if tier == 4:
        Agent.print_bfs_analysis(observation)
        return

# Runs an action based on the input string
def run_action(state, action):

    # Adds line to differentiate between moves
    print("")
    print("-" * 80)
    print(f"Action: {action}")
    print("-" * 80)

    if action in MOVE_ACTION_TO_DIRECTION:
        Movement.move_in_direction(state, MOVE_ACTION_TO_DIRECTION[action])
    elif action == "take":
        Movement.take_around_current_tile(state)
    else:
        print(f"Unknown action: {action}")

    if not state.print_observation_tier and (not state.ai_mode or state.ai_observation_tier <= 1):
        Sense.print_senses(state)

    if state.goal_cube is not None:
        Vision.update_agent_vision(state)
        observation = Vision.get_observations(state, state.goal_cube)
        goal_direction = observation["goal"]["direction"]
        # This line was changed to send "east_west" to the ai and x to the console
        print(f"Goal distance: {observation['goal']['distance']}, x: {goal_direction['x_difference']}, y: {goal_direction['y_difference']}, z: {goal_direction['z_difference']}")
        if state.print_observation_tier: print_observation_tier(state, observation)

    if goal_completed(state):
        print("Goal reached!")
        print(Vision.get_observations(state, state.goal_cube))
        pygame.quit()
        sys.exit(0)

# This is in a seperate function in case goal changes or gets more complicated
def goal_completed(state):
    if state.goal_cube is None: # Safety
        return False
    if (state.agent["x"] == state.goal_cube["x"] and state.agent["y"] == state.goal_cube["y"] and state.agent["z"] == state.goal_cube["z"] + 1):
        return True
    return False

# Runs the main pygame window
def main():
    state = GameState()
    state.agent_vision = Vision.create_empty_agent_vision()
    # Setup and ai flag
    args = get_launch_options(state)
    state.ai_observation_tier = args.tier
    state.ai_mode = args.ai

    Agent = None
    if args.ai:
        from ai import Agent


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

    state.cubes, state.cube_map, state.checkpoint_location = LevelLoader.load_vox_cubes(VOX_FILE, LEVEL_SIZE)
    Level.store_original_colours(state.cubes)

    if state.checkpoint_location is None: # Safety check, every level should have a spawn point
        print("No spawn point found")
        pygame.quit()
        sys.exit(1)

    if state.keys_start:
        for key_location, matching_key_location in KEY_LOCATION_ADJACENT.items():
            state.agent["x"] = key_location[0]
            state.agent["y"] = key_location[1]
            state.agent["z"] = key_location[2] + 1
            run_action(state, "take")

            matching_key_cube = state.cube_map.get(matching_key_location)

            if matching_key_cube is not None and matching_key_cube["type"] in KEY_TYPES:
                Movement.remove_cube(state, matching_key_cube)

    if state.checkpoint_start:
        if state.checkpoint_start > 5: state.checkpoint_start = 5
        state.checkpoint_tracking_iterator = 0
        for i in range(state.checkpoint_start):
            state.agent["x"] = CHECKPOINT_LOCATIONS[i][0]
            state.agent["y"] = CHECKPOINT_LOCATIONS[i][1]
            state.agent["z"] = CHECKPOINT_LOCATIONS[i][2] + 1
            Movement.move_in_direction(state, "stay")
    else:
        state.agent["x"] = state.checkpoint_location[0]
        state.agent["y"] = state.checkpoint_location[1]
        state.agent["z"] = state.checkpoint_location[2]

    state.agent["alive"] = True


    for cube in state.cubes:
        if cube["type"] == "goal":
            state.goal_cube = cube

    state.set_respawn_point(state.agent["x"], state.agent["y"], state.agent["z"])
    print(f"Loaded {len(state.cubes)} cubes from {VOX_FILE}")

    if not state.print_observation_tier and (not state.ai_mode or state.ai_observation_tier <= 1):
        Sense.print_senses(state)

    # Game loop
    # Taken from one of my other projects, will likely be refactored as the project develops but it works for now
    while True:
        current_time = pygame.time.get_ticks()

        if args.ai and current_time - state.last_agent_step > AGENT_STEP_TIME:
            Vision.update_agent_vision(state)
            observation = Vision.get_observations(state, state.goal_cube)
            screenshot_path = None

            if observation["goal_reached"]:
                print("Goal reached!")
                print(observation)
                pygame.quit()
                sys.exit(0)

            action = Agent.choose_action(observation, goal, screenshot_path, args.tier)

            if action is None:
                print("Agent did not choose an action. Skipping this step.")
            else:
                print(f"Agent chose : {action}")
                run_action(state, action)

            state.agent_step_count += 1
            state.last_agent_step = current_time

        Level.update_toggleable_hazard_colours(state)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                if event.key == pygame.K_w:
                    run_action(state, "move_north")

                if event.key == pygame.K_a:
                    run_action(state, "move_west")

                if event.key == pygame.K_s:
                    run_action(state, "move_south")

                if event.key == pygame.K_d:
                    run_action(state, "move_east")

                if event.key == pygame.K_e:
                    run_action(state, "take")

                if event.key == pygame.K_m:
                    Vision.print_agent_text_vision(state)

        Render.draw_background_gradient(screen)
        Level.draw_scene(state, screen)
        pygame.display.flip()
        clock.tick(60)

# Taken from other thing
# Allows module to be imported but also run directly
if __name__ == "__main__": main()
