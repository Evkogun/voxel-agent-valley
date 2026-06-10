# voxel-agent-valley

This is a voxel-based environment designed to measure the degree of observation harness required to achieve different levels of goals.

## Requirements

* Python 3.9+

  * `pygame`
  * `openai`
* An OpenAI API key

Install the required Python packages:

```bash
pip install pygame openai
```

Set your OpenAI API key on Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="api_key"
```

Set your OpenAI API key on Mac/Linux:

```bash
export OPENAI_API_KEY="api_key"
```

## Running the Project

Runs the voxel world in manual mode.

```bash
python main.py
```

Runs the world with the LLM agent choosing actions.

```bash
python main.py --ai
```


## Command-Line Options

| Command          | Description                                                           |
| ---------------- | --------------------------------------------------------------------- |
| `--ai`           | Runs the world with the LLM agent choosing actions.                   |
| `--tier 0`       | Sends only basic surroundings/action information.                     |
| `--tier 1`       | Sends immediate state, inventory, surroundings and goal information. |
| `--tier 2`       | Sends local symbolic text-map vision.                                 |
| `--tier 3`       | Sends branch analysis and recent-move memory.                         |
| `--tier 4`       | Sends BFS route analysis. This is the default.                        |
| `--checkpoint N` | Starts from checkpoint N, useful for testing later sections.          |
| `--keys`         | Starts with the required keys already collected.                      |

Running `--tier` without enabling `--ai` prints a rough estimate of what the AI would receive, though this is not entirely accurate, especially for tier 3.

## Initial Development Process

### Stage 1: Choosing the Environment Style

The first goal of the project was to attempt to create a 3D environment abstract enough for the AI to understand and interact with. Through typical code, this was found to be difficult. However, inspiration came in the form of an isometric voxel game known as Monument Valley. While unfortunately this project is nowhere near the scale of that, Monument Valley provided the perfect inspiration for the agent environment.

### Stage 2: Creating the Voxel World

Creation of the environment was another issue. Manually assigning blocks was too difficult, so a level designer had to be found. The best candidate was MagicaVoxel, as it exported in a format that could relatively easily be converted into a processable cubes, not faces. It had the added bonus of storing a colour palette that was easily accessible.

This had the advantage of flexibility, as any colour within `255, 255, 255, 255` could match to any type of in game asset, not limited by colour, shape or functionality. If the scope of the project allowed for it, the environment could include shapes other than cubes.

### Stage 3: Adding Player Movement and Tile Behaviour

Once the game environment was designed, a player operated character was inserted. Initially, this moved through the typical interact, turn and move forward harness. However, for the purposes of testing, this seemed unnecessarily clunky.

Dividing up the movement actions further into climb, drop, etc. was briefly considered to expand the agent action space. However, this proved too challenging for little benefit.

After the introduction of movement, tile behaviour came to the forefront, as the agent needed a world with meaningful constraints rather than just an open grid. The agent needed to execute actions and deal with consequences such as locked doors and hazardous tiles.

### Stage 4: Integrating the LLM Agent

The next major step was integrating `Agent.py`. The LLM agent was given an observation of the current game state and asked to return one action from a limited action space.

This simplified harness made it easier to reason with and reduced ambiguity in the agent's output, though it did sometimes say one direction and give another.

### Stage 5: Improving the Observation Format

After the first version, the main challenge became deciding what information the LLM needed. This started off as the agent's current position, inventory and nearby tiles, but later evolved into goal distances and directions, updating objective markers, recent positions and later periodic images.

Unfortunately, this proved to be both expensive and ineffective. Instead, a low level character based map system was implemented and this became the basis for the second level of AI observation.

### Stage 6: Adding Lookahead and Branch Analysis

Another tier of harness was needed. Low level LLMs could not parse the map and needed information interpreted more directly without overwhelming token limits. This manifested specifically in the maze, where the AI would backtrack, pick the wrong direction or get stuck in loops.

Allowing the AI to look ahead and path to the next junction or other significant tiles, increased the scope of its decision making. This became the basis for the third level of observation.

Unfortunately, no matter how much this system was improved, the agent struggled in environments with more than one junction or increased verticality.

### Stage 7: Debugging Agent Decision-Making

A large part of the process involved fixing cases where the agent made plausible but incorrect decisions or weighed certain parts of the prompting too highly.

For example, the AI frequently could not handle open spaces and would backtrack unnecessarily, avoid junctions, misread stairs, fail to understand ladders or struggle to choose between similar paths. This was solved through providing the AI with an immediate memory of visited tiles and through `exploration_score`, which prioritised unexplored and mission critical cubes.

A large issue was preserving the autonomy of the AI and not making decisions for it. For example, convincing the AI to pick up an adjacent key was more difficult than anticipated.

### Stage 8: Adding BFS Route Analysis

Later, I added BFS for deeper lookahead. This allowed the system to analyse and weigh nearby choices beyond the four closest junctions, presenting the LLM with a more accurate picture of its environment.

This became one of the most critical advancements, as it allowed the AI to make longer term plans about which directions yielded the best results.

I grew concerned at the decreasing autonomy of the AI, so I allowed the AI to tiebreak between similar results and provided up to two other points of interest when scanning.

### Stage 9: Refactoring and Final Structure

After all of the observation modes were complete, I worked on reorganising the codebase into separate files for modularity and readability. Logic was separated into different files and later different folders.

I also added a shared game state structure to avoid repeatedly passing or calling common variables. Finally, I divided up the code and prompts into observability levels and added a way to mock agent input in a format that was readable to the user.

## What Worked

The most effective approach was giving the LLM structured observations rather than relying on image understanding or long winded text descriptions. The agent performed better when the environment preprocessed important facts, such as valid moves, tile types, goal distance, recent positions and branch outcomes.

The limited action space also helped. By forcing the model to choose from a small set of valid commands, the system became easier to validate and debug.

## Final Design

The final design uses the environment to translate the voxel world into compact, structured observations, then lets the LLM choose an action. The environment remains responsible for enforcing physics, collision, item pickup, hazards and movement rules, while the LLM is responsible for choosing the next action based on the state summary.

# Note on AI Use

AI assistance was used to support parts of the development process, including generating and refining LLM prompts, improving documentation wording, and helping with small repetitive or boilerplate tasks. The main design decisions, code structure, debugging process, and final implementation were carried out and reviewed by me.