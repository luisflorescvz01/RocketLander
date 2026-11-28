"""RocketLander: fly the rocket with the keyboard. Physics lives in physics.py."""

import math

import pygame

from physics import (
    DT, GRAVITY, ROCKET_WIDTH, ROCKET_HEIGHT, LEG_SPAN, LEG_DROP,
    DRY_MASS, MAX_THRUST, PAD_X, PAD_WIDTH, Rocket,
)

# --- Settings -------------------------------------------------------------
WIDTH, HEIGHT = 800, 600     # Window size in pixels.
FPS = 60                     # Frames per second we aim for.
GROUND_Y = HEIGHT - 60       # Pixel row where the ground starts (y grows downward).

SKY_COLOR = (225, 235, 240)  # Colors are (red, green, blue), each 0-255.
GRID_COLOR = (205, 218, 224)
GRID_LABEL_COLOR = (120, 135, 142)
GROUND_COLOR = (90, 100, 105)
ROCKET_COLOR = (240, 180, 50)
FLAME_COLOR = (255, 120, 30)
NOZZLE_COLOR = (40, 45, 50)
LEG_COLOR = (60, 70, 75)
CONTACT_COLOR = (30, 150, 90)            # A foot pad that is on the ground.
TEXT_COLOR = (30, 40, 45)
WRECK_COLOR = (110, 60, 50)
LANDED_COLOR = (20, 120, 80)
OFF_PAD_COLOR = (170, 110, 20)
CRASHED_COLOR = (180, 50, 40)
PAD_COLOR = (40, 50, 55)
PAD_STRIPE_COLOR = (240, 180, 50)

PIXELS_PER_METER = 10        # Closest camera zoom: 1 m is drawn as 10 pixels.
THROTTLE_RATE = 0.5          # How fast W/S move the throttle, per second.

# Where the legs attach to the body, measured up from its bottom edge (drawing only).
LEG_HIP_HEIGHT = 1.6         # The main strut's top joint, m.
LEG_BRACE_HEIGHT = 0.2       # The brace's top joint, m.


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

    def to_world_x(self, x_px):
        """The opposite of to_screen_x: which world x (m) is at this pixel column."""
        return self.center_x + (x_px - WIDTH / 2) / self.scale


def grid_spacing(scale, min_pixels=50):
    """The smallest round distance (1, 2, 5, 10, 20, 50, ... m) at least min_pixels apart."""
    spacing = 1
    while True:
        for step in (1, 2, 5):
            if step * spacing * scale >= min_pixels:
                return step * spacing
        spacing = spacing * 10


def draw_grid(screen, camera, font):
    """Light lines at round distances, placed in world meters so they move with the camera."""
    spacing = grid_spacing(camera.scale)
    # Vertical lines: every multiple of spacing between the window's left and right edges.
    first = math.floor(camera.to_world_x(0) / spacing)
    last = math.ceil(camera.to_world_x(WIDTH) / spacing)
    for i in range(first, last + 1):
        x = camera.to_screen_x(i * spacing)
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, GROUND_Y))
    # Horizontal lines: every multiple of spacing above the ground, labeled on the right.
    height = spacing
    while camera.to_screen_y(height) > 0:
        y = camera.to_screen_y(height)
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WIDTH, y))
        label = font.render(f"{height} m", True, GRID_LABEL_COLOR)
        screen.blit(label, label.get_rect(bottomright=(WIDTH - 6, y - 2)))
        height = height + spacing


def main():
    pygame.init()                                     # Start pygame's modules.
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # Open the window.
    pygame.display.set_caption("RocketLander")
    clock = pygame.time.Clock()                       # Keeps the loop at a steady speed.
    font = pygame.font.SysFont("consolas", 18)        # For the on-screen numbers.
    big_font = pygame.font.SysFont("consolas", 48, bold=True)  # For LANDED / CRASHED.
    small_font = pygame.font.SysFont("consolas", 13)           # For grid labels.

    rocket = Rocket()    # All of the rocket's state in one object.
    camera = Camera()    # Turns world meters into screen pixels, frame by frame.
    throttle = 0.0       # The keyboard's throttle setting, nudged by W / S.

    running = True
    while running:
        # 1. Handle events: things the player did since the last frame.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:             # The window's X button.
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                rocket = Rocket()                     # Restart = a brand-new rocket...
                throttle = 0.0                        # ...with the engine set to off.

        # Held keys. Events say "W was pressed"; get_pressed() says "W is down now".
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            throttle = throttle + THROTTLE_RATE * DT
        if keys[pygame.K_s]:
            throttle = throttle - THROTTLE_RATE * DT
        throttle = min(1.0, max(0.0, throttle))       # Keep it between 0 and 1.
        # A/D aim the nozzle: -1 = full left, +1 = full right, 0 (neither key) = center.
        gimbal_command = keys[pygame.K_d] - keys[pygame.K_a]

        # 2. Update the game state: one physics step, all done in physics.py.
        rocket.step(throttle, gimbal_command)

        # 3. Draw: paint everything again, back to front.
        camera.follow(rocket)                         # Choose this frame's view first.
        screen.fill(SKY_COLOR)
        draw_grid(screen, camera, small_font)         # Behind everything else.
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
        nozzle = rocket.base()
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
        pygame.draw.line(screen, NOZZLE_COLOR, along(0), along(0.8), 4)

        # The legs, drawn before the body so they seem to attach behind it. Every point is
        # in the rocket's own coordinates, so to_world() tilts the legs along with the body.
        bottom = -ROCKET_HEIGHT / 2
        strut_width = max(2, round(0.25 * camera.scale))
        for side, foot, touching in zip((-1, 1), rocket.feet(), rocket.foot_contacts):
            hip = rocket.to_world(side * ROCKET_WIDTH / 2, bottom + LEG_HIP_HEIGHT)
            brace_top = rocket.to_world(side * ROCKET_WIDTH / 2, bottom + LEG_BRACE_HEIGHT)
            middle = ((hip[0] + foot[0]) / 2, (hip[1] + foot[1]) / 2)
            pad_left = rocket.to_world(side * LEG_SPAN - 0.4, bottom - LEG_DROP)
            pad_right = rocket.to_world(side * LEG_SPAN + 0.4, bottom - LEG_DROP)
            pygame.draw.line(screen, LEG_COLOR, camera.to_screen(brace_top),
                             camera.to_screen(middle), max(1, strut_width // 2))
            pygame.draw.line(screen, LEG_COLOR, camera.to_screen(hip), camera.to_screen(foot), strut_width)
            pad_color = CONTACT_COLOR if touching else LEG_COLOR
            pygame.draw.line(screen, pad_color, camera.to_screen(pad_left), camera.to_screen(pad_right), strut_width)

        # The body is now a rotated polygon from its four corners.
        body_color = WRECK_COLOR if rocket.status == "crashed" else ROCKET_COLOR
        pygame.draw.polygon(screen, body_color, [camera.to_screen(p) for p in rocket.corners()])

        # On-screen readout so we can check the physics.
        weight = (DRY_MASS + rocket.fuel) * GRAVITY
        clearance = max(0.0, rocket.clearance())
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
        left, right = ("down" if touching else "up" for touching in rocket.foot_contacts)
        lines.append(f"legs      {left} / {right}")
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
