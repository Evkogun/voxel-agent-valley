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

Creation of the environment was another issue, manually asigning blocks was too difficult