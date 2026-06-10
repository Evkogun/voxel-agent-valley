import pygame

BACKGROUND_TOP = (228, 220, 234)
BACKGROUND_BOTTOM = (170, 155, 195)

# Generic set colours
CUBE_TOP_COLOUR = (120, 180, 255)
CUBE_LEFT_COLOUR = (90, 140, 210)
CUBE_RIGHT_COLOUR = (70, 110, 170)
CUBE_OUTLINE = (85, 95, 100)
TEXT_COLOUR = (20, 20, 20)

TILE_W = 32
TILE_H = 16
CUBE_HEIGHT = 16

WIDTH = 600
HEIGHT = 600

MIDDLE_X = WIDTH // 2
MIDDLE_Y = HEIGHT // 2 - 50

# Height lighting variation, used to distinguish different levels when perspectively next to each other
LOWEST_LEVEL = 0
HIGHEST_LEVEL = 12
LOW_LEVEL_DARKNESS = 0.85
HIGH_LEVEL_LIGHTNESS = 1.08


# Converts 3d world co-ordinates into 2d screen isometric co-ordinates
# xyz -> xy
# Basically an xyz axis gizmo
# X is down right, Y is down left, Z is up
def iso_project(x, y, z, origin_x = MIDDLE_X, origin_y = MIDDLE_Y):
    screen_x = origin_x + (x - y) * (TILE_W // 2) # TILE_W/H is divided since moving in isometric, so half the distance
    screen_y = origin_y + (x + y) * (TILE_H // 2) - z * CUBE_HEIGHT
    return screen_x, screen_y


# Creates and returns an array that stores the co-ordinates of the diamonds that make up a cube
def cube_faces(lx, ly, w = TILE_W, h = TILE_H, height = CUBE_HEIGHT):
    half_w = w // 2
    half_h = h // 2

    top = [
        (lx, ly - half_h),
        (lx + half_w, ly),
        (lx, ly + half_h),
        (lx - half_w, ly),
    ]

    left = [
        top[3],
        top[2],
        (top[2][0], top[2][1] + height),
        (top[3][0], top[3][1] + height),
    ]

    right = [
        top[1],
        top[2],
        (top[2][0], top[2][1] + height),
        (top[1][0], top[1][1] + height),
    ]

    return top, left, right

# Shades a colour by a factor (0.5 = half as bright, 2 = twice as bright)
def shade_colour(colour, factor):
    r, g, b = colour
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
    )


# Applies height lighting to a colour
def apply_height_lighting(colour, z):

    if HIGHEST_LEVEL == LOWEST_LEVEL: return colour # If height lighting is disabled

    height_range = HIGHEST_LEVEL - LOWEST_LEVEL
    height_position = (z - LOWEST_LEVEL) / height_range # Converts z into a 0 - 1 range

    height_position = max(0, min(1, height_position)) # Clamps height position to 0 - 1 range

    light_range = HIGH_LEVEL_LIGHTNESS - LOW_LEVEL_DARKNESS # Darkest to lightest difference
    light_factor = LOW_LEVEL_DARKNESS + height_position * light_range

    return shade_colour(colour, light_factor)


# Draws a cube at world co ordinates
def draw_cube(
    screen, x, y, z,
    top_colour = CUBE_TOP_COLOUR,
    left_colour = None,
    right_colour = None,
    origin_x = MIDDLE_X,
    origin_y = MIDDLE_Y,
    draw_outline = True,
):
    
    # Makes low cubes slightly darker and high cubes slightly lighter
    top_colour = apply_height_lighting(top_colour, z)

    # If there is no input for the left/right colour just make them darker versions of the top colour
    # Otherwise apply height lighting to them as well
    if left_colour is None: left_colour = shade_colour(top_colour, 0.78)
    else: left_colour = apply_height_lighting(left_colour, z)

    if right_colour is None: right_colour = shade_colour(top_colour, 0.66)
    else: right_colour = apply_height_lighting(right_colour, z)

    lx, ly = iso_project(x, y, z, origin_x, origin_y) # Screen co-ords
    top, left, right = cube_faces(lx, ly)

    # Draw side faces
    pygame.draw.polygon(screen, left_colour, left)
    pygame.draw.polygon(screen, right_colour, right)
    pygame.draw.polygon(screen, top_colour, top)

    # Prevents water/boundary tiles from having outlines to distinguish them from normal cubes and reduce visual strain
    if not draw_outline: return

    # Outlines
    pygame.draw.polygon(screen, CUBE_OUTLINE, left, 1)
    pygame.draw.polygon(screen, CUBE_OUTLINE, right, 1)
    pygame.draw.polygon(screen, CUBE_OUTLINE, top, 1)


# Draws a simple agent marker above the cube it is standing on
def draw_agent(screen, x, y, z, origin_x=MIDDLE_X, origin_y=MIDDLE_Y):

    shadow_x, shadow_y = iso_project(x, y, z - 1, origin_x, origin_y)
    # Draws a small shadow below the character
    pygame.draw.ellipse(
        screen,
        (70, 70, 70),
        (
            shadow_x - 8,
            shadow_y - 3,
            16, 6,
        ),
    )

    lx, ly = iso_project(x, y, z, origin_x, origin_y)

    pygame.draw.circle(screen, (170, 45, 55), (lx, ly), 6)
    pygame.draw.circle(screen, (235, 75, 80), (lx, ly), 4)


def draw_background_gradient(screen):
    for y in range(HEIGHT):
        blend = y / HEIGHT

        r = int(BACKGROUND_TOP[0] + (BACKGROUND_BOTTOM[0] - BACKGROUND_TOP[0]) * blend)
        g = int(BACKGROUND_TOP[1] + (BACKGROUND_BOTTOM[1] - BACKGROUND_TOP[1]) * blend)
        b = int(BACKGROUND_TOP[2] + (BACKGROUND_BOTTOM[2] - BACKGROUND_TOP[2]) * blend)

        pygame.draw.line(screen, (r, g, b), (0, y), (WIDTH, y))