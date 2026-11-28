"""RocketLander physics: the rocket and its world, with no pygame and no window."""

import math

# --- Physics (all in meters, seconds, and "up is positive") ---------------
DT = 1 / 60                  # Time step: seconds simulated per step (one frame at 60 FPS).
SUBSTEPS = 4                 # Each step is split into this many smaller physics steps.
GRAVITY = 9.81               # Downward acceleration, m/s².
START_HEIGHT = 40.0          # Rocket's starting height above ground, m.
START_X = -15.0              # Starting sideways position, m (0 = screen center, + = right).
START_VX = 2.0               # Starting sideways velocity, m/s (+ = moving right).
ROCKET_WIDTH = 2.0           # m
ROCKET_HEIGHT = 8.0          # m
LEG_SPAN = 2.2               # How far each foot is out from the center line, m.
LEG_DROP = 1.2               # How far the feet reach below the bottom of the body, m.

# --- Engine ----------------------------------------------------------------
DRY_MASS = 80.0              # Mass of the empty rocket, kg.
START_FUEL = 30.0            # Fuel on board at the start, kg.
MAX_THRUST = 2200.0          # Engine force at 100% throttle, newtons.
MAX_FUEL_FLOW = 1.375        # Fuel burned per second at 100% throttle, kg/s.
MAX_GIMBAL = math.radians(12)    # Furthest the nozzle can swivel, each way.
GIMBAL_RATE = math.radians(30)   # How fast the nozzle swivels, per second.
NOZZLE_ARM = ROCKET_HEIGHT / 2   # Distance from the center down to the nozzle, m.

# --- Landing legs: a spring and a damper in each leg, and friction at each foot -----
LEG_STIFFNESS = 5200.0       # Spring: N of push per m the foot is pressed into the ground.
LEG_DAMPING = 670.0          # Damper: N of push per m/s the foot moves into the ground.
FRICTION = 0.85              # A foot's sideways grip can be at most this fraction of its push.
GRIP = 310.0                 # N of sideways resistance per m/s a loaded foot slides.
# After a crash the hull itself can hit the ground: much stiffer than a leg, like metal.
BODY_STIFFNESS = 24000.0     # N of push per m a body corner is pressed into the ground.
BODY_DAMPING = 1400.0        # N of push per m/s a body corner moves into the ground.

# --- Rules -----------------------------------------------------------------
SAFE_SPEED = 5.0             # A foot touching down faster than this breaks its leg, m/s.
SAFE_ANGLE = math.radians(15)    # To count as landed, stay within this tilt of upright.
SETTLE_SPEED = 0.6           # ...moving slower than this, m/s...
SETTLE_SPIN = math.radians(15)   # ...spinning slower than this...
SETTLE_TIME = 0.3            # ...with both feet down, for this long in a row, s.
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
        self.impact_speed = None  # Fastest a foot has hit the ground so far, m/s.
        self.crash_reason = None  # Why the flight counted as a crash, for the player.
        self.foot_contacts = [False, False]   # Is each foot [left, right] on the ground?
        self.settle_time = 0.0    # How long it has been resting calmly on both feet, s.
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

    def feet(self):
        """The two feet in world coordinates: [left, right]."""
        foot_y = -ROCKET_HEIGHT / 2 - LEG_DROP
        return [self.to_world(-LEG_SPAN, foot_y), self.to_world(LEG_SPAN, foot_y)]

    def stance_center(self):
        """The point midway between the two feet, in world coordinates."""
        (left_x, left_y), (right_x, right_y) = self.feet()
        return ((left_x + right_x) / 2, (left_y + right_y) / 2)

    def pad_offset(self):
        """How far the middle of the stance is from the pad's center, m (negative = left)."""
        return self.stance_center()[0] - PAD_X

    def corners(self):
        """The body's four corners in world coordinates, clockwise from bottom-left."""
        w, h = ROCKET_WIDTH / 2, ROCKET_HEIGHT / 2
        return [self.to_world(-w, -h), self.to_world(-w, h),
                self.to_world(w, h), self.to_world(w, -h)]

    def clearance(self):
        """Height of the lowest point (a foot or a body corner) above the ground, m."""
        return min(y for _, y in self.feet() + self.corners())

    def point_velocity(self, point):
        """How fast a point on the rocket is moving, m/s: the center's motion plus the spin's.

        Spinning clockwise moves a point on the right side down and a point above up-right.
        """
        dx, dy = point[0] - self.x, point[1] - self.y
        return (self.vx + self.spin * dy, self.vy - self.spin * dx)

    def step(self, throttle, gimbal_command):
        """Advance the rocket by one time step of DT seconds.

        throttle: 0.0 (engine off) to 1.0 (full).
        gimbal_command: -1.0 (nozzle full left) to +1.0 (full right); 0.0 = centered.
        Values outside these ranges are clamped, so any controller is safe to use.
        """
        self.throttle = min(1.0, max(0.0, throttle))
        gimbal_command = min(1.0, max(-1.0, gimbal_command))

        # Aim the nozzle, then run several small physics steps that together last DT.
        # Small steps keep stiff things (like the landing-leg springs) stable.
        # Once the flight is over the controls do nothing: the nozzle stays where it is.
        target = gimbal_command * MAX_GIMBAL if self.status == "flying" else self.gimbal
        for _ in range(SUBSTEPS):
            self._substep(target, DT / SUBSTEPS)

    def _substep(self, gimbal_target, dt):
        """One small physics step of dt seconds. Only step() should call this."""
        # The nozzle can't jump to the commanded angle: it moves at most GIMBAL_RATE * dt.
        max_move = GIMBAL_RATE * dt
        self.gimbal = self.gimbal + min(max_move, max(-max_move, gimbal_target - self.gimbal))

        if self.status != "flying":
            self.throttle = 0.0                       # Engine off once the flight is over.
        if self.status in ("landed", "off_pad"):
            return                                    # A landed rocket rests where it is.
        # Still flying, or a crashed wreck that keeps tumbling, sliding and settling.

        # The engine only pushes while there is fuel left.
        thrust = self.throttle * MAX_THRUST if self.fuel > 0 else 0.0
        mass = DRY_MASS + self.fuel                   # Lighter as fuel burns.
        self.fuel = max(0.0, self.fuel - self.throttle * MAX_FUEL_FLOW * dt)

        # Thrust points along the body, turned by the nozzle's swivel.
        direction = self.angle - self.gimbal
        force_x = thrust * math.sin(direction)                # Sideways part.
        force_y = thrust * math.cos(direction) - mass * GRAVITY   # Upward part, minus weight.
        # Off-center thrust twists the rocket.
        torque = thrust * math.sin(self.gimbal) * NOZZLE_ARM

        # The ground pushes on any foot pressed into it. Add those forces and twists too.
        ground_x, ground_y, ground_torque = self._ground_forces()
        force_x = force_x + ground_x
        force_y = force_y + ground_y
        torque = torque + ground_torque

        # a = F / m for moving, and angular acceleration = torque / inertia for turning.
        inertia = mass * (ROCKET_HEIGHT ** 2 + ROCKET_WIDTH ** 2) / 12
        self.spin = self.spin + torque / inertia * dt     # Torque changes the spin...
        self.angle = self.angle + self.spin * dt          # ...and spin changes the angle.
        self.vx = self.vx + force_x / mass * dt           # Force changes the velocity...
        self.vy = self.vy + force_y / mass * dt
        self.y = self.y + self.vy * dt                    # ...and velocity changes the position.
        self.x = self.x + self.vx * dt
        self.time = self.time + dt

        if self.status == "flying":
            self._judge(dt)
        else:
            # A wreck's outcome can't change, but keep track of which feet touch the ground.
            self.foot_contacts = [y <= 0 for _, y in self.feet()]

    def _ground_forces(self):
        """The ground's push on each contact point below it: (sideways, upward, torque)."""
        # Each contact point has its own spring stiffness and damping.
        contacts = [(foot, LEG_STIFFNESS, LEG_DAMPING) for foot in self.feet()]
        if self.status == "crashed":
            # A wreck can lie on its side or nose, so the hull's corners touch the ground too.
            contacts += [(corner, BODY_STIFFNESS, BODY_DAMPING) for corner in self.corners()]

        total_x = total_y = total_torque = 0.0
        for point, stiffness, damping in contacts:
            depth = -point[1]                     # How far it is pressed into the ground.
            if depth <= 0:
                continue                          # Not touching: no force.
            point_vx, point_vy = self.point_velocity(point)
            # Spring (deeper = harder) plus damper (moving down faster = harder).
            # The ground can push but never pull, so the push is never below zero.
            push = max(0.0, depth * stiffness - point_vy * damping)
            # Friction resists sliding, but can't grip harder than FRICTION x push.
            limit = FRICTION * push
            friction = min(limit, max(-limit, -point_vx * GRIP))
            total_x = total_x + friction
            total_y = total_y + push
            # A push away from the center twists the rocket, like the off-center thrust.
            dx, dy = point[0] - self.x, point[1] - self.y
            total_torque = total_torque + dy * friction - dx * push
        return total_x, total_y, total_torque

    def _judge(self, dt):
        """Check the ground rules after moving: broken leg, body impact, or a calm landing."""
        feet = self.feet()
        for i, foot in enumerate(feet):
            touching = foot[1] <= 0
            if touching and not self.foot_contacts[i]:          # This foot just touched down.
                speed = math.hypot(*self.point_velocity(foot))
                self.impact_speed = max(self.impact_speed or 0.0, speed)
                if speed > SAFE_SPEED:
                    self._crash("a leg broke: it touched down too fast")
                    return
            self.foot_contacts[i] = touching

        if any(y <= 0 for _, y in self.corners()):
            self._crash("the body hit the ground")
            return

        # Landed = resting calmly on both feet for SETTLE_TIME in a row.
        calm = (all(self.foot_contacts)
                and math.hypot(self.vx, self.vy) <= SETTLE_SPEED
                and abs(self.tilt()) <= SAFE_ANGLE
                and abs(self.spin) <= SETTLE_SPIN)
        self.settle_time = self.settle_time + dt if calm else 0.0
        if self.settle_time >= SETTLE_TIME:
            # Only a calm landing gets asked "was it on the pad?".
            self.status = "off_pad" if abs(self.pad_offset()) > PAD_WIDTH / 2 else "landed"

    def _crash(self, reason):
        """End the flight as a crash. The physics keeps running: the wreck tumbles and settles."""
        self.status = "crashed"
        self.crash_reason = reason
        self.throttle = 0.0
