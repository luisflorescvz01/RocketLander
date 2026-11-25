"""Step 2: a rocket that falls under gravity and stops at the ground."""

import pygame

# --- Settings -------------------------------------------------------------
WIDTH, HEIGHT = 800, 600     # Window size in pixels.
FPS = 60                     # Frames per second we aim for.
GROUND_Y = HEIGHT - 60       # Pixel row where the ground starts (y grows downward).

SKY_COLOR = (225, 235, 240)  # Colors are (red, green, blue), each 0-255.
GROUND_COLOR = (90, 100, 105)
ROCKET_COLOR = (240, 180, 50)            # NEW
TEXT_COLOR = (30, 40, 45)                # NEW

# --- Physics (all in meters, seconds, and "up is positive") ---------------  NEW
DT = 1 / FPS                 # Time step: seconds simulated per frame.       NEW
GRAVITY = 9.81               # Downward acceleration, m/s².                  NEW
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.     NEW
ROCKET_WIDTH = 2.0           # m                                             NEW
ROCKET_HEIGHT = 8.0          # m                                             NEW
PIXELS_PER_METER = 10        # Screen scale: 1 m is drawn as 10 pixels.      NEW


def to_screen_y(height_m):                                                  # NEW
    """Convert a height in meters (up = +) to a pixel row (down = +)."""
    return GROUND_Y - height_m * PIXELS_PER_METER


def main():
    pygame.init()                                     # Start pygame's modules.
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # Open the window.
    pygame.display.set_caption("RocketLander")
    clock = pygame.time.Clock()                       # Keeps the loop at a steady speed.
    font = pygame.font.SysFont("consolas", 18)        # NEW: for the on-screen numbers.

    # The rocket's state: everything we need to know about it right now.   NEW
    y = START_HEIGHT     # Height of the rocket's bottom above the ground, m.
    vy = 0.0             # Vertical velocity, m/s (negative = falling).
    time = 0.0           # Simulated seconds since the start.
    on_ground = False
    impact_speed = None  # Speed at the moment it hits the ground.

    running = True
    while running:
        # 1. Handle events: things the player did since the last frame.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:             # The window's X button.
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # 2. Update the game state: one physics step of DT seconds.        NEW
        if not on_ground:
            vy = vy - GRAVITY * DT    # Gravity changes the velocity...
            y = y + vy * DT           # ...and velocity changes the position.
            time = time + DT
            if y <= 0:                # Reached (or passed) the ground this step.
                impact_speed = abs(vy)
                y = 0.0
                vy = 0.0
                on_ground = True

        # 3. Draw: paint everything again, back to front.
        screen.fill(SKY_COLOR)
        pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))

        # The rocket: a rectangle centered horizontally, its bottom at height y.  NEW
        width_px = ROCKET_WIDTH * PIXELS_PER_METER
        height_px = ROCKET_HEIGHT * PIXELS_PER_METER
        left = WIDTH / 2 - width_px / 2
        top = to_screen_y(y) - height_px        # Rect is drawn from its top-left corner.
        pygame.draw.rect(screen, ROCKET_COLOR, (left, top, width_px, height_px))

        # On-screen readout so we can check the physics.                   NEW
        lines = [f"time    {time:5.2f} s",
                 f"height  {y:5.1f} m",
                 f"speed   {vy:+6.1f} m/s"]
        if impact_speed is not None:
            lines.append(f"impact  {impact_speed:5.1f} m/s")
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, TEXT_COLOR), (15, 15 + i * 22))

        pygame.display.flip()                         # Show the finished frame.

        clock.tick(FPS)                               # Wait so we run at most FPS frames per second.

    pygame.quit()                                     # Close the window cleanly.


if __name__ == "__main__":
    main()
