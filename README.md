# voxel-agent-valley

Requirements
- Python 3.9+
- 'pygame'
- 'openai'
- An OpenAI API key

bash command:
pip install pygame openai

Set OpenAI API key on Windows PowerShell:
$env OPENAI_API_KEY="api_key"

mac
export OPENAI_API_KEY="api_key"

python main.py	    Runs the voxel world in manual mode.
--ai            	Runs the world with the LLM agent choosing actions.
--tier 0	        Sends only basic surroundings/action information.
--tier 1	        Sends immediate state, inventory, surroundings and goal information.
--tier 2	        Sends local symbolic text-map vision.
--tier 3	        Sends branch analysis and recent-move memory.
--tier 4	        Sends BFS route analysis. This is the default.
--checkpoint N	    Starts from checkpoint N, useful for testing later sections.
--keys	            Starts with required keys already collected.

Running --tier without enabling ai prints a rough estimate of what the ai would recieve (though not entirely accurate especially tier 3)

Initial development process

The first goal of the project was to attempt to create a 3d environment abstract enough for the ai to understand and interact with, through typical code this was found to be difficult however inspiration came in the form of a isometric voxel game known an monument valley, while unfortunately this project is nowhere near the scale of that it, monument valley provided the perfect inspiration for the agent environment.

Creation of the environment was another issue, manually assigning blocks was too difficult so a level designer had to be found, the best candidate was MagicaVoxel as it exported in a format that could relatively easy be converted into a processable format (not faces but cubes), it had the added bonus of storing a colour palette that was easily accessible. This had the advantage of flexibility as any colour within 255, 255, 255, 255 could match to any type of in game asset, not limited by colour, shape or functionality and if the scope of the project allowed for it the environment could include shapes other than cubes!

Once the game environment was designed a player operated character was inserted, initially this moved through the typical interact, turn and move forward harness, however for the purposes of testing this seemed unnecessarily clunky. Dividing up the movement actions further into climb and drop ect were briefly considered to expand the agent action space however this proved too challenging for little benefit. After the introduction of movement, tile behavior came to the forefront as the agent needed a world with meaningful constraints rather than just an open grid. The agent needed to exact actions and deal with consequences such as locked doors and hazardous tiles.

The next major step was integrating Agent.py, the LLM agent was given an observation of the current game state and asked to return one action from a limited action space. This simplified harness made it easier to reason with and reduced ambiguity in the agents output (though it did sometimes say one direction and give another).

After the first version, the main challenge became how to decide what information the LLM needed