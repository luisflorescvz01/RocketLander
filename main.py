"""Step 6: a landing pad to aim for."""

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
NOZZLE_COLOR = (40, 45, 50)
TEXT_COLOR = (30, 40, 45)
WRECK_COLOR = (110, 60, 50)
LANDED_COLOR = (20, 120, 80)
OFF_PAD_COLOR = (170, 110, 20)
CRASHED_COLOR = (180, 50, 40)
PAD_COLOR = (40, 50, 55)
PAD_STRIPE_COLOR = (240, 180, 50)

# --- Physics (all in meters, seconds, and "up is positive") ---------------
DT = 1 / FPS                 # Time step: seconds simulated per frame.
GRAVITY = 9.81               # Downward acceleration, m/s².
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.
START_X = -15.0              # Starting sideways position, m (0 = screen center, + = right).
START_VX = 2.0               # Starting sideways velocity, m/s (+ = moving right).
ROCKET_WIDTH = 2.0           # m
ROCKET_HEIGHT = 8.0          # m
PIXELS_PER_METER = 10        # Closest camera zoom: 1 m is drawn as 10 pixels.

# --- Engine ----------------------------------------------------------------
DRY_MASS = 80.0              # Mass of the empty rocket, kg.
START_FUEL = 30.0            # Fuel on board at the start, kg.
MAX_THRUST = 2200.0          # Engine force at 100% throttle, newtons.
MAX_FUEL_FLOW = 1.375        # Fuel burned per second at 100% throttle, kg/s.
THROTTLE_RATE = 0.5          # How fast W/S move the throttle, per second.
MAX_GIMBAL = math.radians(12)    # Furthest the nozzle can swivel, each way.
GIMBAL_RATE = math.radians(30)   # How fast the nozzle swivels, per second.
NOZZLE_ARM = ROCKET_HEIGHT / 2   # Distance from the center down to the nozzle, m.

# --- Rules -----------------------------------------------------------------
SAFE_SPEED = 5.0             # Touch down slower than this to land, m/s (now total speed).
SAFE_ANGLE = math.radians(15)    # Touch down within this tilt of upright.
PAD_X = 0.0                  # Center of the landing pad, m.
PAD_WIDTH = 12.0             # The rocket's base must touch down within this width, m.


class Rocket:
    """Everything we need to know about the rocket right now, in one place."""

    def __init__(self):
        # Runs when we write Rocket(): sets up a fresh rocket at the start.
        self.x = START_X          # Sideways position of the rocket's center, m.
        self.vx = START_VX        # Sideways velocity, m/s (+ = moving right).
        self.y = START_HEIGHT + ROCKET_HEIGHT / 2   # Height of the rocket's CENTER, m.
        self.vy = 0.0             # Vertical velocity, m/s (negative = falling).
        self.angle = 0.0          # Tilt in radians. 0 = upright, + = nose leans right.
        self.spin = 0.0           # How fast the angle changes, radians/s (+ = clockwise).
        self.gimbal = 0.0         # Nozzle swivel in radians (+ = nozzle swung right).
        self.time = 0.0           # Simulated seconds since the start.
        self.status = "flying"    # "flying", "landed", "off_pad" or "crashed".
        self.impact_speed = None  # Speed at the moment it hits the ground.
        self.crash_reason = None  # Why a touchdown counted as a crash, for the player.
        self.throttle = 0.0       # Engine setting, 0.0 (off) to 1.0 (full).
        self.fuel = START_FUEL    # kg left in the tank.

    def to_world(self, local_x, local_y):
        """Turn a point on the rocket (meters from its center, upright) into world coordinates.

        local_x is to the rocket's right, local_y toward its nose. Rotating clockwise
        by the angle uses the same sin and cos as the tilted thrust.
        """
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (self.x + local_x * c + local_y * s,
                self.y + local_y * c - local_x * s)

    def tilt(self):
        """The angle wrapped into -180°..+180°, so a full spin counts as upright again."""
        return math.remainder(self.angle, math.tau)     # tau = 2π = one full turn.

    def base(self):
        """The middle of the rocket's bottom edge, where the engine is, in world coordinates."""
        return self.to_world(0, -ROCKET_HEIGHT / 2)

    def pad_offset(self):
        """How far the base is from the pad's center, m (negative = left of it)."""
        return self.base()[0] - PAD_X

    def corners(self):
        """The body's four corners in world coordinates, clockwise from bottom-left."""
        w, h = ROCKET_WIDTH / 2, ROCKET_HEIGHT / 2
        return [self.to_world(-w, -h), self.to_world(-w, h),
                self.to_world(w, h), self.to_world(w, -h)]


class Camera:
    """Decides which part of the world is on screen, and at what zoom."""

    def __init__(self):
        self.center_x = 0.0               # World x shown in the middle of the window, m.
        self.scale = PIXELS_PER_METER     # Pixels per meter.

    def follow(self, rocket):
        """Frame the pad and the rocket (with a margin), zooming out only when needed."""
        margin = ROCKET_HEIGHT
        left = min(PAD_X - PAD_WIDTH / 2, rocket.x - margin)
        right = max(PAD_X + PAD_WIDTH / 2, rocket.x + margin)
        top = rocket.y + margin                    # Highest point that must be visible, m.
        fit_width = WIDTH * 0.9 / (right - left)   # Zoom that fits the width, keeping 5% each side.
        fit_height = (GROUND_Y - 20) / top         # Zoom that fits the height, 20 px from the top.
        self.scale = min(PIXELS_PER_METER, fit_width, fit_height)
        self.center_x = (left + right) / 2

    def to_screen_x(self, x_m):
        """Convert a sideways position in meters to a pixel column."""
        return WIDTH / 2 + (x_m - self.center_x) * self.scale

    def to_screen_y(self, height_m):
        """Convert a height in meters (up = +) to a pixel row (down = +)."""
        return GROUND_Y - height_m * self.scale

    def to_screen(self, point):
        """Convert a world point (x, y) in meters to a pixel position."""
        return (self.to_screen_x(point[0]), self.to_screen_y(point[1]))


def main():
    pygame.init()                                     # Start pygame's modules.
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # Open the window.
    pygame.display.set_caption("RocketLander")
    clock = pygame.time.Clock()                       # Keeps the loop at a steady speed.
    font = pygame.font.SysFont("consolas", 18)        # For the on-screen numbers.
    big_font = pygame.font.SysFont("consolas", 48, bold=True)  # For LANDED / CRASHED.

    rocket = Rocket()    # All of the rocket's state in one object.
    camera = Camera()    # Turns world meters into screen pixels, frame by frame.

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

        # A/D choose where the nozzle should point; letting go means "center".
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

            # Thrust points along the body, turned by the nozzle's swivel.
            direction = rocket.angle - rocket.gimbal
            ax = thrust * math.sin(direction) / mass              # Sideways part.
            ay = thrust * math.cos(direction) / mass - GRAVITY    # Upward part, minus gravity.

            # Off-center thrust twists the rocket. Turning has its own a = F / m:
            # angular acceleration = torque / moment of inertia.
            torque = thrust * math.sin(rocket.gimbal) * NOZZLE_ARM
            inertia = mass * (ROCKET_HEIGHT ** 2 + ROCKET_WIDTH ** 2) / 12
            rocket.spin = rocket.spin + torque / inertia * DT     # Torque changes the spin...
            rocket.angle = rocket.angle + rocket.spin * DT        # ...and spin changes the angle.

            rocket.vx = rocket.vx + ax * DT            # Now something pushes sideways.
            rocket.vy = rocket.vy + ay * DT            # Acceleration changes the velocity...
            rocket.y = rocket.y + rocket.vy * DT       # ...and velocity changes the position.
            rocket.x = rocket.x + rocket.vx * DT
            rocket.time = rocket.time + DT

            # Touchdown happens at the lowest corner, not the middle of the bottom.
            lowest = min(corner[1] for corner in rocket.corners())
            if lowest <= 0:           # A corner reached (or passed) the ground this step.
                # Total speed combines both directions (Pythagoras): √(vx² + vy²).
                rocket.impact_speed = math.hypot(rocket.vx, rocket.vy)
                rocket.y = rocket.y - lowest          # Lift it so it rests on the ground.
                rocket.vy = 0.0
                rocket.vx = 0.0       # The ground stops the sideways drift too.
                rocket.spin = 0.0     # ...and the spin.
                # The rules that decide the outcome. Every rule must pass to land.
                reasons = []
                if rocket.impact_speed >= SAFE_SPEED:
                    reasons.append("too fast")
                if abs(rocket.tilt()) > SAFE_ANGLE:
                    reasons.append("too tilted")
                if reasons:
                    rocket.status = "crashed"
                    rocket.crash_reason = " and ".join(reasons)
                # Only a safe touchdown gets asked "was it on the pad?".
                elif abs(rocket.pad_offset()) > PAD_WIDTH / 2:
                    rocket.status = "off_pad"
                else:
                    rocket.status = "landed"

        # 3. Draw: paint everything again, back to front.
        camera.follow(rocket)                         # Choose this frame's view first.
        screen.fill(SKY_COLOR)
        pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))

        # The pad: a dark slab on the ground with yellow stripes, one per 2 m.
        pad_left = camera.to_screen_x(PAD_X - PAD_WIDTH / 2)
        pad_width_px = PAD_WIDTH * camera.scale
        pygame.draw.rect(screen, PAD_COLOR, (pad_left, GROUND_Y, pad_width_px, 8))
        stripes = int(PAD_WIDTH / 2)
        for i in range(stripes):
            x = pad_left + (i + 0.25) * pad_width_px / stripes
            pygame.draw.rect(screen, PAD_STRIPE_COLOR, (x, GROUND_Y + 2, pad_width_px / stripes / 2, 4))

        # The nozzle and flame start at the bottom center of the rocket and point
        # opposite to the thrust: the exhaust goes one way, the rocket is pushed the other.
        nozzle = rocket.to_world(0, -ROCKET_HEIGHT / 2)
        direction = rocket.angle - rocket.gimbal
        exhaust = (-math.sin(direction), -math.cos(direction))   # Unit vector, world meters.
        across = (exhaust[1], -exhaust[0])                       # Perpendicular to it.

        def along(distance, side=0.0):
            """A point `distance` m down the exhaust from the nozzle, `side` m across."""
            return camera.to_screen((nozzle[0] + exhaust[0] * distance + across[0] * side,
                              nozzle[1] + exhaust[1] * distance + across[1] * side))

        if rocket.throttle > 0 and rocket.fuel > 0 and rocket.status == "flying":
            flame_length = rocket.throttle * 4.0                 # Up to 4 m long.
            pygame.draw.polygon(screen, FLAME_COLOR, [
                along(0, -ROCKET_WIDTH / 3), along(0, ROCKET_WIDTH / 3), along(flame_length)])
        # The nozzle: a short dark line that shows which way the engine is swiveled.
        pygame.draw.line(screen, NOZZLE_COLOR, along(0), along(1.0), 4)

        # The body is now a rotated polygon from its four corners.
        body_color = WRECK_COLOR if rocket.status == "crashed" else ROCKET_COLOR
        pygame.draw.polygon(screen, body_color, [camera.to_screen(p) for p in rocket.corners()])

        # On-screen readout so we can check the physics.
        weight = (DRY_MASS + rocket.fuel) * GRAVITY
        clearance = max(0.0, min(corner[1] for corner in rocket.corners()))
        lines = [f"time      {rocket.time:5.2f} s",
                 f"height    {clearance:5.1f} m",
                 f"speed     {rocket.vy:+6.1f} m/s",
                 f"to pad    {rocket.pad_offset():+6.1f} m",
                 f"side spd  {rocket.vx:+6.1f} m/s",
                 f"tilt      {math.degrees(rocket.tilt()):+6.1f} °",
                 f"spin      {math.degrees(rocket.spin):+6.1f} °/s",
                 f"nozzle    {math.degrees(rocket.gimbal):+6.1f} °   (A / D)",
                 f"throttle  {rocket.throttle:5.0%}   (W / S)",
                 f"fuel      {rocket.fuel:5.1f} kg",
                 f"max TWR   {MAX_THRUST / weight:5.2f}"]
        if rocket.impact_speed is not None:
            lines.append(f"impact    {rocket.impact_speed:5.1f} m/s")
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, TEXT_COLOR), (15, 15 + i * 22))

        # The result, centered on screen, once the flight is over.
        if rocket.status != "flying":
            # A dictionary looks up the title and color for each outcome.
            title, color = {"landed": ("LANDED", LANDED_COLOR),
                            "off_pad": ("LANDED OFF PAD", OFF_PAD_COLOR),
                            "crashed": ("CRASHED", CRASHED_COLOR)}[rocket.status]
            message = big_font.render(title, True, color)
            hint_text = "Press R to restart"
            if rocket.status == "off_pad":
                missed_by = abs(rocket.pad_offset()) - PAD_WIDTH / 2
                hint_text = f"Missed the pad by {missed_by:.1f} m · {hint_text}"
            elif rocket.crash_reason:                              # E.g. "Too fast · Press R..."
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
