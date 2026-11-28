"""RocketLander physics: the rocket and its world, with no pygame and no window."""

import math

# --- Physics (all in meters, seconds, and "up is positive") ---------------
DT = 1 / 60                  # Time step: seconds simulated per step (one frame at 60 FPS).
GRAVITY = 9.81               # Downward acceleration, m/s².
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.
START_X = -15.0              # Starting sideways position, m (0 = screen center, + = right).
START_VX = 2.0               # Starting sideways velocity, m/s (+ = moving right).
ROCKET_WIDTH = 2.0           # m
ROCKET_HEIGHT = 8.0          # m

# --- Engine ----------------------------------------------------------------
DRY_MASS = 80.0              # Mass of the empty rocket, kg.
START_FUEL = 30.0            # Fuel on board at the start, kg.
MAX_THRUST = 2200.0          # Engine force at 100% throttle, newtons.
MAX_FUEL_FLOW = 1.375        # Fuel burned per second at 100% throttle, kg/s.
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
