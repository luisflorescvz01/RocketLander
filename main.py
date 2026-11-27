"""Step 5: 2D motion, rotation and engine gimbal steering."""

import math

import pygame

# --- Settings -------------------------------------------------------------
WIDTH, HEIGHT = 800, 600     # Window size in pixels.
FPS = 60                     # Frames per second we aim for.
GROUND_Y = HEIGHT - 60       # Pixel row where the ground starts (y grows downward).

SKY_COLOR = (225, 235, 240)  # Colors are (red, green, blue), each 0-255.
GROUND_COLOR = (90, 100, 105)
ROCKET_COLOR = (240, 180, 50)
FLAME_COLOR = (255, 120, 30)
NOZZLE_COLOR = (40, 45, 50)              # NEW
TEXT_COLOR = (30, 40, 45)
WRECK_COLOR = (110, 60, 50)
LANDED_COLOR = (20, 120, 80)
CRASHED_COLOR = (180, 50, 40)

# --- Physics (all in meters, seconds, and "up is positive") ---------------
DT = 1 / FPS                 # Time step: seconds simulated per frame.
GRAVITY = 9.81               # Downward acceleration, m/s².
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.
START_X = -15.0              # Starting sideways position, m (0 = screen center, + = right).
START_VX = 2.0               # Starting sideways velocity, m/s (+ = moving right).
ROCKET_WIDTH = 2.0           # m
ROCKET_HEIGHT = 8.0          # m
PIXELS_PER_METER = 10        # Screen scale: 1 m is drawn as 10 pixels.

# --- Engine ----------------------------------------------------------------
DRY_MASS = 80.0              # Mass of the empty rocket, kg.
START_FUEL = 30.0            # Fuel on board at the start, kg.
MAX_THRUST = 2200.0          # Engine force at 100% throttle, newtons.
MAX_FUEL_FLOW = 1.375        # Fuel burned per second at 100% throttle, kg/s.
THROTTLE_RATE = 0.5          # How fast W/S move the throttle, per second.
MAX_GIMBAL = math.radians(12)    # NEW: furthest the nozzle can swivel, each way.
GIMBAL_RATE = math.radians(30)   # NEW: how fast the nozzle swivels, per second.
NOZZLE_ARM = ROCKET_HEIGHT / 2   # NEW: distance from the center down to the nozzle, m.

# --- Rules -----------------------------------------------------------------
SAFE_SPEED = 5.0             # Touch down slower than this to land, m/s (now total speed).
SAFE_ANGLE = math.radians(15)    # NEW: touch down within this tilt of upright.


class Rocket:
    """Everything we need to know about the rocket right now, in one place."""

    def __init__(self):
        # Runs when we write Rocket(): sets up a fresh rocket at the start.
        self.x = START_X          # Sideways position of the rocket's center, m.
        self.vx = START_VX        # Sideways velocity, m/s (+ = moving right).
        self.y = START_HEIGHT + ROCKET_HEIGHT / 2   # NEW: height of the rocket's CENTER, m.
        self.vy = 0.0             # Vertical velocity, m/s (negative = falling).
        self.angle = 0.0          # NEW: tilt in radians. 0 = upright, + = nose leans right.
        self.spin = 0.0           # NEW: how fast the angle changes, radians/s (+ = clockwise).
        self.gimbal = 0.0         # NEW: nozzle swivel in radians (+ = nozzle swung right).
        self.time = 0.0           # Simulated seconds since the start.
        self.status = "flying"    # "flying", "landed" or "crashed".
        self.impact_speed = None  # Speed at the moment it hits the ground.
        self.crash_reason = None  # NEW: why a touchdown counted as a crash, for the player.
        self.throttle = 0.0       # Engine setting, 0.0 (off) to 1.0 (full).
        self.fuel = START_FUEL    # kg left in the tank.

    def to_world(self, local_x, local_y):                                   # NEW
        """Turn a point on the rocket (meters from its center, upright) into world coordinates.

        local_x is to the rocket's right, local_y toward its nose. Rotating clockwise
        by the angle uses the same sin and cos as the tilted thrust.
        """
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (self.x + local_x * c + local_y * s,
                self.y + local_y * c - local_x * s)

    def tilt(self):                                                         # NEW
        """The angle wrapped into -180°..+180°, so a full spin counts as upright again."""
        return math.remainder(self.angle, math.tau)     # tau = 2π = one full turn.

    def corners(self):                                                      # NEW
        """The body's four corners in world coordinates, clockwise from bottom-left."""
        w, h = ROCKET_WIDTH / 2, ROCKET_HEIGHT / 2
        return [self.to_world(-w, -h), self.to_world(-w, h),
                self.to_world(w, h), self.to_world(w, -h)]


def to_screen_x(x_m):
    """Convert a sideways position in meters (0 = middle) to a pixel column."""
    return WIDTH / 2 + x_m * PIXELS_PER_METER


def to_screen_y(height_m):
    """Convert a height in meters (up = +) to a pixel row (down = +)."""
    return GROUND_Y - height_m * PIXELS_PER_METER


def to_screen(point):                                                       # NEW
    """Convert a world point (x, y) in meters to a pixel position."""
    return (to_screen_x(point[0]), to_screen_y(point[1]))


def main():
    pygame.init()                                     # Start pygame's modules.
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # Open the window.
    pygame.display.set_caption("RocketLander")
    clock = pygame.time.Clock()                       # Keeps the loop at a steady speed.
    font = pygame.font.SysFont("consolas", 18)        # For the on-screen numbers.
    big_font = pygame.font.SysFont("consolas", 48, bold=True)  # For LANDED / CRASHED.

    rocket = Rocket()    # All of the rocket's state in one object.

    running = True
    while running:
        # 1. Handle events: things the player did since the last frame.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:             # The window's X button.
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                rocket = Rocket()                     # Restart = a brand-new rocket.

        # Held keys. Events say "W was pressed"; get_pressed() says "W is down now".
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            rocket.throttle = rocket.throttle + THROTTLE_RATE * DT
        if keys[pygame.K_s]:
            rocket.throttle = rocket.throttle - THROTTLE_RATE * DT
        rocket.throttle = min(1.0, max(0.0, rocket.throttle))  # Keep it between 0 and 1.

        # NEW: A/D choose where the nozzle should point; letting go means "center".
        target = (keys[pygame.K_d] - keys[pygame.K_a]) * MAX_GIMBAL
        # The nozzle can't jump there: it moves at most GIMBAL_RATE * DT per frame.
        step = GIMBAL_RATE * DT
        rocket.gimbal = rocket.gimbal + min(step, max(-step, target - rocket.gimbal))

        # 2. Update the game state: one physics step of DT seconds.
        if rocket.status != "flying":
            rocket.throttle = 0.0                     # Engine off once down.
        else:
            # The engine only pushes while there is fuel left.
            thrust = rocket.throttle * MAX_THRUST if rocket.fuel > 0 else 0.0
            mass = DRY_MASS + rocket.fuel             # Lighter as fuel burns.
            rocket.fuel = max(0.0, rocket.fuel - rocket.throttle * MAX_FUEL_FLOW * DT)

            # NEW: thrust points along the body, turned by the nozzle's swivel.
            direction = rocket.angle - rocket.gimbal
            ax = thrust * math.sin(direction) / mass              # Sideways part.
            ay = thrust * math.cos(direction) / mass - GRAVITY    # Upward part, minus gravity.

            # NEW: off-center thrust twists the rocket. Turning has its own a = F / m:
            # angular acceleration = torque / moment of inertia.
            torque = thrust * math.sin(rocket.gimbal) * NOZZLE_ARM
            inertia = mass * (ROCKET_HEIGHT ** 2 + ROCKET_WIDTH ** 2) / 12
            rocket.spin = rocket.spin + torque / inertia * DT     # Torque changes the spin...
            rocket.angle = rocket.angle + rocket.spin * DT        # ...and spin changes the angle.

            rocket.vx = rocket.vx + ax * DT            # NEW: now something pushes sideways.
            rocket.vy = rocket.vy + ay * DT            # Acceleration changes the velocity...
            rocket.y = rocket.y + rocket.vy * DT       # ...and velocity changes the position.
            rocket.x = rocket.x + rocket.vx * DT
            rocket.time = rocket.time + DT

            # NEW: touchdown happens at the lowest corner, not the middle of the bottom.
            lowest = min(corner[1] for corner in rocket.corners())
            if lowest <= 0:           # A corner reached (or passed) the ground this step.
                # NEW: total speed combines both directions (Pythagoras): √(vx² + vy²).
                rocket.impact_speed = math.hypot(rocket.vx, rocket.vy)
                rocket.y = rocket.y - lowest          # NEW: lift it so it rests on the ground.
                rocket.vy = 0.0
                rocket.vx = 0.0       # The ground stops the sideways drift too.
                rocket.spin = 0.0     # NEW: ...and the spin.
                # NEW: the rules that decide the outcome. Every rule must pass to land.
                reasons = []
                if rocket.impact_speed >= SAFE_SPEED:
                    reasons.append("too fast")
                if abs(rocket.tilt()) > SAFE_ANGLE:
                    reasons.append("too tilted")
                if reasons:
                    rocket.status = "crashed"
                    rocket.crash_reason = " and ".join(reasons)
                else:
                    rocket.status = "landed"

        # 3. Draw: paint everything again, back to front.
        screen.fill(SKY_COLOR)
        pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))

        # NEW: the nozzle and flame start at the bottom center of the rocket and point
        # opposite to the thrust: the exhaust goes one way, the rocket is pushed the other.
        nozzle = rocket.to_world(0, -ROCKET_HEIGHT / 2)
        direction = rocket.angle - rocket.gimbal
        exhaust = (-math.sin(direction), -math.cos(direction))   # Unit vector, world meters.
        across = (exhaust[1], -exhaust[0])                       # Perpendicular to it.

        def along(distance, side=0.0):
            """A point `distance` m down the exhaust from the nozzle, `side` m across."""
            return to_screen((nozzle[0] + exhaust[0] * distance + across[0] * side,
                              nozzle[1] + exhaust[1] * distance + across[1] * side))

        if rocket.throttle > 0 and rocket.fuel > 0 and rocket.status == "flying":
            flame_length = rocket.throttle * 4.0                 # Up to 4 m long.
            pygame.draw.polygon(screen, FLAME_COLOR, [
                along(0, -ROCKET_WIDTH / 3), along(0, ROCKET_WIDTH / 3), along(flame_length)])
        # The nozzle: a short dark line that shows which way the engine is swiveled.
        pygame.draw.line(screen, NOZZLE_COLOR, along(0), along(1.0), 4)

        # NEW: the body is now a rotated polygon from its four corners.
        body_color = WRECK_COLOR if rocket.status == "crashed" else ROCKET_COLOR
        pygame.draw.polygon(screen, body_color, [to_screen(p) for p in rocket.corners()])

        # On-screen readout so we can check the physics.
        weight = (DRY_MASS + rocket.fuel) * GRAVITY
        clearance = max(0.0, min(corner[1] for corner in rocket.corners()))   # NEW
        lines = [f"time      {rocket.time:5.2f} s",
                 f"height    {clearance:5.1f} m",
                 f"speed     {rocket.vy:+6.1f} m/s",
                 f"x         {rocket.x:+6.1f} m",
                 f"side spd  {rocket.vx:+6.1f} m/s",
                 f"tilt      {math.degrees(rocket.tilt()):+6.1f} °",         # NEW
                 f"spin      {math.degrees(rocket.spin):+6.1f} °/s",         # NEW
                 f"nozzle    {math.degrees(rocket.gimbal):+6.1f} °   (A / D)",  # NEW
                 f"throttle  {rocket.throttle:5.0%}   (W / S)",
                 f"fuel      {rocket.fuel:5.1f} kg",
                 f"max TWR   {MAX_THRUST / weight:5.2f}"]
        if rocket.impact_speed is not None:
            lines.append(f"impact    {rocket.impact_speed:5.1f} m/s")
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, TEXT_COLOR), (15, 15 + i * 22))

        # The result, centered on screen, once the flight is over.
        if rocket.status != "flying":
            title = "LANDED" if rocket.status == "landed" else "CRASHED"
            color = LANDED_COLOR if rocket.status == "landed" else CRASHED_COLOR
            message = big_font.render(title, True, color)
            hint_text = "Press R to restart"
            if rocket.crash_reason:                              # NEW: e.g. "Too fast · Press R..."
                hint_text = f"{rocket.crash_reason.capitalize()} · {hint_text}"
            hint = font.render(hint_text, True, TEXT_COLOR)
            # get_rect(center=...) positions an image by its middle instead of its corner.
            screen.blit(message, message.get_rect(center=(WIDTH / 2, HEIGHT / 3)))
            screen.blit(hint, hint.get_rect(center=(WIDTH / 2, HEIGHT / 3 + 45)))

        pygame.display.flip()                         # Show the finished frame.

        clock.tick(FPS)                               # Wait so we run at most FPS frames per second.

    pygame.quit()                                     # Close the window cleanly.


if __name__ == "__main__":
    main()
