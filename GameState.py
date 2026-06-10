class GameState:
    def __init__(self):
        self.checkpoint_tracking_iterator = 0
        self.checkpoint_start = 0
        self.keys_start = False
        self.ai_observation_tier = 4
        self.ai_mode = False
        self.agent = {
            "x": 0,
            "y": 0,
            "z": 0,
            "inventory": [],
            "alive": True,
        }
        self.agent_vision = []
        self.last_agent_step = 0
        self.toggleable_hazard_safe_until = 0
        self.checkpoint_location = None
        self.cubes = []
        self.cube_map = {}
        self.goal_cube = None
        self.agent_step_count = 0
        self.print_observation_tier = False

    def set_respawn_point(self, x, y, z):
        self.checkpoint_location[0] = x
        self.checkpoint_location[1] = y
        self.checkpoint_location[2] = z

    def respawn_agent(self):
        self.agent["x"] = self.checkpoint_location[0]
        self.agent["y"] = self.checkpoint_location[1]
        self.agent["z"] = self.checkpoint_location[2]
        self.agent["alive"] = True

        print(f"Respawned at ({self.agent['x']}, {self.agent['y']}, {self.agent['z']})")

    def kill_agent(self, reason):
        self.agent["alive"] = False

        print("")
        print("Agent died")
        print(reason)

        self.respawn_agent()
        print("")
