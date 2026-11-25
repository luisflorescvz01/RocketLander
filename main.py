"""Step 3: an engine with throttle, thrust and fuel that fights gravity."""

import pygame

# --- Settings -------------------------------------------------------------
WIDTH, HEIGHT = 800, 600     # Window size in pixels.
FPS = 60                     # Frames per second we aim for.
GROUND_Y = HEIGHT - 60       # Pixel row where the ground starts (y grows downward).

SKY_COLOR = (225, 235, 240)  # Colors are (red, green, blue), each 0-255.
GROUND_COLOR = (90, 100, 105)
ROCKET_COLOR = (240, 180, 50)
FLAME_COLOR = (255, 120, 30)             # NEW
TEXT_COLOR = (30, 40, 45)

# --- Physics (all in meters, seconds, and "up is positive") ---------------
DT = 1 / FPS                 # Time step: seconds simulated per frame.
GRAVITY = 9.81               # Downward acceleration, m/s².
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.
ROCKET_WIDTH = 2.0           # m
ROCKET_HEIGHT = 8.0          # m
PIXELS_PER_METER = 10        # Screen scale: 1 m is drawn as 10 pixels.

# --- Engine ----------------------------------------------------------------  NEW
DRY_MASS = 80.0              # Mass of the empty rocket, kg.                  NEW
START_FUEL = 30.0            # Fuel on board at the start, kg.                NEW
MAX_THRUST = 2200.0          # Engine force at 100% throttle, newtons.        NEW
MAX_FUEL_FLOW = 1.375        # Fuel burned per second at 100% throttle, kg/s. NEW
THROTTLE_RATE = 0.5          # How fast W/S move the throttle, per second.    NEW


def to_screen_y(height_m):
    """Convert a height in meters (up = +) to a pixel row (down = +)."""
    return GROUND_Y - height_m * PIXELS_PER_METER


def main():
    pygame.init()                                     # Start pygame's modules.
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # Open the window.
    pygame.display.set_caption("RocketLander")
    clock = pygame.time.Clock()                       # Keeps the loop at a steady speed.
    font = pygame.font.SysFont("consolas", 18)        # For the on-screen numbers.

    # The rocket's state: everything we need to know about it right now.
    y = START_HEIGHT     # Height of the rocket's bottom above the ground, m.
    vy = 0.0             # Vertical velocity, m/s (negative = falling).
    time = 0.0           # Simulated seconds since the start.
    on_ground = False
    impact_speed = None  # Speed at the moment it hits the ground.
    throttle = 0.0       # NEW: engine setting, 0.0 (off) to 1.0 (full).
    fuel = START_FUEL    # NEW: kg left in the tank.

    running = True
    while running:
        # 1. Handle events: things the player did since the last frame.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:             # The window's X button.
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # NEW: Held keys. Events say "W was pressed"; get_pressed() says "W is down now".
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            throttle = throttle + THROTTLE_RATE * DT
        if keys[pygame.K_s]:
            throttle = throttle - THROTTLE_RATE * DT
        throttle = min(1.0, max(0.0, throttle))       # NEW: keep it between 0 and 1.

        # 2. Update the game state: one physics step of DT seconds.
        if on_ground:
            throttle = 0.0                            # NEW: engine off once down.
        else:
            # NEW: the engine only pushes while there is fuel left.
            thrust = throttle * MAX_THRUST if fuel > 0 else 0.0
            mass = DRY_MASS + fuel                    # NEW: lighter as fuel burns.
            acceleration = thrust / mass - GRAVITY    # NEW: a = F / m, minus gravity.
            fuel = max(0.0, fuel - throttle * MAX_FUEL_FLOW * DT)  # NEW

            vy = vy + acceleration * DT   # Acceleration changes the velocity...
            y = y + vy * DT               # ...and velocity changes the position.
            time = time + DT
            if y <= 0:                # Reached (or passed) the ground this step.
                impact_speed = abs(vy)
                y = 0.0
                vy = 0.0
                on_ground = True

        # 3. Draw: paint everything again, back to front.
        screen.fill(SKY_COLOR)
        pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))

        # The rocket: a rectangle centered horizontally, its bottom at height y.
        width_px = ROCKET_WIDTH * PIXELS_PER_METER
        height_px = ROCKET_HEIGHT * PIXELS_PER_METER
        left = WIDTH / 2 - width_px / 2
        bottom = to_screen_y(y)
        top = bottom - height_px                # Rect is drawn from its top-left corner.

        # NEW: the flame, a triangle under the rocket that grows with throttle.
        if throttle > 0 and fuel > 0:
            flame_length = throttle * 4.0 * PIXELS_PER_METER    # Up to 4 m long.
            center = WIDTH / 2
            pygame.draw.polygon(screen, FLAME_COLOR, [
                (center - width_px / 3, bottom),
                (center + width_px / 3, bottom),
                (center, bottom + flame_length),
            ])
        pygame.draw.rect(screen, ROCKET_COLOR, (left, top, width_px, height_px))

        # On-screen readout so we can check the physics.
        weight = (DRY_MASS + fuel) * GRAVITY                    # NEW
        lines = [f"time      {time:5.2f} s",
                 f"height    {y:5.1f} m",
                 f"speed     {vy:+6.1f} m/s",
                 f"throttle  {throttle:5.0%}   (W / S)",      # NEW
                 f"fuel      {fuel:5.1f} kg",                # NEW
                 f"max TWR   {MAX_THRUST / weight:5.2f}"]    # NEW
        if impact_speed is not None:
            lines.append(f"impact    {impact_speed:5.1f} m/s")
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, TEXT_COLOR), (15, 15 + i * 22))

        pygame.display.flip()                         # Show the finished frame.

        clock.tick(FPS)                               # Wait so we run at most FPS frames per second.

    pygame.quit()                                     # Close the window cleanly.


if __name__ == "__main__":
    main()
