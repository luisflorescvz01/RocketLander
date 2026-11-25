"""Step 4: landing rules and a restart key."""

import pygame

# --- Settings -------------------------------------------------------------
WIDTH, HEIGHT = 800, 600     # Window size in pixels.
FPS = 60                     # Frames per second we aim for.
GROUND_Y = HEIGHT - 60       # Pixel row where the ground starts (y grows downward).

SKY_COLOR = (225, 235, 240)  # Colors are (red, green, blue), each 0-255.
GROUND_COLOR = (90, 100, 105)
ROCKET_COLOR = (240, 180, 50)
FLAME_COLOR = (255, 120, 30)
TEXT_COLOR = (30, 40, 45)
WRECK_COLOR = (110, 60, 50)              # NEW
LANDED_COLOR = (20, 120, 80)             # NEW
CRASHED_COLOR = (180, 50, 40)            # NEW

# --- Physics (all in meters, seconds, and "up is positive") ---------------
DT = 1 / FPS                 # Time step: seconds simulated per frame.
GRAVITY = 9.81               # Downward acceleration, m/s².
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.
ROCKET_WIDTH = 2.0           # m
ROCKET_HEIGHT = 8.0          # m
PIXELS_PER_METER = 10        # Screen scale: 1 m is drawn as 10 pixels.

# --- Engine ----------------------------------------------------------------
DRY_MASS = 80.0              # Mass of the empty rocket, kg.
START_FUEL = 30.0            # Fuel on board at the start, kg.
MAX_THRUST = 2200.0          # Engine force at 100% throttle, newtons.
MAX_FUEL_FLOW = 1.375        # Fuel burned per second at 100% throttle, kg/s.
THROTTLE_RATE = 0.5          # How fast W/S move the throttle, per second.

# --- Rules -----------------------------------------------------------------  NEW
SAFE_SPEED = 5.0             # Touch down slower than this to land, m/s.      NEW


class Rocket:                                                               # NEW
    """Everything we need to know about the rocket right now, in one place."""

    def __init__(self):
        # Runs when we write Rocket(): sets up a fresh rocket at the start.
        self.y = START_HEIGHT     # Height of the rocket's bottom above the ground, m.
        self.vy = 0.0             # Vertical velocity, m/s (negative = falling).
        self.time = 0.0           # Simulated seconds since the start.
        self.status = "flying"    # NEW: "flying", "landed" or "crashed".
        self.impact_speed = None  # Speed at the moment it hits the ground.
        self.throttle = 0.0       # Engine setting, 0.0 (off) to 1.0 (full).
        self.fuel = START_FUEL    # kg left in the tank.


def to_screen_y(height_m):
    """Convert a height in meters (up = +) to a pixel row (down = +)."""
    return GROUND_Y - height_m * PIXELS_PER_METER


def main():
    pygame.init()                                     # Start pygame's modules.
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # Open the window.
    pygame.display.set_caption("RocketLander")
    clock = pygame.time.Clock()                       # Keeps the loop at a steady speed.
    font = pygame.font.SysFont("consolas", 18)        # For the on-screen numbers.
    big_font = pygame.font.SysFont("consolas", 48, bold=True)  # NEW: for LANDED / CRASHED.

    rocket = Rocket()    # NEW: replaces the seven separate state variables.

    running = True
    while running:
        # 1. Handle events: things the player did since the last frame.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:             # The window's X button.
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                rocket = Rocket()                     # NEW: restart = a brand-new rocket.

        # Held keys. Events say "W was pressed"; get_pressed() says "W is down now".
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            rocket.throttle = rocket.throttle + THROTTLE_RATE * DT
        if keys[pygame.K_s]:
            rocket.throttle = rocket.throttle - THROTTLE_RATE * DT
        rocket.throttle = min(1.0, max(0.0, rocket.throttle))  # Keep it between 0 and 1.

        # 2. Update the game state: one physics step of DT seconds.
        if rocket.status != "flying":                # NEW: was "if rocket.on_ground:".
            rocket.throttle = 0.0                     # Engine off once down.
        else:
            # The engine only pushes while there is fuel left.
            thrust = rocket.throttle * MAX_THRUST if rocket.fuel > 0 else 0.0
            mass = DRY_MASS + rocket.fuel             # Lighter as fuel burns.
            acceleration = thrust / mass - GRAVITY    # a = F / m, minus gravity.
            rocket.fuel = max(0.0, rocket.fuel - rocket.throttle * MAX_FUEL_FLOW * DT)

            rocket.vy = rocket.vy + acceleration * DT  # Acceleration changes the velocity...
            rocket.y = rocket.y + rocket.vy * DT       # ...and velocity changes the position.
            rocket.time = rocket.time + DT
            if rocket.y <= 0:         # Reached (or passed) the ground this step.
                rocket.impact_speed = abs(rocket.vy)
                rocket.y = 0.0
                rocket.vy = 0.0
                # NEW: the rule that decides the outcome of the flight.
                if rocket.impact_speed < SAFE_SPEED:
                    rocket.status = "landed"
                else:
                    rocket.status = "crashed"

        # 3. Draw: paint everything again, back to front.
        screen.fill(SKY_COLOR)
        pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))

        # The rocket: a rectangle centered horizontally, its bottom at height y.
        width_px = ROCKET_WIDTH * PIXELS_PER_METER
        height_px = ROCKET_HEIGHT * PIXELS_PER_METER
        left = WIDTH / 2 - width_px / 2
        bottom = to_screen_y(rocket.y)
        top = bottom - height_px                # Rect is drawn from its top-left corner.

        # The flame, a triangle under the rocket that grows with throttle.
        if rocket.throttle > 0 and rocket.fuel > 0:
            flame_length = rocket.throttle * 4.0 * PIXELS_PER_METER    # Up to 4 m long.
            center = WIDTH / 2
            pygame.draw.polygon(screen, FLAME_COLOR, [
                (center - width_px / 3, bottom),
                (center + width_px / 3, bottom),
                (center, bottom + flame_length),
            ])
        body_color = WRECK_COLOR if rocket.status == "crashed" else ROCKET_COLOR   # NEW
        pygame.draw.rect(screen, body_color, (left, top, width_px, height_px))

        # On-screen readout so we can check the physics.
        weight = (DRY_MASS + rocket.fuel) * GRAVITY
        lines = [f"time      {rocket.time:5.2f} s",
                 f"height    {rocket.y:5.1f} m",
                 f"speed     {rocket.vy:+6.1f} m/s",
                 f"throttle  {rocket.throttle:5.0%}   (W / S)",
                 f"fuel      {rocket.fuel:5.1f} kg",
                 f"max TWR   {MAX_THRUST / weight:5.2f}"]
        if rocket.impact_speed is not None:
            lines.append(f"impact    {rocket.impact_speed:5.1f} m/s")
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, TEXT_COLOR), (15, 15 + i * 22))

        # NEW: the result, centered on screen, once the flight is over.
        if rocket.status != "flying":
            title = "LANDED" if rocket.status == "landed" else "CRASHED"
            color = LANDED_COLOR if rocket.status == "landed" else CRASHED_COLOR
            message = big_font.render(title, True, color)
            hint = font.render("Press R to restart", True, TEXT_COLOR)
            # get_rect(center=...) positions an image by its middle instead of its corner.
            screen.blit(message, message.get_rect(center=(WIDTH / 2, HEIGHT / 3)))
            screen.blit(hint, hint.get_rect(center=(WIDTH / 2, HEIGHT / 3 + 45)))

        pygame.display.flip()                         # Show the finished frame.

        clock.tick(FPS)                               # Wait so we run at most FPS frames per second.

    pygame.quit()                                     # Close the window cleanly.


if __name__ == "__main__":
    main()
