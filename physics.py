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

    def step(self, throttle, gimbal_command):
        """Advance the rocket by one time step of DT seconds.

        throttle: 0.0 (engine off) to 1.0 (full).
        gimbal_command: -1.0 (nozzle full left) to +1.0 (full right); 0.0 = centered.
        Values outside these ranges are clamped, so any controller is safe to use.
        """
        self.throttle = min(1.0, max(0.0, throttle))
        gimbal_command = min(1.0, max(-1.0, gimbal_command))

        # The nozzle can't jump to the commanded angle: it moves at most GIMBAL_RATE * DT.
        target = gimbal_command * MAX_GIMBAL
        step = GIMBAL_RATE * DT
        self.gimbal = self.gimbal + min(step, max(-step, target - self.gimbal))

        if self.status != "flying":
            self.throttle = 0.0                       # Engine off once down.
            return

        # The engine only pushes while there is fuel left.
        thrust = self.throttle * MAX_THRUST if self.fuel > 0 else 0.0
        mass = DRY_MASS + self.fuel                   # Lighter as fuel burns.
        self.fuel = max(0.0, self.fuel - self.throttle * MAX_FUEL_FLOW * DT)

        # Thrust points along the body, turned by the nozzle's swivel.
        direction = self.angle - self.gimbal
        ax = thrust * math.sin(direction) / mass              # Sideways part.
        ay = thrust * math.cos(direction) / mass - GRAVITY    # Upward part, minus gravity.

        # Off-center thrust twists the rocket. Turning has its own a = F / m:
        # angular acceleration = torque / moment of inertia.
        torque = thrust * math.sin(self.gimbal) * NOZZLE_ARM
        inertia = mass * (ROCKET_HEIGHT ** 2 + ROCKET_WIDTH ** 2) / 12
        self.spin = self.spin + torque / inertia * DT     # Torque changes the spin...
        self.angle = self.angle + self.spin * DT          # ...and spin changes the angle.

        self.vx = self.vx + ax * DT            # Acceleration changes the velocity...
        self.vy = self.vy + ay * DT
        self.y = self.y + self.vy * DT         # ...and velocity changes the position.
        self.x = self.x + self.vx * DT
        self.time = self.time + DT

        # Touchdown happens at the lowest corner, not the middle of the bottom.
        lowest = min(corner[1] for corner in self.corners())
        if lowest <= 0:           # A corner reached (or passed) the ground this step.
            # Total speed combines both directions (Pythagoras): √(vx² + vy²).
            self.impact_speed = math.hypot(self.vx, self.vy)
            self.y = self.y - lowest              # Lift it so it rests on the ground.
            self.vy = 0.0
            self.vx = 0.0         # The ground stops the sideways drift too.
            self.spin = 0.0       # ...and the spin.
            # The rules that decide the outcome. Every rule must pass to land.
            reasons = []
            if self.impact_speed >= SAFE_SPEED:
                reasons.append("too fast")
            if abs(self.tilt()) > SAFE_ANGLE:
                reasons.append("too tilted")
            if reasons:
                self.status = "crashed"
                self.crash_reason = " and ".join(reasons)
            # Only a safe touchdown gets asked "was it on the pad?".
            elif abs(self.pad_offset()) > PAD_WIDTH / 2:
                self.status = "off_pad"
            else:
                self.status = "landed"
