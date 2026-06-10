from level import Render

# Stores the voxel colours that are used as object types in a mapping table
# These were manually pulled from the program, the long term plan is to have this implemented in the Render module to allow customisation of level colour palettes
COLOUR_TO_TYPE = {
    (238, 0, 0): "spawn",
    (0, 238, 0): "checkpoint",
    (238, 238, 238): "path",
    (0, 0, 238): "stairs",
    (0, 0, 119): "ladder",
    (51, 0, 51): "key1",
    (51, 0, 102): "key2",
    (153, 102, 0): "door",
    (170, 170, 170): "ledge",
    (255, 255, 0): "hazard",
    (153, 153, 51): "toggleable_hazard",
    (51, 0, 0): "timed_pressure_plate",
    (153, 204, 255): "death_tile",
    (0, 136, 0): "goal",
}

# Colour Palette
TYPE_TO_RENDER_COLOUR = {
    "spawn": (255, 105, 97),
    "checkpoint": (120, 220, 140),
    "path": (250, 240, 218),
    "stairs": (90, 130, 210),
    "ladder": (55, 85, 150),
    "key1": (155, 95, 220),
    "key2": (105, 75, 190),
    "door": (145, 95, 50),
    "ledge": (170, 175, 175),
    "hazard": (245, 180, 65),
    "toggleable_hazard": (185, 170, 95),
    "timed_pressure_plate": (120, 55, 55),
    "death_tile": (88, 160, 192),
    "goal": (70, 200, 120),
    "unknown": (255, 0, 255),
}

# 4 byte integer vox reader
def read_int(data, offset):
    # VOX chunk sizes are stored as little endian (backwards by byte) 32 bit integers
    int_bytes = data[offset:offset + 4]
    return int.from_bytes(int_bytes, byteorder="little", signed=True)

# Converts an RGB colour into a tile type
def get_type_from_colour(colour):
    return COLOUR_TO_TYPE.get(colour, "unknown")

def get_render_colour_from_type(tile_type):
    return TYPE_TO_RENDER_COLOUR.get(tile_type, Render.CUBE_TOP_COLOUR)

# Reads voxel positions and palette colours from a Vox file
def read_vox_file(path):
    with open(path, "rb") as file:
        data = file.read()

    offset = 8 # For readability
    voxels = [] # Stores the co-ords and *Palette index of the cubes
    palette = None # This storage format has a list of used colours stored in a palette that have to be retrieved
    # XYZI, I stands for index of which position in the palette corresponds to the cube colour
    # They index in the non python way

    # Reads through each chunk stored in the vox file
    while offset < len(data):
        # Offset stores where in the file we are
        # This identifies what type of chunk we are reading (XYZI or RGBA)
        chunk_id = data[offset:offset + 4].decode("ascii", errors="ignore")
        offset += 4

        content_size = read_int(data, offset)
        offset += 4

        children_size = read_int(data, offset)
        offset += 4

        content_end = offset + content_size

        '''
        Vox chunk layout
       
        chunk_id, 
        content_size, 
        children_size

        each 4 bytes
        
        Then content
        '''

        # XYZI stores the actual cube positions + index
        # Statement for XYZI chunks
        if chunk_id == "XYZI":
            # The first 4 bytes of XYZI chunks is the number of voxels
            num_voxels = read_int(data, offset)
            offset += 4

            for voxel_number in range(num_voxels):
                x = data[offset]
                y = data[offset + 1]
                z = data[offset + 2]
                colour_index = data[offset + 3]
                offset += 4

                voxels.append(
                    {
                        "x": x,
                        "y": y,
                        "z": z,
                        "colour_index": colour_index,
                    }
                )

        # RGBA stores the colour palette used by the cubes
        # Statement for RGBA chunks
        elif chunk_id == "RGBA":
            palette = []
            for _ in range(256): # Colour ranges from 0-255
                r = data[offset]
                g = data[offset + 1]
                b = data[offset + 2]
                a = data[offset + 3]
                offset += 4

                palette.append((r, g, b))

        # Skips uneeded chunks
        else: offset = content_end

    # Adds actual RGB colours and types to every stored cube (Palette index -> RGB colour --> type)
    for voxel in voxels:
        if palette is not None:
            # MagicaVoxel colour indexes start at 1
            palette_index = max(0, voxel["colour_index"] - 1)
            voxel["colour"] = palette[palette_index]
        else:
            voxel["colour"] = Render.CUBE_TOP_COLOUR # Generic fallback cube colour defined in Render

        voxel["source_colour"] = voxel["colour"]
        voxel["type"] = get_type_from_colour(voxel["source_colour"])
        voxel["colour"] = get_render_colour_from_type(voxel["type"])
    return voxels


# Converts raw vox data into something usable for main
def load_vox_cubes(path, level_size):

    raw_voxels = read_vox_file(path)
    cubes = [] # List to store every cube
    cube_map = {} # List to store cubes by position
    spawn_position = None # Where the spawn point for the player is (1 cube of this type only))

    level_offset = level_size // 2

    for voxel in raw_voxels:
        # Centre the MagicaVoxel coordinates around world origin
        x = voxel["x"] - level_offset
        y = voxel["y"] - level_offset
        z = voxel["z"]

        cube = {
            "x": x,
            "y": y,
            "z": z,
            "colour": voxel["colour"],
            "source_colour": voxel["source_colour"], # Only used in level creation so logic isn't impacted
            "colour_index": voxel["colour_index"],
            "type": voxel["type"],
        }

        cubes.append(cube)
        cube_map[(x, y, z)] = cube

        if cube["type"] == "spawn": # Sets spawn postition is found, if multiple instances set most recent
            spawn_position = [x, y, z + 1]

    return cubes, cube_map, spawn_position